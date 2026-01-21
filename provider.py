import os
import re

import yaml
import traceback
import asyncio
import concurrent.futures
from typing import Optional, List, Tuple, Set
from threading import Lock

import jmcomic
from astrbot.api import logger
from jmcomic import JmMagicConstants

from .config import PluginConfig
from .models import ComicInfo
from .storage import StorageManager

# 添加自定义解析函数用于处理jmcomic库无法解析的情况
def extract_title_from_html(html_content: str) -> str:
    """从HTML内容中提取标题的多种尝试方法"""
    # 使用多种模式进行正则匹配
    patterns = [
        r"<h1[^>]*>([^<]+)</h1>",
        r"<title>([^<]+)</title>",
        r'name:\s*[\'"]([^\'"]+)[\'"]',
        r'"name":\s*"([^"]+)"',
        r'data-title=[\'"]([^\'"]+)[\'"]',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html_content)
        if matches:
            title = matches[0].strip()
            logger.info(f"已使用备用解析方法找到标题: {title}")
            return title

    return "未知标题"

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
        self.downloading_covers: Set[str] = set()
        self._download_lock = Lock()
        self._active_downloads = set()

        # 初始化 jmcomic 配置
        self.option = self._init_option()

    def _init_option(self):
        pdf_dir=self.storage.dirs.get("pdfs")
        download_dir=self.storage.dirs.get("downloads")
        """配置 jmcomic 的 Option"""
        # 构建配置字典 (简化原代码的构建过程)
        option_dict = {
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
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                            "Referer": f"https://{self.config.domain_list[0]}/",
                            "Connection": "keep-alive",
                            "Cache-Control": "max-age=0",
                        },
                    }
                }
            },
            "dir_rule": {"base_dir": download_dir},
            "download": {
                "cache": True,
                "image": {"decode": True, "suffix": ".jpg"},
                "threading": {
                    "image": self.config.max_threads,
                    "photo": self.config.max_threads,
                },
            },
            # 配置插件：下载完自动转PDF
            "plugins": {
                "after_album": [{
                    "plugin": "img2pdf",
                    "kwargs": {
                        "pdf_dir": pdf_dir,
                        "filename_rule": "Aid",
                        # 如果需要加密 PDF 可以在这里加
                        "encrypt": {
                            "password": self.config.pdf_password
                        }
                    }
                }]
            }
        }
        logger.info(f"download存储目录: {download_dir}")
        logger.info(f"pdf存储目录: {pdf_dir}")
        yaml_str = yaml.safe_dump(option_dict, allow_unicode=True)
        # 应用配置
        return jmcomic.create_option_by_str(yaml_str)


    def login(self) -> bool:
        """执行登录"""
        try:
            if not self.client:
                self.client = self.option.new_jm_client()
            if self.config.is_jm_login and self.config.jm_username and self.config.jm_passwd:
                logger.info(f"JMComic 登录尝试: {self.config.jm_username},{self.config.jm_passwd}")
                self.client.login(self.config.jm_username, self.config.jm_passwd)
                logger.info(f"JMComic 登录成功: {self.config.jm_username}")
            return True
        except Exception as e:
            logger.error(f"JMComic 登录失败: {e}")
            return False

    def get_total_pages(self, album) -> int:
        """获取漫画总页数"""
        try:
            return sum(len(self.client.get_photo_detail(p.photo_id, False)) for p in album)
        except Exception as e:
            logger.error(f"获取总页数失败: {str(e)}")
            return 0

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
                total_pages = self.get_total_pages(album)
            except:
                pass

            return ComicInfo(
                id=str(album.album_id),
                title=album.title,
                tags=album.tags,
                #author=album.authors[0],
                pub_date=getattr(album, 'pub_date', ''),
                total_pages=total_pages
            )
        except Exception as e:
            logger.error(f"获取漫画详情失败 [{comic_id}]: {e}")
            # 原代码中的 retry/fallback 逻辑应该封装在这里
            return None

    def download_cover(self, album_id: str) -> Tuple[bool, str]:
        """下载漫画封面"""
        logger.info(f"检索下载队列: {self.downloading_covers}")

        if album_id in self.downloading_covers:
            return False, "封面正在下载中"
        logger.info(f"下载漫画封面任务生成: {album_id}")
        self.downloading_covers.add(album_id)
        try:
            # 记录在对应ID下载封面
            logger.info(f"开始下载漫画封面，ID: {album_id}")
            try:
                album = self.client.get_album_detail(album_id)
                if not album:
                    return False, "漫画不存在"

                # 记录漫画标题
                logger.info(f"获取到漫画信息，ID: {album_id}, 标题: {album.title}")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"获取漫画详情失败: {error_msg}")

                if "文本没有匹配上字段" in error_msg and "pattern:" in error_msg:
                    # 尝试手动解析HTML
                    try:
                        html_content = self.client._postman.get_html(
                            f"https://{self.config.domain_list[0]}/album/{album_id}"
                        )
                        title = extract_title_from_html(html_content)
                        return (
                            False,
                            f"解析漫画信息失败，网站结构可能已更改，但找到了标题: {title}",
                        )
                    except Exception as parse_e:
                        return False, f"解析漫画信息失败: {str(parse_e)}"

                return False, f"获取漫画详情失败: {error_msg}"

            first_photo = album[0]
            photo = self.client.get_photo_detail(first_photo.photo_id, True)
            if not photo:
                return False, "章节内容为空"

            image = photo[0]

            # 使用独立的封面目录保存封面
            cover_path = os.path.join(
                self.storage.dirs.get("covers"), f"{album_id}.jpg"
            )

            # 删除可能存在的旧封面，强制更新
            if os.path.exists(cover_path):
                try:
                    os.remove(cover_path)
                    logger.info(f"已删除旧封面: {cover_path}")
                except Exception as e:
                    logger.error(f"删除旧封面失败: {str(e)}")

            # 创建漫画文件夹 - 仍然需要创建这个目录，因为下载漫画时会用到
            comic_folder = self.get_comic_folder(album_id)
            os.makedirs(comic_folder, exist_ok=True)

            # 下载封面到封面专用目录
            logger.info(f"下载封面到: {cover_path}")
            self.client.download_by_image_detail(image, cover_path)

            # 验证封面是否已下载
            if os.path.exists(cover_path):
                file_size = os.path.getsize(cover_path)
                logger.info(f"封面下载成功: {cover_path}, 大小: {file_size} 字节")
                if file_size < 1000:  # 如果文件太小，可能下载失败
                    logger.warning(f"封面文件大小异常，可能下载失败: {file_size} 字节")
            else:
                logger.error(f"封面下载后未找到文件: {cover_path}")

            return True, cover_path
        except Exception as e:
            error_msg = str(e)
            logger.error(f"封面下载失败: {error_msg}")

            if "文本没有匹配上字段" in error_msg:
                return (
                    False,
                    "封面下载失败: 网站结构可能已更改，请更新jmcomic库或使用/jmdomain更新域名",
                )

            return False, f"封面下载失败: {error_msg}"
        finally:
            self.downloading_covers.discard(album_id)

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
        # 简化版：直接调用库
        jmcomic.download_album(comic_id, self.option)

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

    def search_author_works(self, author_name: str, limit: int = 5) -> Tuple[int, List[Tuple[str, str]]]:
        """搜索作者作品，支持自动翻页直到满足 limit 数量"""
        if not self.client: self.login()

        all_results = []
        total_count = 0
        current_page = 1

        try:
            logger.info(f"正在搜索作者: {author_name}, 目标数量: {limit}")
            while len(all_results) < limit:
                # 使用 ORDER_BY_LATEST 确保按最新排序
                resp = self.client.search_site(
                    search_query=author_name,
                    page=current_page,
                    order_by=JmMagicConstants.ORDER_BY_LATEST
                )

                if current_page == 1:
                    total_count = resp.total
                    if total_count == 0:
                        break

                page_results = list(resp.iter_id_title())
                if not page_results:
                    break

                all_results.extend(page_results)

                # 如果已经获取了所有存在的作品，停止翻页
                if len(all_results) >= total_count:
                    break

                current_page += 1

            return total_count, all_results[:limit]
        except Exception as e:
            logger.error(f"搜索作者失败: {e}")
            return 0, []

    def find_comic_folder(self, comic_id: str) -> str:
        """查找漫画文件夹，支持多种命名方式"""
        logger.info(f"开始查找漫画ID {comic_id} 的文件夹")

        # 尝试直接匹配ID
        id_path = os.path.join(self.storage.dirs.get("downloads"), str(comic_id))
        if os.path.exists(id_path):
            logger.info(f"找到直接匹配的目录: {id_path}")
            return id_path

        # 尝试查找以漫画标题命名的目录
        if os.path.exists(self.storage.dirs.get("downloads")):
            # 首先尝试查找以ID开头或结尾的目录名，或者格式为 [ID]_title 的目录
            exact_matches = []
            partial_matches = []

            for item in os.listdir(self.storage.dirs.get("downloads")):
                item_path = os.path.join(self.storage.dirs.get("downloads"), item)
                if not os.path.isdir(item_path):
                    continue

                # 精确匹配：目录名以ID开头或结尾，或者格式为 [ID]_title
                if (
                    item.startswith(str(comic_id) + "_")
                    or item.endswith("_" + str(comic_id))
                    or item.startswith("[" + str(comic_id) + "]")
                    or item == str(comic_id)
                ):
                    exact_matches.append(item_path)
                    logger.info(f"找到精确匹配的漫画目录: {item_path}")
                # 部分匹配：目录名包含ID但不是精确格式
                elif str(comic_id) in item:
                    # 进一步验证：确保是完整的ID匹配，而不是部分匹配
                    # 使用正则表达式确保ID是独立的数字
                    import re

                    pattern = r"\b" + re.escape(str(comic_id)) + r"\b"
                    if re.search(pattern, item):
                        partial_matches.append(item_path)
                        logger.info(f"找到部分匹配的漫画目录: {item_path}")

            # 优先返回精确匹配
            if exact_matches:
                logger.info(f"找到精确匹配，返回: {exact_matches[0]}")
                return exact_matches[0]
            elif partial_matches:
                logger.info(f"找到部分匹配，返回: {partial_matches[0]}")
                return partial_matches[0]

        # 默认返回downloads目录下的ID路径
        default_path = os.path.join(self.storage.dirs.get("downloads"), str(comic_id))
        logger.info(f"未找到现有目录，返回默认路径: {default_path}")
        return default_path

    def get_comic_folder(self, comic_id: str) -> str:
        """获取漫画文件夹路径"""
        return self.find_comic_folder(comic_id)