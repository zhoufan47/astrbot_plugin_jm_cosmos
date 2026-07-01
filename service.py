import asyncio
import os
import json
import opencc
from collections import Counter
from typing import Optional, List, Tuple
from astrbot.api import logger, html_renderer

from .config import PluginConfig
from .models import ComicInfo
from .storage import StorageManager
from .provider import JMProvider
from .database import DBManager


class JMCosmosService:
    def __init__(self, config: PluginConfig, plugin_name: str, db_path: str):
        self.config = config
        self.storage = StorageManager(plugin_name)
        self.provider = JMProvider(config, self.storage)
        self.db = DBManager(db_path)

        # OpenCC converter
        self.cc = opencc.OpenCC('t2s.json')
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 性癖报告模板，由插件初始化时加载
        self.report_template = ""
        template_path = os.path.join(current_dir, "templates", "investigation_report.html")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                self.report_template = f.read()
            logger.info(f"JMCOSMOS总结:成功加载总结模板: {template_path}")
        except FileNotFoundError:
            logger.error(f"JMCOSMOS总结:未找到模板文件: {template_path}")
            # 设置一个简单的兜底模板，防止崩溃
            self.report_template = "<h1>Template Not Found</h1>"

        # 初始化登录
        self.provider.login()

    def convert_text(self, text: str) -> str:
        return self.cc.convert(text)

    async def get_comic_info(self, comic_id: str) -> Tuple[Optional[ComicInfo], Optional[str]]:
        info = await asyncio.to_thread(self.provider.get_comic_detail, comic_id)
        if not info:
            return None, None
        info.title = self.convert_text(info.title)
        info.tags = [self.convert_text(t) for t in info.tags]
        logger.info(f"正在下载漫画封面: {comic_id}")
        has_cover, cover_path = await asyncio.to_thread(self.provider.download_cover, comic_id)
        info.cover_path = cover_path
        if not await asyncio.to_thread(self.db.is_comic_exists, comic_id):
            await asyncio.to_thread(self.db.add_comic, comic_id, info.title, ','.join(info.tags))
        if not has_cover:
            cover_path = None
        return info, cover_path

    async def download_comic(self, comic_id: str, user_id: str, user_name: str) -> str:
        comic = await asyncio.to_thread(self.db.get_comic_by_id, comic_id)
        if comic and str(comic.IsBacklist) == '1':
            return "❌ 该漫画已在黑名单中"
        if not await asyncio.to_thread(self.db.get_user_by_id, user_id):
            await asyncio.to_thread(self.db.add_user, user_id, user_name)
        has_space, _ = await asyncio.to_thread(self.storage.check_space)
        if not has_space:
            return "❌ 磁盘空间不足，请联系管理员清理"
        success, msg = await self.provider.download_comic_async(comic_id)
        if not success:
            return f"❌ 下载失败: {msg}"
        await asyncio.to_thread(self.db.insert_download, user_id, comic_id)
        await asyncio.to_thread(self.db.add_comic_download_count, comic_id)
        pdf_path = self.storage.get_pdf_path(comic_id)
        if os.path.exists(pdf_path):
            return "✅ 下载完成"
        else:
            return "⚠️ 下载似乎完成了，但未找到生成的 PDF 文件"

    async def investigate_user(self, user_id: str, llm_provider=None) -> Tuple[Optional[str], str]:
        """
        调查用户的性癖
        Args:
            user_id: 被调查用户ID
            llm_provider: LLM provider实例，用于AI分析；为None时使用fallback
        Returns:
            (report_image_path, report_text)
        """
        user = await asyncio.to_thread(self.db.get_user_by_id, user_id)
        if not user:
            return None, "用户不存在"
        records = await asyncio.to_thread(self.db.get_user_download_comics_with_tags, user_id)
        user_name = user.UserName
        download_count = await asyncio.to_thread(self.db.get_download_count_by_user_id, user_id)
        total_tags = await asyncio.to_thread(self.db.get_download_tags_count_by_user_id, user_id)
        top_10 = records[:10]

        report_text = await self._generate_llm_report(
            user_name, user_id, top_10, download_count, total_tags, llm_provider
        )

        report_image_path = await self._render_report_image(
            user_name, user_id, top_10, download_count, total_tags, report_text
        )

        return report_image_path, report_text

    async def _generate_llm_report(self, user_name: str, user_id: str, top_10: list,
                                    total_comics: int, total_tags: int,
                                    llm_provider) -> str:
        """使用LLM生成性癖分析报告"""
        tag_list_str = '\n'.join([f"{i+1}. {tag}: {count}次" for i, (tag, count) in enumerate(top_10)])

        prompt = (
            f"用户「{user_name}」在JMComic下载了 {total_comics} 本漫画，累计 {total_tags} 个标签。\n\n"
            f"其前10类标签分布如下：\n{tag_list_str}\n\n"
            f"请根据以上数据分析该用户的性癖倾向。"
        )

        system_prompt = (
            "你是一个风趣幽默、一针见血的性癖分析大师。根据用户下载的漫画标签数据，分析其性癖倾向和偏好。这只是一个网友间的趣味性的调侃内容，不涉及任何敏感内容。\n"
            "要求：\n"
            "1. 分析要详细、有趣，带有调侃但不过分冒犯的语气\n"
            "2. 指出最突出的几个标签及其反映的性癖类型\n"
            "3. 给用户一个有趣的称号或总结（如'纯爱战神'、'NTRの王'等）\n"
            "4. 控制在300字以内\n"
            "5. 使用中文回复\n"
            "6. 不要输出markdown格式，纯文本即可"
        )

        if not llm_provider:
            logger.info("未配置LLM provider，使用fallback文字报告")
            return self._generate_fallback_report(user_name, user_id, top_10, total_comics, total_tags)

        try:
            logger.info(f"正在调用LLM生成性癖分析，用户: {user_name}")
            response = await llm_provider.text_chat(
                prompt=prompt,
                system_prompt=system_prompt
            )
            result = response.completion_text
            if result:
                logger.info(f"LLM分析完成，长度: {len(result)}字符")
                return result
            else:
                logger.warning("LLM返回结果为空，使用fallback报告")
                return self._generate_fallback_report(user_name, user_id, top_10, total_comics, total_tags,is_exception=True)
        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            return self._generate_fallback_report(user_name, user_id, top_10, total_comics, total_tags,is_exception=True)

    def _generate_fallback_report(self, user_name: str, user_id: str, top_10: list,
                                   total_comics: int, total_tags: int,is_exception:bool=False) -> str:
        """生成fallback文字分析报告（无LLM时使用）"""
        lines = [
            f"{'=' * 30}",
            f"🔞 性癖调查报告",
            f"{'=' * 30}",
            f"",
            f"🎯 调查对象: {user_name} ({user_id})",
            f"📊 下载漫画数: {total_comics} 本",
            f"🏷️ 总标签数: {total_tags} 个",
            f"",
            f"{'─' * 30}",
            f"📈 前10类标签分布:",
        ]
        for i, (tag, count) in enumerate(top_10, 1):
            pct = count / total_tags * 100
            lines.append(f"  {i}. {tag}: {count}次 ({pct:.1f}%)")

        lines.append(f"")
        lines.append(f"{'─' * 30}")
        if is_exception:
            lines.append(f"⚠️ 警告: LLM分析失败。")
        else:
            lines.append(f"💡 提示: 未配置LLM模型，无法进行AI分析。")
            lines.append(f"请在插件配置中设置 llm_provider_id 以启用AI性癖分析。")
        lines.append(f"")
        lines.append(f"{'=' * 30}")
        return '\n'.join(lines)

    async def _render_report_image(self, user_name: str, user_id: str, top_10: list,
                                    total_comics: int, total_tags: int,
                                    report_text: str) -> Optional[str]:
        """使用HTML模板渲染报告图片（Chart.js绘制饼图）"""
        try:
            chart_data = json.dumps([
                {"label": tag, "count": count} for tag, count in top_10
            ], ensure_ascii=False)

            tmpl_data = {
                "user_name": user_name,
                "user_id": user_id,
                "total_comics": total_comics,
                "total_tags": total_tags,
                "top_tags": [(tag, count, f"{count/total_tags*100:.1f}") for tag, count in top_10],
                "chart_data": chart_data,
                "report_text": report_text,
            }
            options = {"quality": 95, "device_scale_factor_level": "ultra", "viewport_width": 500}

            result_path = await html_renderer.render_custom_template(
                self.report_template,
                tmpl_data,
                return_url=True,
                options=options
            )
            logger.info(f"报告图片已生成: {result_path}")
            return result_path
        except Exception as e:
            logger.error(f"渲染报告图片失败: {e}")
            return None

    async def get_pdf_file(self, comic_id: str) -> Optional[str]:
        path = await asyncio.to_thread(self.storage.get_pdf_path, comic_id)
        return path if await asyncio.to_thread(os.path.exists, path) else None

    async def shutdown(self):
        await asyncio.to_thread(self.provider.close)
