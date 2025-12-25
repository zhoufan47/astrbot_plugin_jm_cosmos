from typing import List, Optional
from pydantic import BaseModel
import os
import json
from astrbot.api import logger


class CosmosConfig(BaseModel):
    domain_list: List[str] = ["18comic.vip", "jm365.xyz", "18comic.org"]
    proxy: Optional[str] = None
    avs_cookie: str = ""
    max_threads: int = 10
    debug_mode: bool = False
    show_cover: bool = True
    jm_username: str = ""
    jm_passwd: str = ""
    is_jm_login: bool = False

    @classmethod
    def load(cls, path: str) -> "CosmosConfig":
        """加载配置，如果失败则返回默认配置"""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    return cls.parse_obj(json.load(f))
            except Exception as e:
                logger.error(f"[JMCosmos] 加载配置失败: {e}，使用默认配置")
        return cls()

    def save(self, path: str):
        """保存配置到文件"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(self.json(indent=2, ensure_ascii=False))
            logger.info(f"[JMCosmos] 配置已保存至 {path}")
        except Exception as e:
            logger.error(f"[JMCosmos] 保存配置失败: {e}")