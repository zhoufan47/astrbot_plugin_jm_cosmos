import os
import shutil
import time
from datetime import datetime
from typing import List, Tuple
from astrbot.api.star import StarTools
from astrbot.api import logger


class StorageManager:
    def __init__(self, plugin_name: str):
        self.base_dir = StarTools.get_data_dir(plugin_name)
        self.dirs = {
            "downloads": os.path.join(self.base_dir, "downloads"),
            "pdfs": os.path.join(self.base_dir, "pdfs"),
            "logs": os.path.join(self.base_dir, "logs"),
            "covers": os.path.join(self.base_dir, "covers"),
            "temp": os.path.join(self.base_dir, "temp"),
        }
        self._init_dirs()
        self.max_storage_size = 8 * 1024 * 1024 * 1024  # 8GB (原代码是2GB，这里调整看需求)

    def _init_dirs(self):
        for path in self.dirs.values():
            os.makedirs(path, exist_ok=True)

    def get_path(self, key: str, filename: str) -> str:
        """获取特定类别下的文件绝对路径"""
        return os.path.join(self.dirs[key], filename)

    def get_cover_path(self, comic_id: str) -> str:
        return self.get_path("covers", f"{comic_id}.jpg")

    def get_pdf_path(self, comic_id: str) -> str:
        return self.get_path("pdfs", f"{comic_id}.pdf")

    def get_download_dir(self, comic_id: str) -> str:
        # 简化原有的复杂查找逻辑，推荐统一管理
        # 这里保留简单逻辑，直接返回 ID 目录
        return os.path.join(self.dirs["downloads"], str(comic_id))

    def clear_covers(self) -> int:
        count = 0
        for f in os.listdir(self.dirs["covers"]):
            try:
                os.remove(os.path.join(self.dirs["covers"], f))
                count += 1
            except Exception:
                pass
        return count

    def check_space(self) -> Tuple[bool, float]:
        """返回 (是否有空间, 已用空间MB)"""
        total_size = 0
        for root, _, files in os.walk(self.base_dir):
            for f in files:
                total_size += os.path.getsize(os.path.join(root, f))

        return total_size < self.max_storage_size, total_size / (1024 * 1024)

    def save_debug_log(self, prefix: str, content: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.get_path("logs", f"{prefix}_{timestamp}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path