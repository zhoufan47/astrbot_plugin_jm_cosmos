# comicUtils.py

import re
from astrbot.api import logger


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


def validate_comic_id(comic_id: str) -> bool:
    """验证漫画ID格式，防止路径遍历"""
    if not re.match(r"^\d+$", comic_id):
        return False
    if len(comic_id) > 10:  # 合理的ID长度限制
        return False
    return True


def validate_domain(domain: str) -> bool:
    """验证域名格式"""
    # 基本域名格式验证
    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
    if not re.match(pattern, domain):
        return False
    if len(domain) > 253:
        return False
    # 防止添加恶意域名
    blocked_domains = ["localhost", "127.0.0.1", "0.0.0.0"]
    return domain not in blocked_domains


def handle_download_error(error: Exception, context: str) -> str:
    """统一的错误处理"""
    error_msg = str(error)

    if "timeout" in error_msg.lower():
        return f"{context}超时，请检查网络连接或稍后重试"
    elif "connection" in error_msg.lower():
        return f"{context}连接失败，请检查网络或代理设置"
    elif "文本没有匹配上字段" in error_msg:
        return f"{context}失败：网站结构可能已更改，请使用 /jmdomain update 更新域名"
    elif "permission" in error_msg.lower() or "access" in error_msg.lower():
        return f"{context}失败：文件权限错误，请检查存储目录权限"
    elif "space" in error_msg.lower() or "disk" in error_msg.lower():
        return f"{context}失败：存储空间不足，请清理磁盘空间"
    else:
        logger.error(f"{context}未知错误: {error_msg}", exc_info=True)
        return f"{context}失败：{error_msg[:100]}"  # 限制错误消息长度

