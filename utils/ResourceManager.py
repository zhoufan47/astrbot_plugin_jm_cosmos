
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger

import os
import yaml
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional, Any

import time

import jmcomic

class ResourceManager:
    """资源管理器，管理文件路径和创建必要的目录"""

    def __init__(self, plugin_name: str):
        # 使用StarTools获取数据目录
        self.base_dir = StarTools.get_data_dir(plugin_name)

        # 目录结构
        self.downloads_dir = os.path.join(self.base_dir, "downloads")
        self.pdfs_dir = os.path.join(self.base_dir, "pdfs")
        self.logs_dir = os.path.join(self.base_dir, "logs")
        self.temp_dir = os.path.join(self.base_dir, "temp")
        # 添加专门的封面目录
        self.covers_dir = os.path.join(self.base_dir, "covers")

        # 存储管理配置
        self.max_storage_size = 2 * 1024 * 1024 * 1024  # 2GB限制
        self.max_file_age_days = 30  # 文件保留30天

        # 创建必要的目录
        for dir_path in [
            self.downloads_dir,
            self.pdfs_dir,
            self.logs_dir,
            self.temp_dir,
            self.covers_dir,
        ]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

    def check_storage_space(self) -> tuple[bool, int]:
        """检查存储空间使用情况"""
        total_size = 0
        try:
            for root, dirs, files in os.walk(self.base_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"计算存储空间时出错: {str(e)}")
            return False, 0

        return total_size < self.max_storage_size, total_size

    def cleanup_old_files(self) -> int:
        """清理超过指定天数的文件"""

        cutoff_time = time.time() - (self.max_file_age_days * 24 * 60 * 60)
        cleaned_count = 0

        try:
            for root, dirs, files in os.walk(self.base_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        if os.path.getmtime(file_path) < cutoff_time:
                            try:
                                os.remove(file_path)
                                cleaned_count += 1
                                logger.info(f"清理过期文件: {file_path}")
                            except Exception as e:
                                logger.error(f"删除文件失败 {file_path}: {str(e)}")
        except Exception as e:
            logger.error(f"清理文件时出错: {str(e)}")

        return cleaned_count

    def get_storage_info(self) -> dict:
        """获取存储信息"""
        has_space, total_size = self.check_storage_space()
        return {
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_size_mb": round(self.max_storage_size / (1024 * 1024), 2),
            "has_space": has_space,
            "usage_percent": round((total_size / self.max_storage_size) * 100, 2),
        }

    def find_comic_folder(self, comic_id: str) -> str:
        """查找漫画文件夹，支持多种命名方式"""
        logger.info(f"开始查找漫画ID {comic_id} 的文件夹")

        # 尝试直接匹配ID
        id_path = os.path.join(self.downloads_dir, str(comic_id))
        if os.path.exists(id_path):
            logger.info(f"找到直接匹配的目录: {id_path}")
            return id_path

        # 尝试查找以漫画标题命名的目录
        if os.path.exists(self.downloads_dir):
            # 首先尝试查找以ID开头或结尾的目录名，或者格式为 [ID]_title 的目录
            exact_matches = []
            partial_matches = []

            for item in os.listdir(self.downloads_dir):
                item_path = os.path.join(self.downloads_dir, item)
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
        default_path = os.path.join(self.downloads_dir, str(comic_id))
        logger.info(f"未找到现有目录，返回默认路径: {default_path}")
        return default_path

    def get_comic_folder(self, comic_id: str) -> str:
        """获取漫画文件夹路径"""
        return self.find_comic_folder(comic_id)

    def get_cover_path(self, comic_id: str) -> str:
        """获取封面图片路径"""
        # 始终返回封面目录中对应ID的封面路径
        cover_path = os.path.join(self.covers_dir, f"{comic_id}.jpg")

        # 如果封面已存在则返回
        if os.path.exists(cover_path):
            file_size = os.path.getsize(cover_path)
            if file_size > 1000:  # 有效文件大小
                return cover_path
            else:
                # 文件过小，可能是空文件或损坏文件，删除它
                try:
                    os.remove(cover_path)
                    logger.warning(
                        f"删除无效封面文件: {cover_path}, 大小: {file_size}字节"
                    )
                except Exception:
                    pass

        # 返回封面目录中的预期路径
        return cover_path

    def get_pdf_path(self, comic_id: str) -> str:
        """获取PDF文件路径"""
        return os.path.join(self.pdfs_dir, f"{comic_id}.pdf")

    def get_log_path(self, prefix: str) -> str:
        """获取日志文件路径"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.logs_dir, f"{prefix}_{timestamp}.txt")

    def list_comic_images(self, comic_id: str, limit: int = None) -> List[str]:
        """获取漫画图片列表"""
        comic_folder = self.get_comic_folder(comic_id)
        if not os.path.exists(comic_folder):
            logger.warning(f"漫画目录不存在: {comic_folder}")
            return []

        logger.info(f"正在查找漫画图片，目录: {comic_folder}")
        image_files = []

        # 遍历目录结构寻找图片
        try:
            # 首先直接检查主目录下的图片
            direct_images = [
                os.path.join(comic_folder, f)
                for f in os.listdir(comic_folder)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                and os.path.isfile(os.path.join(comic_folder, f))
            ]

            if direct_images:
                # 主目录下有图片，直接使用
                image_files.extend(sorted(direct_images))
                logger.info(f"在主目录下找到 {len(direct_images)} 张图片")
            else:
                # 检查所有子目录
                sub_folders = []
                for item in os.listdir(comic_folder):
                    item_path = os.path.join(comic_folder, item)
                    if os.path.isdir(item_path):
                        sub_folders.append(item_path)

                # 按照目录名排序，确保图片顺序正确
                sub_folders.sort()

                # 从每个子目录收集图片
                for folder in sub_folders:
                    folder_images = []
                    for img in os.listdir(folder):
                        if img.lower().endswith(
                            (".jpg", ".jpeg", ".png", ".webp")
                        ) and os.path.isfile(os.path.join(folder, img)):
                            folder_images.append(os.path.join(folder, img))

                    # 确保每个文件夹内的图片按名称排序
                    folder_images.sort()
                    image_files.extend(folder_images)

                logger.info(f"在子目录中找到 {len(image_files)} 张图片")
        except Exception as e:
            logger.error(f"列出漫画图片时出错: {str(e)}")

        if not image_files:
            logger.warning(f"未找到任何图片文件，请检查目录: {comic_folder}")

        # 应用限制并返回结果
        return image_files[:limit] if limit else image_files

    def clear_cover_cache(self):
        """清理封面缓存目录"""
        if os.path.exists(self.covers_dir):
            logger.info(f"开始清理封面缓存目录: {self.covers_dir}")
            try:
                # 先列出所有文件
                count = 0
                for file in os.listdir(self.covers_dir):
                    file_path = os.path.join(self.covers_dir, file)
                    if os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                            count += 1
                        except Exception as e:
                            logger.error(
                                f"删除封面缓存文件失败: {file_path}, 错误: {str(e)}"
                            )
                logger.info(f"封面缓存清理完成，共删除 {count} 个文件")
                return count
            except Exception as e:
                logger.error(f"清理封面缓存目录失败: {str(e)}")
                return 0
        return 0


class JMClientFactory:
    """JM客户端工厂，负责创建和管理JM客户端实例"""

    def __init__(self, config: CosmosConfig, resource_manager: ResourceManager):
        self.config = config
        self.resource_manager = resource_manager
        self.option = self._create_option()

    def _create_option(self):
        """创建JM客户端选项"""
        option_dict = {
            "client": {
                "impl": "html",
                "domain": self.config.domain_list,
                "retry_times": 5,
                "postman": {
                    "meta_data": {
                        "proxies": {"https": self.config.proxy}
                        if self.config.proxy
                        else None,
                        "cookies": {"AVS": self.config.avs_cookie},
                        # 添加浏览器模拟的请求头
                        "headers": {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                            "Referer": f"https://{self.config.domain_list[0]}/",
                            "Connection": "keep-alive",
                            "Cache-Control": "max-age=0",
                        },
                    }
                },
            },
            "download": {
                "cache": True,
                "image": {"decode": True, "suffix": ".jpg"},
                "threading": {
                    "image": self.config.max_threads,
                    "photo": self.config.max_threads,
                },
            },
            "dir_rule": {"base_dir": self.resource_manager.downloads_dir},
            "plugins": {
                "after_album": [
                    {
                        "plugin": "img2pdf",
                        "kwargs": {
                            "pdf_dir": self.resource_manager.pdfs_dir,
                            "filename_rule": "Aid",
                        },
                    }
                ]
            },
        }
        yaml_str = yaml.safe_dump(option_dict, allow_unicode=True)
        return jmcomic.create_option_by_str(yaml_str)

    def create_client(self):
        """创建JM客户端"""
        client = self.option.new_jm_client();
        logger.info(f"已登录到JM漫画网站: {client.get_cookies()}")
        return client

    def create_client_with_domain(self, domain: str):
        """创建使用特定域名的JM客户端"""
        custom_option = jmcomic.JmOption.default()
        custom_option.client.domain = [domain]
        custom_option.client.postman.meta_data = {
            "proxies": {"https": self.config.proxy} if self.config.proxy else None,
            "cookies": {"AVS": self.config.avs_cookie},
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": f"https://{domain}/",
            },
        }
        return custom_option.new_jm_client()

    def update_option(self):
        """更新JM客户端选项"""
        self.option = self._create_option()
