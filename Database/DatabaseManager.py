# database.py
import sqlite3
import os
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class User:
    """用户数据类"""
    id: Optional[int] = None
    UserId: Optional[str] = None
    UID: Optional[str] = None
    UserName: Optional[str] = None

@dataclass
class Comic:
    """漫画数据类"""
    id: Optional[int] = None
    ComicId: Optional[str] = None
    ComicName: Optional[str] = None
    DownloadDate: Optional[str] = None
    DownloadCount: Optional[str] = None
    IsBacklist: Optional[str] = None

@dataclass
class Download:
    """下载数据类"""
    id: Optional[int] = None
    UserId: Optional[str] = None
    ComicId: Optional[str] = None
    DownloadDate: Optional[str] = None

class DatabaseManager:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库和表结构"""
        try:
            # 确保数据库目录存在
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 创建用户表Users   ID:自动编号   UserId:用户QQ     UserName:用户名
                cursor.execute("""
                                    CREATE TABLE IF NOT EXISTS Users
                                    (
                                        ID INTEGER PRIMARY KEY AUTOINCREMENT,
                                        UserId TEXT NOT NULL,
                                        UserName TEXT NOT NULL
                                    )
                                    """)

                # 创建漫画记录表    ID:自动编号   ComicId:JM车牌号 DownloadDate:下载日期 DownloadCount:下载次数   IsBacklist 是否黑名单
                cursor.execute("""
                                    CREATE TABLE IF NOT EXISTS Comics
                                    (
                                        ID INTEGER PRIMARY KEY AUTOINCREMENT,
                                        ComicId TEXT NOT NULL,
                                        ComicName TEXT NOT NULL,
                                        DownloadDate TEXT NOT NULL, -- 可以存储 YYYY-MM-DD 格式的日期
                                        DownloadCount INTEGER NOT NULL DEFAULT 0,
                                        IsBacklist TEXT NOT NULL DEFAULT '0',
                                        Tags TEXT
                                    )
                                """)

                # 下载记录表  ID:自动编号   UserId:U+用户QQ    ComicId:JM车牌号   DownloadDate:下载日期
                cursor.execute("""
                                    CREATE TABLE IF NOT EXISTS Downloads
                                    (
                                        ID INTEGER PRIMARY KEY AUTOINCREMENT,
                                        UserId TEXT NOT NULL,
                                        ComicId TEXT NOT NULL,
                                        DownloadDate TEXT NOT NULL default (
                                        datetime ( 'now', 'localtime' ))
                                    )
                                """)
                
                conn.commit()
                logger.info("数据库初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def add_user(self, user_id: str, user_name: Optional[str] = None) -> bool:
        """添加新用户"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                                INSERT INTO users (UserId, UserName)
                                VALUES (?, ?)
                                """, (user_id, user_name))
                conn.commit()
                logger.info(f"用户 {user_name} 添加成功")
                return True
        except sqlite3.IntegrityError as e:
            logger.warning(f"用户 {user_name} 已存在: {e}")
            return False
        except Exception as e:
            logger.error(f"添加用户失败: {e}")
            return False
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, UserId, UserName
                    FROM users WHERE UserId = ?
                ''', (user_id,))
                row = cursor.fetchone()
                if row:
                    return User(*row)
                return None
        except Exception as e:
            logger.error(f"查询用户失败: {e}")
            return None
    
    def query_most_download_user(self):
        """
        查询下载次数最多的用户。
        Returns:
            一个UserId。
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                                SELECT UserId
                                from (SELECT COUNT(id) DownloadCount, UserId
                                      FROM Downloads
                                      GROUP BY id, UserId
                                      order by DownloadCount) limit 1
                                """)
                result = cursor.fetchone()  # 获取一条记录
                if result is None: return "0"
                return result
        except sqlite3.Error as e:
            print(f"查询下载次数最多的用户时发生错误：{e}")
            return "0"

    def query_most_download_comic(self):
        """
        查询下载次数最多的漫画。
        Returns:
            一个ComicId。
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                                SELECT ComicId
                                from (SELECT COUNT(id) DownloadCount, ComicId
                                      FROM Downloads
                                      GROUP BY ComicId, id
                                      order by DownloadCount) limit 1
                                """)
                result = cursor.fetchone()  # 获取一条记录
                if result is None: return "0"
                return result
        except sqlite3.Error as e:
            print(f"查询下载次数最多的漫画时发生错误：{e}")
            return "0"

    def update_comic_is_backlist(self, comic_id, is_backlist):
        """
        更新漫画的是否黑名单标示
        Args:
            comic_id: JM车牌号。
            is_backlist: 是否黑名单
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                                UPDATE Comics
                                SET IsBacklist = ?
                                WHERE ComicId = ?
                                """, (comic_id, is_backlist))
                conn.commit()
        except sqlite3.Error as e:
            return f"更新漫画的是否黑名单标示时发生错误：{e}"

    def insert_download(self, comic_id):
        """
        向 download 表中插入一条新记录。
        Args:
            comicId: 车牌号
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                                INSERT INTO Downloads (UserId, ComicId, DownloadDate)
                                VALUES (?, ?, ?)
                                """, (self.UserId, comic_id, datetime.now().date()))
                conn.commit()
        except sqlite3.Error as e:
            return f"插入下载记录时发生错误：{e}"

    def insert_comic(self, comic_id, comic_name, tags):
        """
        向 comics 表中插入一条新记录。
        Args:
            comic_id: 车牌号
            comic_name: 车牌号
            tags: 车牌号
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                                INSERT INTO Comics (ComicId, ComicName, DownloadDate, Tags)
                                VALUES (?, ?, ?)
                                """, (comic_id, comic_name, datetime.now().date(), tags))
                conn.commit()
        except sqlite3.Error as e:
            return f"插入漫画记录时发生错误：{e}"

    def add_comic_download_count(self, comic_id):
        """
        更新漫画的下载次数+1。
        Args:
            comic_id: 车牌号
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                                UPDATE Comics
                                SET DownloadCount = DownloadCount + 1
                                WHERE ComicId = ?
                                """, comic_id)
                conn.commit()
        except sqlite3.Error as e:
            return f"更新漫画下载次数时发生错误：{e}"

    def get_comic_download_count(self, comic_id):
        """
        获取漫画的下载次数。
        Args:
            comic_id: 车牌号
        Returns:
            一个数字，表示漫画的下载次数。
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT COUNT(1)
                                   FROM Downloads
                                   where ComicId = ?
                                """, comic_id)
                result = cursor.fetchone()  # 获取一条记录
                if result is None: return "0"
                return result
        except sqlite3.Error as e:
            print(f"查询下载次数最多的漫画时发生错误：{e}")
            return "0"

    def get_last_download_user(self, comic_id):
        """
        获取漫画的最后下载用户。
        Args:
            comic_id: 车牌号
        Returns:
            一个数字，表示漫画的下载次数。
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT UserId
                                   FROM Downloads
                                   where ComicId = ?
                                   order by DownloadDate desc LIMIT 1
                                """, comic_id)
                result = cursor.fetchone()  # 获取一条记录
                if result is None: return "无记录"
                return result
        except sqlite3.Error as e:
            print(f"获取漫画的最后下载用户时发生错误：{e}")
            return "0"


    def get_first_download_user(self, comic_id):
        """
        获取漫画的最初下载用户。
        Args:
            comic_id: 车牌号
        Returns:
            一个数字，表示漫画的下载次数。
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT UserId
                                   FROM Downloads
                                   where ComicId = ?
                                   order by DownloadDate ASC LIMIT 1
                                """, comic_id)
                result = cursor.fetchone()  # 获取一条记录
                if result is None: return "无记录"
                return result
        except sqlite3.Error as e:
            print(f"获取漫画的最初下载用户时发生错误：{e}")
            return "0"
