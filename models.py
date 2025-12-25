from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class DownloadStatus(Enum):
    SUCCESS = "成功"
    PENDING = "等待中"
    DOWNLOADING = "下载中"
    FAILED = "失败"


@dataclass
class ComicInfo:
    """漫画详情数据传输对象 (DTO)"""
    id: str
    title: str
    tags: List[str] = field(default_factory=list)
    pub_date: str = "未知"
    total_pages: int = 0
    cover_path: Optional[str] = None

    def to_summary_string(self) -> str:
        return (
            f"📖: {self.title}\n"
            f"🆔: {self.id}\n"
            f"🏷️: {', '.join(self.tags[:5])}\n"
            f"📅: {self.pub_date}\n"
            f"📃: {self.total_pages}"
        )


@dataclass
class DownloadResult:
    success: bool
    message: str
    file_path: Optional[str] = None