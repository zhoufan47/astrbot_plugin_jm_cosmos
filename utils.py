import os
import re
import time
import opencc
from astrbot.api.star import StarTools
from astrbot.api import logger



# --- 验证工具 ---
def validate_comic_id(comic_id: str) -> bool:
    return bool(re.match(r"^\d+$", comic_id)) and len(comic_id) <= 10


def validate_domain(domain: str) -> bool:
    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
    return bool(re.match(pattern, domain)) and len(domain) <= 253


def extract_title_from_html(html_content: str) -> str:
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
            return matches[0].strip()
    return "未知标题"


# --- 文本处理 ---
_converter = opencc.OpenCC('t2s.json')


def convert_t2s(text: str) -> str:
    return _converter.convert(text)


# --- 资源管理器 ---
class ResourceManager:
    """负责管理插件的所有文件路径和目录创建"""

    def __init__(self, plugin_name: str):
        self.base_dir = StarTools.get_data_dir(plugin_name)
        self.downloads_dir = os.path.join(self.base_dir, "downloads")
        self.pdfs_dir = os.path.join(self.base_dir, "pdfs")
        self.covers_dir = os.path.join(self.base_dir, "covers")
        self.logs_dir = os.path.join(self.base_dir, "logs")
        self.temp_dir = os.path.join(self.base_dir, "temp")
        self._init_dirs()

    def _init_dirs(self):
        for d in [self.downloads_dir, self.pdfs_dir, self.covers_dir, self.logs_dir, self.temp_dir]:
            os.makedirs(d, exist_ok=True)

    def get_pdf_path(self, comic_id: str) -> str:
        return os.path.join(self.pdfs_dir, f"{comic_id}.pdf")

    def get_cover_path(self, comic_id: str) -> str:
        return os.path.join(self.covers_dir, f"{comic_id}.jpg")

    def get_log_path(self, prefix: str) -> str:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.logs_dir, f"{prefix}_{timestamp}.txt")

    def find_comic_folder(self, comic_id: str) -> str:
        """复杂的目录查找逻辑"""
        # 1. 直接匹配
        direct_path = os.path.join(self.downloads_dir, str(comic_id))
        if os.path.exists(direct_path):
            return direct_path

        # 2. 模糊匹配
        if os.path.exists(self.downloads_dir):
            target_id = str(comic_id)
            for item in os.listdir(self.downloads_dir):
                item_path = os.path.join(self.downloads_dir, item)
                if not os.path.isdir(item_path):
                    continue

                # 精确匹配模式
                if (item.startswith(f"{target_id}_") or
                        item.endswith(f"_{target_id}") or
                        item == f"[{target_id}]"):
                    return item_path

                # 正则单词边界匹配
                if re.search(r"\b" + re.escape(target_id) + r"\b", item):
                    return item_path

        return direct_path

    def cleanup_old_files(self, days=30) -> int:
        cutoff = time.time() - (days * 86400)
        count = 0
        for root, _, files in os.walk(self.base_dir):
            for file in files:
                path = os.path.join(root, file)
                try:
                    if os.path.getmtime(path) < cutoff:
                        os.remove(path)
                        count += 1
                except Exception:
                    pass
        return count

    def check_storage_space(self, max_size_bytes=2 * 1024 * 1024 * 1024) -> bool:
        total_size = 0
        for root, _, files in os.walk(self.base_dir):
            for f in files:
                total_size += os.path.getsize(os.path.join(root, f))
        return total_size < max_size_bytes

    def clear_cover_cache(self) -> int:
        count = 0
        if os.path.exists(self.covers_dir):
            for f in os.listdir(self.covers_dir):
                try:
                    os.remove(os.path.join(self.covers_dir, f))
                    count += 1
                except:
                    pass
        return count