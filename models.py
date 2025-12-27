from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ComicInfo(BaseModel):
    """标准化的漫画信息模型"""
    id: str
    title: str
    tags: List[str] = Field(default_factory=list)
    author: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    pub_date: Optional[str] = None
    total_pages: int = 0
    cover_path: Optional[str] = None

    # 用于显示的简短描述
    def to_display_string(self) -> str:
        return (
            f"📖: {self.title}\n"
            f"🆔: {self.id}\n"
            f"🏷️: {', '.join(self.tags[:5])}\n"
            f"📅: {self.pub_date or '未知'}\n"
            f"📃: {self.total_pages} 页"
        )


class DownloadResult(BaseModel):
    """下载结果模型"""
    success: bool
    message: str
    file_path: Optional[str] = None
    file_type: str = "pdf"  # pdf, zip, image_folder


class StorageStatus(BaseModel):
    """存储状态模型"""
    total_mb: float
    used_mb: float
    free_mb: float
    percent: float