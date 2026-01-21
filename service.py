import asyncio
import os
import opencc
from typing import Optional, List, Tuple
from astrbot.api import logger

from .config import PluginConfig
from .models import ComicInfo
from .storage import StorageManager
from .provider import JMProvider
from .database import DBManager  # 复用您原有的数据库模块


class JMCosmosService:
    def __init__(self, config: PluginConfig, plugin_name: str, db_path: str):
        self.config = config
        self.storage = StorageManager(plugin_name)
        self.provider = JMProvider(config, self.storage)
        self.db = DBManager(db_path)  # 假设 DBManager 接受路径

        # OpenCC converter
        self.cc = opencc.OpenCC('t2s.json')

        # 初始化登录
        self.provider.login()

    def convert_text(self, text: str) -> str:
        return self.cc.convert(text)

    async def get_comic_info(self, comic_id: str) -> Tuple[Optional[ComicInfo], Optional[str]]:
        """获取漫画信息和封面路径"""
        # 1. 获取详情 - 使用 asyncio.to_thread 包装同步操作
        info = await asyncio.to_thread(self.provider.get_comic_detail, comic_id)
        if not info:
            return None,None

        # 2. 简繁转换
        info.title = self.convert_text(info.title)
        info.tags = [self.convert_text(t) for t in info.tags]

        # 3. 尝试下载封面 - 使用 asyncio.to_thread 包装同步操作
        logger.info(f"正在下载漫画封面: {comic_id}")
        has_cover,cover_path = await asyncio.to_thread(self.provider.download_cover, comic_id)
        info.cover_path = cover_path

        # 4. 入库 (业务逻辑的一部分) - 使用 asyncio.to_thread 包装同步操作
        if not await asyncio.to_thread(self.db.is_comic_exists, comic_id):
            await asyncio.to_thread(self.db.add_comic, comic_id, info.title, ','.join(info.tags))
        if not has_cover:
            cover_path = None
        return info,cover_path

    async def download_comic(self, comic_id: str, user_id: str, user_name: str) -> str:
        """处理完整的下载业务流程"""
        # 1. 检查黑名单
        comic = await asyncio.to_thread(self.db.get_comic_by_id, comic_id)
        if comic and str(comic.IsBacklist) == '1':
            return "❌ 该漫画已在黑名单中"

        # 2. 记录用户信息
        if not await asyncio.to_thread(self.db.get_user_by_id, user_id):
            await asyncio.to_thread(self.db.add_user, user_id, user_name)

        # 3. 检查存储空间
        has_space, _ = await asyncio.to_thread(self.storage.check_space)
        if not has_space:
            return "❌ 磁盘空间不足，请联系管理员清理"

        # 4. 执行下载
        success, msg = await self.provider.download_comic_async(comic_id)
        if not success:
            return f"❌ 下载失败: {msg}"

        # 5. 记录下载历史
        await asyncio.to_thread(self.db.insert_download, user_id, comic_id)
        await asyncio.to_thread(self.db.add_comic_download_count, comic_id)

        # 6. 检查 PDF
        pdf_path = self.storage.get_pdf_path(comic_id)
        if os.path.exists(pdf_path):
            return f"✅ 下载完成"
        else:
            return "⚠️ 下载似乎完成了，但未找到生成的 PDF 文件"

    async def get_pdf_file(self, comic_id: str) -> Optional[str]:
        path = await asyncio.to_thread(self.storage.get_pdf_path, comic_id)
        return path if await asyncio.to_thread(os.path.exists, path) else None

    async def shutdown(self):
        await asyncio.to_thread(self.provider.close)