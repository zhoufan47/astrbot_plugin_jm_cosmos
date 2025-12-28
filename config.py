from typing import List, Optional
from pydantic import BaseModel, Field


class PluginConfig(BaseModel):
    domain_list: List[str] = Field(
        default=["18comic.vip", "jm365.xyz", "18comic.org"],
        description="JMComic 域名列表"
    )
    proxy: Optional[str] = None
    avs_cookie: str = ""
    max_threads: int = Field(default=10, ge=1, le=50)
    debug_mode: bool = False
    show_cover: bool = True
    jm_username: Optional[str] = None
    jm_passwd: Optional[str] = None
    is_jm_login: bool = False
    is_discord_post: bool = False
    discord_post_api_url: Optional[str] = None

    # 自动处理字符串列表转换 (为了兼容 AstrBot 有时传回逗号分隔字符串的情况)
    @classmethod
    def from_dict(cls, data: dict):
        if "domain_list" in data and isinstance(data["domain_list"], str):
            data["domain_list"] = [d.strip() for d in data["domain_list"].split(",") if d.strip()]
        return cls(**data)