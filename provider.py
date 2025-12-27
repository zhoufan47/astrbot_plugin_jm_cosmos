import os
import yaml
import traceback
import asyncio
import concurrent.futures
from typing import Optional, List, Tuple
from threading import Lock

import jmcomic
from astrbot.api import logger

from .config import PluginConfig
from .models import ComicInfo
from .storage import StorageManager


class JMProvider:
    """负责与 jmcomic 库交互，不包含任何 AstrBot 逻辑"""

    def __init__(self, config: PluginConfig, storage: StorageManager):
        self.config = config
        self.storage = storage
        self.client = None
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(config.max_threads, 20),
            thread_name_prefix="jm_worker"
        )
        self._download_lock = Lock()
        self._active_downloads = set()

        # 初始化 jmcomic 配置
        self._init_option()

    def _init_option(self):
        """配置 jmcomic 的 Option"""
        # 构建配置字典 (简化原代码的构建过程)
        option_dict = {
            "client": {
                "domain": self.config.domain_list,
                "postman": {
                    "meta_data": {
                        "proxies": {"https": self.config.proxy} if self.config.proxy else None,
                        "cookies": {"AVS": self.config.avs_cookie} if self.config.avs_cookie else None,
                        "headers": {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                        }
                    }
                }
            },
            "dir_rule": {"base_dir": self.storage.dirs["downloads"]},
            "download": {
                "threading": {"image": self.config.max_threads}
            },
            # 配置插件：下载完自动转PDF
            "plugins": {
                "after_album": [{
                    "plugin": "img2pdf",
                    "kwargs": {
                        "pdf_dir": self.storage.dirs["pdfs"],
                        "filename_rule": "Aid",
                        # 如果需要加密 PDF 可以在这里加
                        "encrypt": {
                            "password": "123"
                        }
                    }
                }]
            }
        }

        # 应用配置
        jmcomic.create_option_by_str(yaml.safe_dump(option_dict))

    def login(self) -> bool:
        """执行登录"""
        try:
            # 这里的 client 创建逻辑可以根据需要优化，比如支持特定 domain
            self.client = jmcomic.JmOption.default().new_jm_client()
            if self.config.is_jm_login and self.config.jm_username and self.config.jm_passwd:
                logger.info(f"JMComic 登录尝试: {self.config.jm_username},{self.config.jm_passwd}")
                self.client.login(self.config.jm_username, self.config.jm_passwd)
                logger.info(f"JMComic 登录成功: {self.config.jm_username}")
            return True
        except Exception as e:
            logger.error(f"JMComic 登录失败: {e}")
            return False

    def get_comic_detail(self, comic_id: str) -> Optional[ComicInfo]:
        """获取漫画详情并转换为标准 Model"""
        if not self.client:
            self.login()

        try:
            album = self.client.get_album_detail(comic_id)

            # 计算总页数
            total_pages = 0
            try:
                # 注意：这可能会触发网络请求，视库的实现而定
                # 简单实现：只统计章节数，或者需要遍历章节统计图片
                total_pages = sum(len(ep) for ep in album)
            except:
                pass

            return ComicInfo(
                id=str(album.album_id),
                title=album.title,
                tags=album.tags,
                author=album.author if hasattr(album, 'author') else [],
                pub_date=getattr(album, 'pub_date', ''),
                total_pages=total_pages
            )
        except Exception as e:
            logger.error(f"获取漫画详情失败 [{comic_id}]: {e}")
            # 原代码中的 retry/fallback 逻辑应该封装在这里
            return None

    def download_cover(self, comic_id: str) -> Optional[str]:
        """下载封面，返回路径"""
        target_path = self.storage.get_cover_path(comic_id)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
            return target_path

        try:
            if not self.client: self.login()
            album = self.client.get_album_detail(comic_id)
            if not album: return None

            # 获取第一张图作为封面
            image_detail = album[0][0]
            self.client.download_by_image_detail(image_detail, target_path)
            return target_path
        except Exception as e:
            logger.error(f"封面下载失败: {e}")
            return None

    async def download_comic_async(self, comic_id: str) -> Tuple[bool, str]:
        """异步下载漫画入口"""
        if comic_id in self._active_downloads:
            return False, "该漫画正在下载中"

        with self._download_lock:
            self._active_downloads.add(comic_id)

        try:
            loop = asyncio.get_running_loop()
            # 在线程池中执行阻塞的下载任务
            await loop.run_in_executor(
                self._thread_pool,
                self._download_sync,
                comic_id
            )
            return True, "下载完成"
        except Exception as e:
            error_msg = f"下载异常: {str(e)}"
            logger.error(error_msg)
            if self.config.debug_mode:
                self.storage.save_debug_log(f"err_{comic_id}", traceback.format_exc())
            return False, error_msg
        finally:
            with self._download_lock:
                self._active_downloads.discard(comic_id)

    def _download_sync(self, comic_id: str):
        """同步下载逻辑 (运行在线程池中)"""
        # 这里放置复杂的重试、多域名切换逻辑
        # 简化版：直接调用库
        jmcomic.download_album(comic_id, jmcomic.JmOption.default())

    def search_site(self, query: str, page: int = 1) -> List[Tuple[str, str]]:
        """搜索"""
        if not self.client: self.login()
        try:
            # 返回 [(id, title), ...]
            resp = self.client.search_site(query, page=page)
            return list(resp.iter_id_title())
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    def close(self):
        self._thread_pool.shutdown(wait=False)