import aiohttp
from astrbot.api import logger
import traceback

async def post_to_discord(comic_id,comic_title,comic_info, tags,cover_path, pdf_path):
    # ==================== 新增 API 推送逻辑 ====================
    try:
        # 1. 配置 API 地址 (请修改为您实际的 API 地址)
        api_url = "http://192.168.31.35:2238/api/publish"

        logger.info(f"准备推送漫画数据到 API: {api_url}")

        # 3. 构造请求体
        payload = {
            "comic_id":comic_id,
            "title": comic_title,
            "content": comic_info,
            "cover": cover_path,
            "tags": tags,
            "attachment": [
                pdf_path
            ]
        }
        logger.info(f"请求体: {payload}")
        # 4. 异步发送请求
        async with aiohttp.ClientSession() as session:
            # 设置超时，防止 API 无响应卡住插件
            timeout = aiohttp.ClientTimeout(total=10)
            logger.info(f"异步发送请求到 API: {api_url}")
            async with session.post(api_url, json=payload, timeout=timeout) as response:
                logger.info(f"等待响应……")
                resp_text = await response.text()
                if response.status == 200:
                    logger.info(f"✅ API 推送成功: {resp_text}")
                    # 可选：通知用户 API 推送成功
                    # yield event.plain_result("API 推送成功")
                else:
                    logger.error(f"❌ API 推送失败 [Status {response.status}]: {resp_text}")

    except Exception as api_e:
        logger.error(traceback.format_exc())
        logger.error(f"❌ API 推送过程中发生错误: {api_e}")
        # 这里 catch 所有异常，确保 API 报错不会影响给用户发文件
    # ==================== API 推送逻辑结束 ====================