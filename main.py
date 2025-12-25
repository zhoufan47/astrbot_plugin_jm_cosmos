import os
import asyncio
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, Image, File
from astrbot.api import logger

# 导入拆分后的模块
from .config import CosmosConfig
from .utils import ResourceManager, validate_comic_id
from .service import JMService
from .models import DownloadStatus

# 导入原有的模块 (假设这些文件还在)
from .database import DBManager
from .thirdpartyapi import discordPoster


@register("jm_cosmos", "GEMILUXVII", "全能型JM漫画下载与管理工具", "1.1.0",
          "https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos")
class JMCosmosPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.plugin_name = "jm_cosmos"

        # 1. 资源与配置初始化
        self.rm = ResourceManager(self.plugin_name)

        # 兼容 AstrBot 配置系统与本地配置
        cfg_path = os.path.join(self.context.get_data_dir(), "config", f"astrbot_plugin_{self.plugin_name}_config.json")
        self.cfg = CosmosConfig.load(cfg_path)
        if config:
            # 如果 AstrBot 传入了配置，合并更新
            # 注意：config 是 dict，需要 update 到 pydantic model
            update_data = {k: v for k, v in config.items() if hasattr(self.cfg, k)}
            self.cfg = self.cfg.copy(update=update_data)

        # 2. 数据库初始化
        db_path = os.path.join(self.context.get_data_dir(), "db", "jm_cosmos.db")
        self.db_manager = DBManager(db_path)

        # 3. 核心服务初始化 (高内聚核心)
        self.service = JMService(self.cfg, self.rm)

        logger.info(f"JMCosmos Plugin Initialized. Domain: {self.cfg.domain_list[0]}")

    async def terminate(self):
        """插件卸载清理"""
        self.service.shutdown()

    @filter.command("jm")
    async def cmd_download(self, event: AstrMessageEvent, comic_id: str = None):
        """下载JM漫画并转换为PDF"""
        if not comic_id:
            yield event.plain_result("请提供漫画ID，例如：/jm 12345")
            return

        if not validate_comic_id(comic_id):
            yield event.plain_result("无效的ID格式")
            return

        # 数据库逻辑 (黑名单检查)
        comic = self.db_manager.get_comic_by_id(comic_id)
        if comic and str(comic.IsBacklist) == '1':
            yield event.plain_result(f"漫画[{comic_id}]在黑名单中。")
            return

        # 记录用户信息
        if not self.db_manager.get_user_by_id(event.get_sender_id()):
            self.db_manager.add_user(event.get_sender_id(), event.get_sender_name())
        self.db_manager.insert_download(event.get_sender_id(), comic_id)
        self.db_manager.add_comic_download_count(comic_id)

        yield event.plain_result(f"开始处理 {comic_id}...")

        # 1. 获取详情
        info, err = await self.service.get_comic_detail(comic_id)
        if info:
            # 特殊逻辑
            if event.get_sender_id() == "199946763":
                info.tags.append("萨摩耶")

            # 存入数据库
            if not self.db_manager.is_comic_exists(comic_id):
                self.db_manager.add_comic(comic_id, info.title, ','.join(info.tags[:5]))

        # 2. 执行下载
        result = await self.service.download_comic(comic_id)

        if not result.success:
            yield event.plain_result(f"下载失败: {result.message}")
            return

        # 3. 发送文件
        yield event.plain_result(f"{comic_id} 下载完成，正在发送...")

        try:
            # 使用 AstrBot 标准组件发送
            yield event.chain_result([
                Plain(f"文件生成成功: {os.path.basename(result.file_path)}"),
                File(name=f"{comic_id}.pdf", file=result.file_path)
            ])

            # 4. Discord 推送 (保持原有逻辑)
            if info:
                await discordPoster.post_to_discord(
                    comic_id,
                    f"{comic_id}-{info.title}",
                    Plain(info.to_summary_string()),  # 适配原有接口
                    info.tags,
                    info.cover_path,
                    result.file_path
                )
        except Exception as e:
            logger.error(f"发送文件失败: {e}")
            yield event.plain_result(f"发送失败，请检查日志。")

    @filter.command("jminfo")
    async def cmd_info(self, event: AstrMessageEvent, comic_id: str = None):
        """查询漫画详情"""
        if not comic_id or not validate_comic_id(comic_id):
            yield event.plain_result("ID无效")
            return

        info, err = await self.service.get_comic_detail(comic_id)
        if err:
            yield event.plain_result(f"查询失败: {err}")
            return

        components = [Plain(info.to_summary_string())]
        if self.cfg.show_cover and info.cover_path and os.path.exists(info.cover_path):
            components.append(Image.fromFileSystem(info.cover_path))

        yield event.chain_result(components)

    @filter.command("jmimg")
    async def cmd_preview(self, event: AstrMessageEvent, comic_id: str = None, pages: int = 3):
        """预览漫画前几页"""
        if not comic_id: return

        yield event.plain_result(f"正在获取预览 (前{pages}页)...")
        success, msg, paths = await self.service.get_preview_images(comic_id, int(pages))

        if not success:
            yield event.plain_result(f"预览失败: {msg}")
            return

        for path in paths:
            yield event.image_result(path)
            await asyncio.sleep(0.5)  # 避免刷屏

    @filter.command("jmconfig")
    async def cmd_config(self, event: AstrMessageEvent, key: str = None, val: str = None):
        """简单配置管理"""
        if not key:
            yield event.plain_result(f"当前配置:\nDomain: {self.cfg.domain_list}\nProxy: {self.cfg.proxy}")
            return

        # 实现简单的配置修改逻辑
        if key == "proxy":
            self.cfg.proxy = val if val != "clear" else None
        elif key == "domain":
            if val not in self.cfg.domain_list:
                self.cfg.domain_list.insert(0, val)

        # 保存并更新服务
        self.cfg.save(
            os.path.join(self.context.get_data_dir(), "config", f"astrbot_plugin_{self.plugin_name}_config.json"))
        self.service.update_client_config()
        yield event.plain_result("配置已更新")