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

        # 创建漫画记录表    ID:自动编号   ComicId:JM车牌号 DownloadDate  DownloadCount:签到次数    SignInCoins:签到获得的金币
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS SignIns (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserId TEXT NOT NULL,
                SignInDate TEXT NOT NULL,  -- 可以存储 YYYY-MM-DD 格式的日期
                SignInCount INTEGER NOT NULL DEFAULT 1,
                SignInCoins REAL NOT NULL DEFAULT 0.0
            )
        """)

        # 创建用户表fish_cooling   ID:自动编号   UserId:U+用户QQ    cooling:冷却时间
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fish_cooling (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserId TEXT NOT NULL,
                cooling TEXT NOT NULL
            )
        """)

        # 创建装备表equipment   ID:自动编号   UserId:U+用户QQ    equipment_type:装备类型    equipment_id:装备ID    equipment_name:装备名称
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserId TEXT NOT NULL,
                equipment_type TEXT NOT NULL,
                equipment_id INTEGER NOT NULL,
                equipment_name TEXT NOT NULL
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

    # ********** signIns表操作 **********

    def insert_sign_in(self):
        """
        向 signIns 表中插入一条新记录。
        """
        if self.UserId is None: return
        try:
            # sign_in_date = datetime.now().strftime("%Y-%m-%d")
            sign_in_date = "2025-01-01"
            self.cursor.execute("""
                INSERT INTO signIns (UserId, SignInDate, SignInCount, SignInCoins)
                VALUES (?, ?, ?, ?)
            """, (self.UserId, sign_in_date, 0, 0.0))
            self.connection.commit()
        except sqlite3.Error as e:
            return f"插入签到记录时发生错误：{e}"

    def query_sign_in(self):
        """
        根据 UserId 查询用户签到信息。
        Returns:
            一个元组，包含查询到的签到信息 (ID, UserId, SignInDate, SignInCount, SignInCoins)，如果没有找到则返回 None。
        """
        try:
            self.cursor.execute("""
                SELECT ID, UserId, SignInDate, SignInCount, SignInCoins
                FROM signIns
                WHERE UserId = ?
            """, (self.UserId,))
            result = self.cursor.fetchone()  # 获取一条记录
            return result
        except sqlite3.Error as e:
            print(f"查询签到记录时发生错误：{e}")
            return None

    def update_sign_in(self, economy):
        """
        更新用户签到信息。
        Args:
            economy: 签到获得的金币数。
        """
        if self.UserId is None: return
        try:
            sign_in_date = datetime.now().strftime("%Y-%m-%d")
            self.cursor.execute("""
                UPDATE signIns
                SET SignInDate = ?,
                    SignInCount = SignInCount + 1,
                    SignInCoins = ?
                WHERE UserId = ?
            """, (sign_in_date, economy, self.UserId))
            self.connection.commit()
        except sqlite3.Error as e:
            return f"更新签到记录时发生错误：{e}"

    def query_sign_in_count(self):
        """
        查询用户签到次数。
        Returns:
            一个整数，表示用户签到次数。
        """
        if self.UserId is None: return 0
        try:
            self.cursor.execute("""
                SELECT SignInCount
                FROM signIns
                WHERE UserId = ?
            """, (self.UserId,))
            result = self.cursor.fetchone()  # 获取一条记录
            if result is None: return 0
            return result
        except sqlite3.Error as e:
            print(f"查询签到次数时发生错误：{e}")
            return 0

    def query_sign_in_coins(self):
        """
        查询用户签到获得的金币。
        Returns:
            一个浮点数，表示用户签到获得的金币。
        """
        if self.UserId is None: return 0.0
        try:
            self.cursor.execute("""
                SELECT SignInCoins
                FROM signIns
                WHERE UserId = ?
            """, (self.UserId,))
            result = self.cursor.fetchone()  # 获取一条记录
            if result is None: return 0.0
            return result[0]
        except sqlite3.Error as e:
            print(f"查询签到获得的金币时发生错误：{e}")
            return 0.0

    def query_last_sign_in_date(self):
        """
        查询用户上次签到日期。
        Returns:
            一个字符串，表示用户上次签到日期 (YYYY-MM-DD 格式)。
        """
        if self.UserId is None: return ""
        try:
            self.cursor.execute("""
                SELECT SignInDate
                FROM signIns
                WHERE UserId = ?
                ORDER BY ID DESC
                LIMIT 1
            """, (self.UserId,))
            result = self.cursor.fetchone()  # 获取一条记录
            if result is None: return ""
            return result[0]
        except sqlite3.Error as e:
            print(f"查询上次签到日期时发生错误：{e}")
            return ""

    # ********** fish_cooling表操作 **********

    def insert_fish_cooling(self):
        """
        向 fish_cooling 表中插入一条新记录。
        """
        if self.UserId is None: return
        try:
            self.cursor.execute("""
                INSERT INTO fish_cooling (UserId, cooling)
                VALUES (?, ?)
            """, (self.UserId, "2024-12-30 10:00:00"))
            self.connection.commit()
        except sqlite3.Error as e:
            return f"插入用户时发生错误：{e}"

    def query_fish_cooling(self):
        """
        根据 UserId 查询用户钓鱼冷却信息。
        Returns:
            一个元组，包含查询到的用户信息 (cooling,)，如果没有找到则返回 None。
        """
        try:
            self.cursor.execute("""
                SELECT cooling
                FROM fish_cooling
                WHERE UserId = ?
            """, (self.UserId,))
            result = self.cursor.fetchone()  # 获取一条记录
            return result
        except sqlite3.Error as e:
            print(f"查询用户时发生错误：{e}")
            return None

    def update_fish_cooling(self, minutes):
        """
        更新用户钓鱼冷却信息。
        Args:
            minutes: 冷却时间，单位为分钟。
        """
        if self.UserId is None: return
        try:
            cooling_time_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cooling_time_date = datetime.strptime(cooling_time_date_str, "%Y-%m-%d %H:%M:%S")
            cooling_time_date = cooling_time_date + timedelta(minutes=minutes)
            cooling_time_date = cooling_time_date.strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("""
                UPDATE fish_cooling
                SET cooling = ?
                WHERE UserId = ?
            """, (cooling_time_date, self.UserId))
            self.connection.commit()
        except sqlite3.Error as e:
            return f"更新签到记录时发生错误：{e}"

    # ********** equipment表操作 **********

    def insert_equipment(self, equipment_type):
        """
        向 equipment 表中插入一条新记录。
        Args:
            equipment_type: 装备类型 (字符串)。
        """
        if self.UserId is None: return
        if self.query_equipment_type(equipment_type) is not None: return
        # print(self.query_equipment_type(equipment_type))
        try:
            self.cursor.execute("""
                INSERT INTO equipment (UserId, equipment_type, equipment_id, equipment_name)
                VALUES (?, ?, ?, ?)
            """, (self.UserId, equipment_type, -1, "None"))
            # print(equipment_type)
            self.connection.commit()
        except sqlite3.Error as e:
            return f"插入装备记录时发生错误：{e}"

    # def query_equipment_all(self):
    #     """
    #     根据 UserId 查询用户所有装备信息。
    #     Returns:
    #         一个列表，包含查询到的所有装备信息 (ID, UserId, equipment_type, equipment_id, equipment_name)。
    #     """
    #     try:
    #         self.cursor.execute("""
    #             SELECT ID, UserId, equipment_type, equipment_id, equipment_name
    #             FROM equipment
    #             WHERE UserId = ?
    #         """, (self.UserId,))
    #         result = self.cursor.fetchall()  # 获取所有记录
    #         return result
    #     except sqlite3.Error as e:
    #         print(f"查询用户时发生错误：{e}")
    #         return None

    def query_equipment_type(self, equipment_type):
        """
        根据 UserId 和 equipment_type 查询用户装备信息。
        Args:
            equipment_type: 装备类型 (字符串)。
        Returns:
            一个元组，包含查询到的装备信息 (ID, UserId, equipment_type, equipment_id, equipment_name)，如果没有找到则返回 None。
        """
        try:
            self.cursor.execute("""
                SELECT ID, UserId, equipment_type, equipment_id, equipment_name
                FROM equipment
                WHERE UserId = ? AND equipment_type = ?
            """, (self.UserId, equipment_type))
            result = self.cursor.fetchone()  # 获取一条记录
            return result
        except sqlite3.Error as e:
            print(f"查询装备记录时发生错误：{e}")
            return None

    def query_equipment_id(self, equipment_id):
        """
        根据 UserId 和 equipment_id 查询用户装备信息。
        Args:
            equipment_id: 装备ID (整数)。
        Returns:
            一个元组，包含查询到的装备信息 (ID, UserId, equipment_type, equipment_id, equipment_name)，如果没有找到则返回 None。
        """
        try:
            self.cursor.execute("""
                SELECT ID, UserId, equipment_type, equipment_id, equipment_name
                FROM equipment
                WHERE UserId = ? AND equipment_id = ?
            """, (self.UserId, equipment_id))
            result = self.cursor.fetchone()  # 获取一条记录
            return result
        except sqlite3.Error as e:
            print(f"查询装备记录时发生错误：{e}")
            return None

    def query_equipment_name(self, equipment_name):
        """
        根据 UserId 和 equipment_name 查询用户装备信息。
        Args:
            equipment_name: 装备名称 (字符串)。
        Returns:
            一个元组，包含查询到的装备信息 (ID, UserId, equipment_type, equipment_id, equipment_name)，如果没有找到则返回 None。
        """
        try:
            self.cursor.execute("""
                SELECT ID, UserId, equipment_type, equipment_id, equipment_name
                FROM equipment
                WHERE UserId = ? AND equipment_name = ?
            """, (self.UserId, equipment_name))
            result = self.cursor.fetchone()  # 获取一条记录
            return result
        except sqlite3.Error as e:
            print(f"查询装备记录时发生错误：{e}")
            return None

    def update_equipment(self, equipment_type, equipment_id, equipment_name):
        """
        更新用户装备信息。
        Args:
            equipment_type: 装备类型 (字符串)。
            equipment_id: 装备ID (整数)。
            equipment_name: 装备名称 (字符串)。
        """
        if self.UserId is None: return
        try:
            self.cursor.execute("""
                UPDATE equipment
                SET equipment_id = ?,
                    equipment_name = ?
                WHERE UserId = ? AND equipment_type = ?
            """, (equipment_id, equipment_name, self.UserId, equipment_type))
            self.connection.commit()
        except sqlite3.Error as e:
            return f"更新装备记录时发生错误：{e}"

    # ********** 饰品操作方法 **********

    def add_accessory(self, slot, accessory_id, accessory_name):
        """
        添加饰品到指定栏位
        Args:
            slot: 饰品栏位(1-3)
            accessory_id: 饰品ID
            accessory_name: 饰品名称
        Returns:
            成功返回True，失败返回False
        """
        if slot not in ["1", "2", "3"]:
            return False
        return self.update_equipment(f"饰品{slot}", accessory_id, accessory_name)

    def remove_accessory(self, slot):
        """
        移除指定栏位的饰品
        Args:
            slot: 饰品栏位(1-3)
        Returns:
            成功返回True，失败返回False
        """
        print(slot)
        if slot not in ["1", "2", "3"]:
            return False
        return self.update_equipment(f"饰品{slot}", -1, "None")

    def get_accessories(self):
        """
        获取用户所有饰品
        Returns:
            饰品列表，格式: [(slot, accessory_id, accessory_name), ...]
        """
        accessories = []
        for slot in ["1", "2", "3"]:
            result = self.query_equipment_type(f"饰品{slot}")
            if result and result[3]:  # equipment_id不为空
                accessories.append((slot, result[3], result[4]))  # (slot, id, name)
        return accessories