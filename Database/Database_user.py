import sqlite3
from math import exp
import json
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from datetime import datetime, timedelta
from astrbot.api import AstrBotConfig
import os


class Database_user(Star):
    def __init__(self, config, DatabaseFile, Id=None):
        database_config = config.get("database", {})
        database_name = database_config.get("user", "")
        if database_name == "": database_name = "astrbot_plugin_database_user"
        db_file = os.path.join(DatabaseFile, database_name + ".db")
        self.UID = Id
        self.UserId = f"U{Id}"
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()

        # 创建用户表Users   ID:自动编号   UserId:U+用户QQ    UID:用户QQ    UserName:用户名
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserId TEXT NOT NULL,
                UID INTEGER NOT NULL,
                UserName TEXT NOT NULL
            )
        """)

        # 创建漫画记录表    ID:自动编号   ComicId:JM车牌号 DownloadDate:下载日期 DownloadCount:下载次数   IsBacklist 是否黑名单
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Comics (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ComicId TEXT NOT NULL,
                DownloadDate TEXT NOT NULL,  -- 可以存储 YYYY-MM-DD 格式的日期
                DownloadCount INTEGER NOT NULL DEFAULT 1,
                IsBacklist TEXT NOT NULL DEFAULT "0",
                Tags TEXT 
            )
        """)

        # 下载记录表  ID:自动编号   UserId:U+用户QQ    ComicId:JM车牌号   DownloadDate:下载日期
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Download (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserId TEXT NOT NULL,
                ComicId TEXT NOT NULL,
                DownloadDate TEXT NOT NULL
            )
        """)


    def close(self):
        self.cursor.close()
        self.connection.close()

    # ********** users表操作 **********

    def insert_user(self, user_name):
        """
        向 users 表中插入一条新记录。
        Args:
            user_name: 用户名 (字符串, 支持 Emoji)。
        """
        if self.UserId is None: return
        try:
            self.cursor.execute("""
                INSERT INTO users (UserId, UID, UserName)
                VALUES (?, ?, ?)
            """, (self.UserId, self.UID, user_name))
            self.connection.commit()
        except sqlite3.Error as e:
            return f"插入用户时发生错误：{e}"

    def query_user(self):
        """
        根据 UserId 查询用户信息。
        Returns:
            一个元组，包含查询到的用户信息 (ID, UserId, UID, UserName)，如果没有找到则返回 None。
        """
        try:
            self.cursor.execute("""
                SELECT ID, UserId, UID, UserName
                FROM users
                WHERE UserId = ?
            """, (self.UserId,))
            result = self.cursor.fetchone()  # 获取一条记录
            return result
        except sqlite3.Error as e:
            print(f"查询用户时发生错误：{e}")
            return None

    def query_most_download_user(self):
        """
        查询下载次数最多的用户。
        Returns:
            一个UserId。
        """
        try:
            self.cursor.execute("""
                SELECT UserId from (SELECT COUNT(id) DownloadCount,UserId 
                FROM Download GROUP BY id, UserId order by DownloadCount) limit 1
            """)
            result = self.cursor.fetchone()  # 获取一条记录
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
            self.cursor.execute("""
                SELECT ComicId from (SELECT COUNT(id) DownloadCount,ComicId 
                FROM Download GROUP BY ComicId, id order by DownloadCount) limit 1
            """)
            result = self.cursor.fetchone()  # 获取一条记录
            if result is None: return "0"
            return result
        except sqlite3.Error as e:
            print(f"查询下载次数最多的用户时发生错误：{e}")
            return "0"

    def update_comic_is_backlist(self,comic_id, is_backlist):
        """
        更新漫画的是否黑名单标示
        Args:
            comic_id: JM车牌号。
            is_backlist: 是否黑名单
        """
        try:
            self.cursor.execute("""
                UPDATE Comics SET IsBacklist = ? WHERE ComicId = ?
            """, (comic_id, is_backlist))
            self.connection.commit()
        except sqlite3.Error as e:
            return f"更新漫画的是否黑名单标示时发生错误：{e}"
