from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import os
import yaml
from astrbot.api import logger


# 使用数据类来管理配置
@dataclass
class CosmosConfig:
    """Cosmos插件配置类"""

    domain_list: List[str]
    proxy: Optional[str]
    avs_cookie: str
    max_threads: int
    debug_mode: bool
    show_cover: bool

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "CosmosConfig":
        """从字典创建配置对象"""
        return cls(
            domain_list=config_dict.get(
                "domain_list", ["18comic.vip", "jm365.xyz", "18comic.org"]
            ),
            proxy=config_dict.get("proxy"),
            avs_cookie=config_dict.get("avs_cookie", ""),
            max_threads=config_dict.get("max_threads", 10),
            debug_mode=config_dict.get("debug_mode", False),
            show_cover=config_dict.get("show_cover", True),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "domain_list": self.domain_list,
            "proxy": self.proxy,
            "avs_cookie": self.avs_cookie,
            "max_threads": self.max_threads,
            "debug_mode": self.debug_mode,
            "show_cover": self.show_cover,
        }

    @classmethod
    def load_from_file(cls, config_path: str) -> "CosmosConfig":
        """从文件加载配置"""
        default_config = cls(
            domain_list=["18comic.vip", "jm365.xyz", "18comic.org"],
            proxy=None,
            avs_cookie="",
            max_threads=10,
            debug_mode=False,
            show_cover=True,
        )

        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在，使用默认配置: {config_path}")
            return default_config

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_dict = yaml.safe_load(f)

            if not config_dict:
                logger.warning("配置文件为空，使用默认配置")
                return default_config

            return cls.from_dict(config_dict)
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            return default_config

    def save_to_file(self, config_path: str) -> bool:
        """保存配置到文件"""
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.to_dict(), f, allow_unicode=True)
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")
            return False

