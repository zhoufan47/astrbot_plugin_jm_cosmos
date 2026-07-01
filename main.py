import asyncio
import os
import time
import subprocess
import sys

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.message.message_event_result import MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, Image, File, At
from astrbot.api import logger

from .thirdpartyapi import discordPoster
from .config import PluginConfig
from .service import JMCosmosService


@register(
    "jm_cosmos",
    "zhoufan47",
    "全能型JM漫画下载与管理工具 (Refactored)",
    "1.10.0",
    "https://github.com/zhoufan47/astrbot_plugin_jm_cosmos",
)
class JMCosmosPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)

        # 1. 加载配置
        self.service = None
        self.cfg = PluginConfig.from_dict(config)

        # 2. 初始化业务服务
        self.db_path = os.path.join(
            self.context.get_config().get("data_dir", "data"),
            "db", "jm_cosmos.db"
        )
        self._report_template = ""
        logger.info(f"JMCosmos Refactored Loaded. Debug={self.cfg.debug_mode}")

    async def initialize(self):
        try:
            await asyncio.to_thread(time.sleep, 2)
            self.service = await asyncio.to_thread(JMCosmosService, self.cfg, "jm_cosmos", self.db_path)

            # 加载性癖调查HTML模板
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'investigation_report.html')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    self._report_template = f.read()
                self.service.report_template = self._report_template
                logger.info(f"性癖调查模板已加载: {template_path}")
            else:
                logger.warning(f"性癖调查模板文件不存在: {template_path}")

            logger.info("JmCosmos 异步初始化完成……")
        except Exception as e:
            logger.error(f"JmCosmos 异步初始化失败{e}")

    async def terminate(self):
        """插件卸载时调用"""
        await self.service.shutdown()

    @filter.command("jm")
    async def cmd_download(self, event: AstrMessageEvent,comic_id:str):
        """下载漫画: /jm [ID]"""
        sender_id = event.get_sender_id()
        sender_name = event.get_sender_name()

        # 发送"开始下载"的提示
        yield event.plain_result(f"⏳ 开始请求下载 [{comic_id}]...")
        count = self.service.db.get_comic_download_count(comic_id)
        if count > 0:
            last_download_user_id = self.service.db.get_last_download_user(comic_id)
            first_download_user_id = self.service.db.get_first_download_user(comic_id)
            last_user = self.service.db.get_user_by_id(last_download_user_id)
            first_user = self.service.db.get_user_by_id(first_download_user_id)
            try:
                yield event.plain_result(
                    f"漫画[{comic_id}]已经被下载了 {count} 次，首次下载用户是 {first_user.UserName} ,上一次下载用户是 {last_user.UserName} ")
            except Exception as e:
                logger.error(f"获取用户信息失败: {e}")
        else:
            yield event.plain_result(f"漫画[{comic_id}]是第一次下载,你发现了新大陆！")
        # 调用业务层
        result_msg = await self.service.download_comic(comic_id, sender_id, sender_name)
        yield event.plain_result(result_msg)

        # 如果成功，尝试发送文件
        if "✅" in result_msg:
            pdf_path = await self.service.get_pdf_file(comic_id)
            logger.info(f"已生成文件 [{pdf_path}]")
            # 2. 获取漫画详情 (用于 Discord 推送信息)
            info, cover_path = await self.service.get_comic_info(comic_id)
            if info and "yaoi" in info.tags:
                yield event.plain_result(f"‼警告‼：检测到[{comic_id}]含有[yaoi]标签！这是黑车！")
            # 3. 推送到 Discord
            if info and pdf_path:
                try:
                    # 构造 info 消息列表 (discordPoster通常接收一个组件列表或字符串)
                    if self.cfg.is_discord_post:
                        await discordPoster.post_to_discord(
                            comic_id,
                            f"{info.id}-{info.title}",
                            info.to_display_string(),
                            info.tags,
                            cover_path if cover_path else "",  # 确保不传 None
                            pdf_path,
                            api_url=self.cfg.discord_post_api_url
                        )
                        logger.info(f"已推送漫画 [{comic_id}] 到 Discord")
                except Exception as e:
                    logger.error(f"推送到 Discord 失败: {e}")
            if pdf_path:
                file_size_mb = await asyncio.to_thread(os.path.getsize, pdf_path) / (1024 * 1024)
                if file_size_mb > 90:
                    yield event.plain_result(f"⚠️ 文件较大 ({file_size_mb:.2f}MB)，可能发送失败。")

                # 直接发送文件组件，AstrBot 会自动处理适配器逻辑
                yield event.chain_result([File(name=f"{comic_id}.pdf", file=pdf_path)])


    @filter.llm_tool(name="download_comic")
    async def tool_download(self, event: AstrMessageEvent,comic_id:str)-> MessageEventResult:
        '''下载本子（漫画）

        Args:
            comic_id(string): 本子ID、漫画ID
        '''
        sender_id = event.get_sender_id()
        sender_name = event.get_sender_name()

        # 发送"开始下载"的提示
        yield event.plain_result(f"⏳ 开始请求下载 [{comic_id}]...")
        count = self.service.db.get_comic_download_count(comic_id)
        if count > 0:
            last_download_user_id = self.service.db.get_last_download_user(comic_id)
            first_download_user_id = self.service.db.get_first_download_user(comic_id)
            last_user = self.service.db.get_user_by_id(last_download_user_id)
            first_user = self.service.db.get_user_by_id(first_download_user_id)
            try:
                yield event.plain_result(
                    f"漫画[{comic_id}]已经被下载了 {count} 次，首次下载用户是 {first_user.UserName} ,上一次下载用户是 {last_user.UserName} ")
            except Exception as e:
                logger.error(f"获取用户信息失败: {e}")
        else:
            yield event.plain_result(f"漫画[{comic_id}]是第一次下载,你发现了新大陆！")
        # 调用业务层
        result_msg = await self.service.download_comic(comic_id, sender_id, sender_name)
        yield event.plain_result(result_msg)

        # 如果成功，尝试发送文件
        if "✅" in result_msg:
            pdf_path = await self.service.get_pdf_file(comic_id)
            logger.info(f"已生成文件 [{pdf_path}]")
            # 2. 获取漫画详情 (用于 Discord 推送信息)
            info, cover_path = await self.service.get_comic_info(comic_id)


            # 3. 推送到 Discord
            if info and pdf_path:
                try:
                    # 构造 info 消息列表 (discordPoster通常接收一个组件列表或字符串)
                    if self.cfg.is_discord_post:
                        await discordPoster.post_to_discord(
                            comic_id,
                            f"{info.id}-{info.title}",
                            info.to_display_string(),
                            info.tags,
                            cover_path if cover_path else "",  # 确保不传 None
                            pdf_path,
                            api_url=self.cfg.discord_post_api_url
                        )
                        logger.info(f"已推送漫画 [{comic_id}] 到 Discord")
                except Exception as e:
                    logger.error(f"推送到 Discord 失败: {e}")
            if pdf_path:
                file_size_mb = await asyncio.to_thread(os.path.getsize, pdf_path) / (1024 * 1024)
                if file_size_mb > 90:
                    yield event.plain_result(f"⚠️ 文件较大 ({file_size_mb:.2f}MB)，可能发送失败。")

                # 直接发送文件组件，AstrBot 会自动处理适配器逻辑
                yield event.chain_result([File(name=f"{comic_id}.pdf", file=pdf_path)])


    @filter.command("xp大调查")
    async def cmd_investigate(self, event: AstrMessageEvent):
        """调查指定用户的性癖: /jm大调查 @用户"""
        # 从消息中提取@的用户ID
        target_user_id = None
        for comp in event.message_obj.message:
            if isinstance(comp, At) and comp.qq != 'all':
                target_user_id = str(comp.qq)
                break

        if not target_user_id:
            yield event.plain_result("❌ 请@一个用户，例如: /jm大调查 @小明")
            return

        yield event.plain_result(f"🔍 正在调查用户 [{target_user_id}] 的性癖，请稍候...")

        # 获取LLM provider：优先使用配置指定的，否则使用当前默认模型
        llm_provider = self.context.get_provider_by_id(
            self.cfg.llm_provider_id) or self.context.get_using_provider()

        if not llm_provider:
            yield event.plain_result("❌ 未配置用于文本生成任务的 LLM 提供商。")
            return

        report_image_path, report_text = await self.service.investigate_user(
            target_user_id, llm_provider=llm_provider
        )

        if not report_image_path:
            yield event.plain_result(report_text)
            return

        # 先发送文字报告
        yield event.plain_result(report_text)

        # 再发送报告图片（如果生成成功）
        yield event.chain_result(report_image_path)

    @filter.command("jminfo")
    async def cmd_info(self, event: AstrMessageEvent,comic_id:str):
        """查看详情: /jminfo [ID]"""
        info, cover_path = await self.service.get_comic_info(comic_id)

        if not info:
            yield event.plain_result(f"❌ 无法获取漫画 [{comic_id}] 的信息")
            return

        components = []
        yield event.plain_result(info.to_display_string())
        count = self.service.db.get_comic_download_count(comic_id)
        if count > 0:
            last_download_user_id = self.service.db.get_last_download_user(comic_id)
            first_download_user_id = self.service.db.get_first_download_user(comic_id)
            last_user = self.service.db.get_user_by_id(last_download_user_id)
            first_user = self.service.db.get_user_by_id(first_download_user_id)
            try:
                yield event.plain_result(
                    f"漫画[{comic_id}]已经被下载了 {count} 次，首次下载用户是 {first_user.UserName} ,上一次下载用户是 {last_user.UserName} ")
            except Exception as e:
                logger.error(f"获取用户信息失败: {e}")
        if self.cfg.show_cover and cover_path:
            logger.info(f"已获取漫画的封面 [{cover_path}] 的信息")
            components.append(Image.fromFileSystem(cover_path))
        yield event.chain_result(components)

    @filter.command("jmpassword")
    async def jmpassword(self, event: AstrMessageEvent):
        current_password = self.cfg.pdf_password
        yield event.plain_result(f"当前密码【{current_password}】")

    @filter.llm_tool("jmpassword")
    async def tool_history(self, event: AstrMessageEvent)->MessageEventResult:
        '''查询当前本子的密码

        '''
        current_password = self.cfg.pdf_password
        yield event.plain_result(f"当前密码【{current_password}】")


    @filter.command("jmsearch")
    async def cmd_search(self, event: AstrMessageEvent):
        """搜索: /jmsearch [关键词]"""
        args = event.message_str.strip().split()
        if len(args) < 2:
            return

        query = args[1]
        # 直接调用 Provider 的搜索 (或者封装在 Service 中) - 使用 asyncio.to_thread 包装同步操作
        results = await asyncio.to_thread(self.service.provider.search_site, query)

        if not results:
            yield event.plain_result("未找到相关结果。")
            return

        msg = ["🔍 搜索结果 (前10条):"]
        for cid, title in results[:10]:
            msg.append(f"• {cid}: {title}")

        yield event.plain_result("\n".join(msg))

    @filter.command("jmlogin")
    async def cmd_login(self, event: AstrMessageEvent):
        """登录JM帐号: /jmlogin [用户名] [密码] (不带参数则使用配置)"""
        args = event.message_str.strip().split()

        # 默认使用配置中的账号密码
        username = self.cfg.jm_username
        password = self.cfg.jm_passwd

        # 如果指令提供了参数，则更新
        if len(args) >= 3:
            username = args[1]
            password = args[2]
            # 更新内存中的配置，确保 Service 层调用 Provider 时能拿到新密码
            self.cfg.jm_username = username
            self.cfg.jm_passwd = password
            self.cfg.is_jm_login = True

        if not username or not password:
            yield event.plain_result("❌ 未提供账号密码，且配置文件中未设置。\n用法: /jmlogin [用户名] [密码]")
            return

        yield event.plain_result(f"⏳ 正在尝试登录: {username}...")

        try:
            # 调用 Service 层持有的 Provider 进行登录
            # Provider.login() 方法会读取 self.cfg 中的最新凭证
            if await asyncio.to_thread(self.service.provider.login):
                yield event.plain_result(f"✅ 登录成功！Cookies 已更新。")
            else:
                yield event.plain_result(f"❌ 登录失败，请检查账号密码或网络连通性。")
        except Exception as e:
            logger.error(f"登录异常: {e}")
            yield event.plain_result(f"❌ 登录过程发生异常: {e}")

    @filter.command("jmstat")
    async def statistics(self, event: AstrMessageEvent):
        """查询统计信息

        用法:
        /jmstat 最多下载用户
        /jmstat 最多下载漫画
        /jmstat 妹控
        /jmstat NTR之王
        /jmstat 最爱开大车
        /jmstat 骨科
        /jmstat 炼铜
        """

        args = event.message_str.strip().split()
        if len(args) < 2:
            yield event.plain_result(
                "用法:\n/jmstat 最多下载用户\n "
                "/jmstat 最多下载漫画\n"
                "/jmstat 妹控\n"
                "/jmstat NTR之王\n"
                "/jmstat 最爱开大车\n"
                "/jmstat 骨科\n"
                "/jmstat 炼铜\n"
                "/jmstat 自定义 [自定义TAG]"
            )
            return
        action = args[1].lower()
        if action == "最多下载用户":
            logger.info("查询最多下载用户")
            user_id = await asyncio.to_thread(self.service.db.query_most_download_user)
            logger.info(f"查询到用户ID: {user_id}")
            user = await asyncio.to_thread(self.service.db.get_user_by_id, user_id)
            yield event.plain_result(f"噔噔噔！⭐️截止今天，最多下载用户是{user.UserName}[{user.UserId}]")
        elif action == "最多下载漫画":
            comic_id = await asyncio.to_thread(self.service.db.query_most_download_comic)
            yield event.plain_result(f"噔噔噔！⭐️截止今天，下载最多次数的漫画是{comic_id}]")
        elif action == "妹控":
            user_id = await asyncio.to_thread(self.service.db.get_most_download_user_id_by_tag, "兄妹")
            if user_id is None:
                yield event.plain_result(f"哎呀！没有找到【妹控】指数最高的用户");
                return
            user = await asyncio.to_thread(self.service.db.get_user_by_id, user_id)
            yield event.plain_result(f"噔噔噔！⭐️截止今天，【妹控】指数最高的用户是{user.UserName}[{user.UserId}]")
        elif action == "NTR之王":
            user_id = await asyncio.to_thread(self.service.db.get_most_download_user_id_by_tag, "NTR")
            if user_id is None:
                yield event.plain_result(f"哎呀！没有找到【NTR】指数最高的用户");
                return
            user = await asyncio.to_thread(self.service.db.get_user_by_id, user_id)
            yield event.plain_result(f"噔噔噔！⭐️截止今天，【NTR】指数最高的用户是{user.UserName}[{user.UserId}]")
        elif action == "最爱开大车":
            user_id = await asyncio.to_thread(self.service.db.get_most_download_user_id_by_tag, "年上")
            if user_id is None:
                yield event.plain_result(f"哎呀！没有找到【最爱开大车】指数最高的用户")
                return
            user = await asyncio.to_thread(self.service.db.get_user_by_id, user_id)
            yield event.plain_result(f"噔噔噔！⭐️截止今天，【最爱开大车】指数最高的用户是{user.UserName}[{user.UserId}]")
        elif action == "骨科":
            user_id = await asyncio.to_thread(self.service.db.get_most_download_user_id_by_tag, "乱伦")
            if user_id is None:
                yield event.plain_result(f"哎呀！没有找到【骨科】指数最高的用户")
                return
            user = await asyncio.to_thread(self.service.db.get_user_by_id, user_id)
            yield event.plain_result(f"噔噔噔！⭐️截止今天，【骨科】指数最高的用户是{user.UserName}[{user.UserId}]")
        elif action == "炼铜":
            user_id = await asyncio.to_thread(self.service.db.get_most_download_user_id_by_tag, "萝莉")
            if user_id is None:
                yield event.plain_result(f"哎呀！没有找到【炼铜】指数最高的用户")
                return
            user = await asyncio.to_thread(self.service.db.get_user_by_id, user_id)
            yield event.plain_result(f"噔噔噔！⭐️截止今天，【炼铜】指数最高的用户是{user.UserName}[{user.UserId}]")
        elif action == "自定义":
            custom_tag = args[2]
            user_id = await asyncio.to_thread(self.service.db.get_most_download_user_id_by_tag, custom_tag)
            if user_id is None:
                yield event.plain_result(f"哎呀！没有找到【{custom_tag}】指数最高的用户")
                return
            user = await asyncio.to_thread(self.service.db.get_user_by_id, user_id)
            yield event.plain_result(f"噔噔噔！⭐️截止今天，【{custom_tag}】指数最高的用户是{user.UserName}[{user.UserId}]")
        else:
            yield event.plain_result(
                "用法:\n/jmstat 最多下载用户\n "
                "/jmstat 最多下载漫画\n"
                "/jmstat 妹控\n"
                "/jmstat NTR之王\n"
                "/jmstat 最爱开大车\n"
                "/jmstat 骨科\n"
                "/jmstat 炼铜\n"
                "/jmstat 自定义 [自定义TAG]"
            )

    @filter.command("jmauthor")
    async def cmd_author(self, event: AstrMessageEvent):
        """搜索作者作品: /jmauthor [作者名] [数量]"""
        parts = event.message_str.strip().split()
        if len(parts) < 3:
            yield event.plain_result("用法: /jmauthor [作者名] [数量]\n例如: /jmauthor 水龙敬 5")
            return

        # 解析参数：因为作者名中间可能有空格，取中间部分为作者名，最后一部分为数量
        try:
            order = int(parts[-1])
            author_name = " ".join(parts[1:-1])
        except ValueError:
            yield event.plain_result("❌ 数量必须是数字。")
            return

        if order < 1: order = 1

        yield event.plain_result(f"🔍 正在搜索作者 '{author_name}' 的前 {order} 部作品...")

        # 调用 Provider 获取列表 - 使用 asyncio.to_thread 包装同步操作
        total, results = await asyncio.to_thread(self.service.provider.search_author_works, author_name, order)

        if total == 0:
            yield event.plain_result(f"❌ 未找到作者 '{author_name}' 的作品。")
            return

        # 逻辑：如果只请求 1 部，显示详细图文信息
        if order == 1 and results:
            comic_id = results[0][0]
            # 复用 Service 的获取详情逻辑
            info, cover_path = await self.service.get_comic_info(comic_id)
            if info:
                components = [Plain(f"🎨 作者 {author_name} 的最新作品:\n\n" + info.to_display_string())]
                if self.cfg.show_cover and cover_path:
                    components.append(Image.fromFileSystem(cover_path))
                yield event.chain_result(components)
                return

        # 逻辑：如果请求多部，显示列表
        msg_lines = [f"🎨 作者 {author_name} 共有 {total} 部作品 (显示前 {len(results)} 部):"]
        for i, (cid, title) in enumerate(results):
            msg_lines.append(f"{i + 1}. 🆔{cid}: {title}")

        yield event.plain_result("\n".join(msg_lines))

    @filter.command("jmblackin")
    async def cmd_black_in(self, event: AstrMessageEvent, comic_id:str):
        """加入黑名单: /jmblackin [ID]"""
        await asyncio.to_thread(self.service.db.update_comic_is_backlist, comic_id=comic_id,is_backlist="1")
        yield event.plain_result(f"✅ 已将漫画 [{comic_id}] 加入黑名单")


    @filter.command("jmblackout")
    async def cmd_black_out(self, event: AstrMessageEvent, comic_id:str):
        """加入黑名单: /jmblackout [ID]"""
        await asyncio.to_thread(self.service.db.update_comic_is_backlist, comic_id=comic_id,is_backlist="0")
        yield event.plain_result(f"✅ 已将漫画 [{comic_id}] 移出黑名单")

    @filter.command("jmhis")
    async def cmd_history(self, event: AstrMessageEvent):
        """查询下载历史: /jmhis [ID]"""
        args = event.message_str.strip().split()
        if len(args) < 2:
            yield event.plain_result("请提供漫画ID，例如：/jmhis 12345")
            return

        comic_id = args[1]
        
        # 查询下载历史
        history_records = await asyncio.to_thread(
            self.service.db.get_download_history_by_comic, comic_id
        )
        
        if not history_records:
            yield event.plain_result(f"❌ 没有找到漫画 [{comic_id}] 的下载历史记录")
            return
        
        # 格式化输出
        msg_lines = [f"📚 漫画 [{comic_id}] 的下载历史 (共{len(history_records)}条):\n"]
        for user_name, download_time in history_records:
            # 如果用户名为空或None，显示为匿名用户
            user_display = user_name if user_name else "匿名用户"
            msg_lines.append(f"• {user_display} - {download_time}")
        
        yield event.plain_result("\n".join(msg_lines))


    @filter.command("jmupdate")
    async def cmd_update_jmcomic(self, event: AstrMessageEvent):
        """强制更新jmcomic到最新版本: /jmupdate"""
        yield event.plain_result("⏳ 正在检查并更新 jmcomic 库...")
        
        try:
            # 使用 pip 安装最新版本的 jmcomic
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-m", "pip", "install", "--upgrade", "jmcomic"],
                capture_output=True,
                text=True,
                timeout=120  # 设置超时时间为120秒
            )
            
            if result.returncode == 0:
                # 获取安装的版本信息
                version_result = await asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, "-m", "pip", "show", "jmcomic"],
                    capture_output=True,
                    text=True
                )
                
                version_info = "未知版本"
                for line in version_result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        version_info = line.split(':', 1)[1].strip()
                        break
                
                yield event.plain_result(f"✅ jmcomic 已成功更新至最新版本: {version_info}")
                logger.info(f"jmcomic 已更新至版本: {version_info}")
            else:
                error_msg = result.stderr if result.stderr else "未知错误"
                yield event.plain_result(f"❌ 更新 jmcomic 失败: {error_msg}")
                logger.error(f"更新 jmcomic 失败: {error_msg}")
                
        except subprocess.TimeoutExpired:
            yield event.plain_result("❌ 更新操作超时，请稍后重试")
            logger.error("更新 jmcomic 超时")
        except Exception as e:
            yield event.plain_result(f"❌ 更新过程中发生异常: {str(e)}")
            logger.error(f"更新 jmcomic 时发生异常: {e}")

    @filter.llm_tool("jmhis")
    async def tool_history(self, event: AstrMessageEvent, comic_id:str)->MessageEventResult:
        '''查询漫画的下载历史

        Args:
            comic_id(string): 漫画id
        '''
        """查询下载历史: /jmhis [ID]"""
        # 查询下载历史
        history_records = await asyncio.to_thread(
            self.service.db.get_download_history_by_comic, comic_id
        )

        if not history_records:
            yield event.plain_result(f"❌ 没有找到漫画 [{comic_id}] 的下载历史记录")
            return

        # 格式化输出
        msg_lines = [f"📚 漫画 [{comic_id}] 的下载历史 (共{len(history_records)}条):\n"]
        for user_name, download_time in history_records:
            # 如果用户名为空或None，显示为匿名用户
            user_display = user_name if user_name else "匿名用户"
            msg_lines.append(f"• {user_display} - {download_time}")
        yield event.plain_result("\n".join(msg_lines))