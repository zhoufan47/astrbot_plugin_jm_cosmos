import asyncio
import os
import yaml
import traceback
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Optional, Tuple, List

import jmcomic
from jmcomic import JmHtmlClient, JmApiClient

from .config import CosmosConfig
from .utils import ResourceManager, convert_t2s, extract_title_from_html
from .models import ComicInfo, DownloadResult

logger = logging.getLogger("astrbot")


class JMService:
    """
    核心业务服务
    负责：
    1. 管理 JMClient 实例
    2. 处理下载逻辑、重试机制
    3. 搜索与详情获取
    """

    def __init__(self, config: CosmosConfig, resource_manager: ResourceManager):
        self.config = config
        self.rm = resource_manager
        self.client: Optional[JmHtmlClient] = None
        self.option = None

        # 限制并发数
        self._thread_pool = ThreadPoolExecutor(
            max_workers=min(config.max_threads, 20),
            thread_name_prefix="jm_svc"
        )
        self._download_lock = Lock()
        self._downloading_ids = set()

        # 初始化
        self.update_client_config()

    def update_client_config(self):
        """根据当前 Config 重建 Client 和 Option"""
        try:
            yaml_str = self._build_option_yaml()
            self.option = jmcomic.create_option_by_str(yaml_str)

            # 创建新客户端
            new_client = self.option.new_jm_client()
            if self.config.is_jm_login and self.config.jm_username:
                try:
                    new_client.login(self.config.jm_username, self.config.jm_passwd)
                    logger.info(f"JM客户端登录成功: {self.config.jm_username}")
                except Exception as e:
                    logger.warning(f"JM客户端登录失败: {e}")

            self.client = new_client
        except Exception as e:
            logger.error(f"初始化JM客户端失败: {e}")

    def _build_option_yaml(self) -> str:
        """构建 jmcomic 需要的配置"""
        conf = {
            "client": {
                "impl": "html",
                "domain": self.config.domain_list,
                "retry_times": 5,
                "postman": {
                    "meta_data": {
                        "proxies": {"https": self.config.proxy} if self.config.proxy else None,
                        "cookies": {"AVS": self.config.avs_cookie},
                        "headers": {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                            "Referer": f"https://{self.config.domain_list[0]}/",
                        }
                    }
                }
            },
            "download": {
                "cache": True,
                "image": {"decode": True, "suffix": ".jpg"},
                "threading": {
                    "image": self.config.max_threads,
                    "photo": self.config.max_threads,
                }
            },
            "dir_rule": {"base_dir": self.rm.downloads_dir},
            "plugins": {
                "after_album": [{
                    "plugin": "img2pdf",
                    "kwargs": {
                        "pdf_dir": self.rm.pdfs_dir,
                        "filename_rule": "Aid",
                        "encrypt": {"password": "123"}
                    }
                }]
            }
        }
        return yaml.safe_dump(conf, allow_unicode=True)

    async def get_comic_detail(self, comic_id: str) -> Tuple[Optional[ComicInfo], str]:
        """获取漫画详情，自动下载封面"""
        try:
            # 异步执行 IO 密集型操作
            album = await asyncio.get_event_loop().run_in_executor(
                self._thread_pool,
                lambda: self.client.get_album_detail(comic_id)
            )

            # 转换 Tags
            tags = [convert_t2s(t) for t in album.tags]

            # 下载封面
            cover_path = self.rm.get_cover_path(comic_id)
            if not os.path.exists(cover_path) or os.path.getsize(cover_path) < 1000:
                if len(album) > 0 and len(album[0]) > 0:
                    # 使用线程池下载封面
                    await asyncio.get_event_loop().run_in_executor(
                        self._thread_pool,
                        lambda: self.client.download_by_image_detail(album[0][0], cover_path)
                    )

            info = ComicInfo(
                id=comic_id,
                title=album.title,
                tags=tags,
                pub_date=getattr(album, 'pub_date', '未知'),
                total_pages=sum(len(ep) for ep in album),
                cover_path=cover_path
            )
            return info, ""

        except Exception as e:
            msg = self._handle_error(e)
            # 尝试 HTML 解析的回退逻辑
            if "结构" in msg:
                try:
                    html = await asyncio.get_event_loop().run_in_executor(
                        self._thread_pool,
                        lambda: self.client._postman.get_html(f"https://{self.config.domain_list[0]}/album/{comic_id}")
                    )
                    title = extract_title_from_html(html)
                    return None, f"{msg} (解析到标题: {title})"
                except:
                    pass
            return None, msg

    async def download_comic(self, comic_id: str) -> DownloadResult:
        """执行下载任务，包含重试和并发锁"""
        with self._download_lock:
            if comic_id in self._downloading_ids:
                return DownloadResult(False, "该任务正在进行中")
            self._downloading_ids.add(comic_id)

        try:
            # 空间检查
            if not self.rm.check_storage_space():
                cleaned = self.rm.cleanup_old_files()
                if not self.rm.check_storage_space():
                    return DownloadResult(False, f"存储空间不足，已清理 {cleaned} 个旧文件但仍不足")

            # 核心下载逻辑 (放入线程池)
            await asyncio.get_event_loop().run_in_executor(
                self._thread_pool,
                lambda: self._download_with_retry_sync(comic_id)
            )

            # 检查 PDF 结果
            pdf_path = self.rm.get_pdf_path(comic_id)
            if os.path.exists(pdf_path):
                return DownloadResult(True, "下载完成", pdf_path)
            else:
                return DownloadResult(False, "下载似乎完成，但未生成PDF，请检查日志")

        except Exception as e:
            logger.error(f"下载异常: {traceback.format_exc()}")
            return DownloadResult(False, self._handle_error(e))
        finally:
            with self._download_lock:
                self._downloading_ids.discard(comic_id)

    def _download_with_retry_sync(self, comic_id: str):
        """同步的下载重试逻辑 (运行在线程中)"""
        current_domains = self.config.domain_list
        error_buffer = []

        # 尝试使用当前 Client 下载
        try:
            logger.info(f"开始下载 {comic_id}，域名: {current_domains[0]}")
            jmcomic.download_album(comic_id, self.option)
            return
        except Exception as e:
            error_buffer.append(str(e))
            logger.warning(f"主域名下载失败: {e}")

        # 备用域名重试策略
        for domain in current_domains[1:]:
            try:
                logger.info(f"尝试备用域名: {domain}")
                # 创建临时 option
                temp_option = jmcomic.create_option_by_str(self._build_option_yaml())
                temp_option.client.domain = [domain]
                jmcomic.download_album(comic_id, temp_option)
                logger.info(f"备用域名 {domain} 下载成功")
                return
            except Exception as e:
                error_buffer.append(f"{domain}: {e}")

        raise Exception(f"所有域名尝试失败: {'; '.join(error_buffer)}")

    async def get_preview_images(self, comic_id: str, max_pages: int = 3) -> Tuple[bool, str, List[str]]:
        """下载前几页预览"""
        try:
            # 创建预览目录
            preview_dir = os.path.join(self.rm.base_dir, "preview_downloads", comic_id)
            os.makedirs(preview_dir, exist_ok=True)

            # 在线程池中执行
            def _sync_preview():
                album = self.client.get_album_detail(comic_id)
                images = []
                count = 0
                for episode in album:
                    if count >= max_pages: break
                    photos = self.client.get_photo_detail(episode.photo_id, False)
                    for photo in photos:
                        if count >= max_pages: break
                        path = os.path.join(preview_dir, f"{count}.jpg")
                        self.client.download_by_image_detail(photo, path)
                        if os.path.exists(path) and os.path.getsize(path) > 1000:
                            images.append(path)
                            count += 1
                return images

            img_paths = await asyncio.get_event_loop().run_in_executor(self._thread_pool, _sync_preview)

            if img_paths:
                return True, "成功", img_paths
            return False, "未能获取图片", []

        except Exception as e:
            return False, str(e), []

    def _handle_error(self, error: Exception) -> str:
        msg = str(error)
        if "timeout" in msg.lower(): return "连接超时，请检查网络"
        if "没有匹配上" in msg: return "网站结构可能已变更，或域名失效"
        if "permission" in msg.lower(): return "文件权限错误"
        return msg[:100]

    def shutdown(self):
        self._thread_pool.shutdown(wait=False)