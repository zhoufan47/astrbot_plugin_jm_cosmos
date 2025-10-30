# db_manager.py
import sqlite3
import os
from astrbot.api import logger
from typing import Optional

from .domains import User,Comic

from datetime import datetime


"""SQLite数据库管理器"""
class DBManager:

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

    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                                DELETE FROM Users WHERE UserId=?
                                """, user_id)
                conn.commit()
                logger.info(f"用户 {user_id} 删除成功")
                return True
        except sqlite3.IntegrityError as e:
            logger.warning(f"用户 {user_id} 已存在: {e}")
            return False
        except Exception as e:
            logger.error(f"删除用户失败: {e}")
            return False

    def add_comic(self, comic_id: str, comic_name: str, tags: str) -> bool:
        """添加新漫画"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                                INSERT INTO Comics (ComicId, ComicName, DownloadCount, Tags,DownloadDate)
                                VALUES (?, ?, ?, ?,?)
                                """, (comic_id, comic_name,0, tags,datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()
                logger.info(f"漫画 {comic_id} 添加成功")
                return True
        except sqlite3.IntegrityError as e:
            logger.warning(f"漫画 {comic_id} 已存在: {e}")
            return False
        except Exception as e:
            logger.error(f"添加漫画失败: {e}")
            return False

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        logger.info(f"开始查询用户{user_id}")
        """根据ID获取用户"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, UserId, UserName
                    FROM Users WHERE UserId = ?
                ''', (user_id,))
                row = cursor.fetchone()
                if row:
                    logger.info(f"用户 {user_id} 查询成功,{User(*row)}")
                    return User(*row)
                logger.info(f"用户 {user_id} 不存在")
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
                return result[0]
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
                return result[0]
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
                                """, (is_backlist,comic_id))
                conn.commit()
        except sqlite3.Error as e:
            return f"更新漫画的是否黑名单标示时发生错误：{e}"

    def insert_download(self, user_id,comic_id):
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
                                """, (user_id, comic_id,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
        except sqlite3.Error as e:
            return f"插入下载记录时发生错误：{e}"


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
                                """, (comic_id,))
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
                                """, (comic_id,))
                result = cursor.fetchone()  # 获取一条记录
                if result is None: return 0
                return result[0]
        except sqlite3.Error as e:
            print(f"查询下载次数最多的漫画时发生错误：{e}")
            return 0

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
                                """, (comic_id,))
                result = cursor.fetchone()  # 获取一条记录
                if result is None: return "无记录"
                return result[0]
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
                                """, (comic_id,))
                result = cursor.fetchone()  # 获取一条记录
                if result is None: return None
                return result[0]
        except sqlite3.Error as e:
            print(f"获取漫画的最初下载用户时发生错误：{e}")
            return "0"

    def get_comic_by_id(self, comic_id: str) -> Optional[Comic]:
        """根据ID获取漫画"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, ComicId, ComicName,DownloadDate,DownloadCount,Tags,IsBacklist
                    FROM Comics WHERE ComicId = ?
                ''', (comic_id,))
                row = cursor.fetchone()
                if row:
                    return Comic(*row)
                return None
        except Exception as e:
            logger.error(f"查询漫画失败: {e}")
            return None

    def get_most_download_user_id_by_tag(self, custom_tag:str):
        """
        获取标签最常下载的作者ID
        Args:
            custom_tag: 自定义标签
        Returns:
            用户ID，User_Id
        """
        try:
            logger.info(f"查询标签最常下载的作者ID: {custom_tag}")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT UserId FROM (SELECT A.UserId,COUNT(A.ComicId) 
                                        download_count FROM DOWNLOADS A 
                                        LEFT JOIN COMICS B ON A.ComicId = B.ComicId 
                                        WHERE B.TAGS LIKE '%'||?||'%' GROUP BY A.UserId)
                                  ORDER BY DOWNLOAD_COUNT DESC
                                """, (custom_tag,))
                result = cursor.fetchone()  # 获取一条记录
                logger.info(f"获取标签最常下载的作者ID返回结果: {result}")
                if result is None: return None
                return result[0]
        except Exception as e:
            logger.error(f"获取漫画的最初下载用户时发生错误：{e}")
            return "10000"

    def is_comic_exists(self, comic_id):
        try:
            logger.info(f"查询漫画数据是否存在: {comic_id}")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT ComicId From Comics where ComicId=?
                                """, (comic_id,))
                result = cursor.fetchone()  # 获取一条记录
                logger.info(f"查询漫画数据返回结果: {result}")
                if result is None: return False
                logger.info(f"漫画数据已存在: {comic_id}")
                return True
        except Exception as e:
            logger.error(f"获取漫画数据是否存在时发生错误：{e}")
            return False