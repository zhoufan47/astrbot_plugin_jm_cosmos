from typing import Optional
from dataclasses import dataclass


@dataclass
class Comic:
    """漫画数据类"""
    id: Optional[int] = None
    ComicId: Optional[str] = None
    ComicName: Optional[str] = None
    DownloadDate: Optional[str] = None
    DownloadCount: Optional[str] = None
    Tags: Optional[str] = None
    IsBacklist: Optional[str] = None

@dataclass
class Download:
    """下载数据类"""
    id: Optional[int] = None
    UserId: Optional[str] = None
    ComicId: Optional[str] = None
    DownloadDate: Optional[str] = None

@dataclass
class User:
    """用户数据类"""
    id: Optional[int] = None
    UserId: Optional[str] = None
    UserName: Optional[str] = None