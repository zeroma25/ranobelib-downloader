"""
Модуль для работы с кэшем скачанных глав (SQLite)
"""

import atexit
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple
import shutil

from .settings import USER_DATA_DIR


class ChapterCache:
    """Менеджер кэша глав на основе SQLite."""
    
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[str] = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ChapterCache, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if getattr(self, '_initialized', False):
            return
            
        if db_path is None:
            db_path = os.path.join(USER_DATA_DIR, "cache", "cache.db")
        self.db_path = db_path
        self._conn = None
        self._init_db()
        self._initialized = True
        atexit.register(self.close)

    def close(self):
        """Закрытие соединения перед выходом."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Получение или создание подключения к БД (одно на все потоки)."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL;")
        return self._conn

    def _init_db(self):
        """Инициализация таблиц базы данных."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chapters (
                    novel_id TEXT,
                    branch_id TEXT,
                    volume TEXT,
                    number TEXT,
                    name TEXT,
                    html TEXT,
                    PRIMARY KEY (novel_id, branch_id, volume, number)
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS novels (
                    novel_id TEXT PRIMARY KEY,
                    name TEXT
                )
                """
            )

    def save_novel_info(self, novel_id: str, name: str):
        """Сохранение информации о новелле для отображения в списке кэша."""
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO novels (novel_id, name) VALUES (?, ?)",
                (str(novel_id), name)
            )

    def get_all_cached_novels(self) -> List[Dict[str, str]]:
        """Возвращает список всех закэшированных новелл."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT c.novel_id, n.name 
            FROM chapters c
            LEFT JOIN novels n ON c.novel_id = n.novel_id
            """
        )
        return [{"id": row[0], "name": row[1] or f"Новелла {row[0]}"} for row in cursor.fetchall()]

    def get_chapter(
        self, novel_id: str, branch_id: str, volume: str, number: str
    ) -> Optional[Dict[str, Any]]:
        """Получение закэшированной главы."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT name, html FROM chapters
            WHERE novel_id = ? AND branch_id = ? AND volume = ? AND number = ?
            """,
            (str(novel_id), str(branch_id), str(volume), str(number)),
        )
        row = cursor.fetchone()
        if row:
            return {
                "volume": str(volume),
                "number": str(number),
                "name": row[0],
                "html": row[1],
            }
        return None

    def get_cached_chapters(self, novel_id: str) -> set:
        """Получение набора ключей (branch_id, volume, number) закэшированных глав для новеллы."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT branch_id, volume, number FROM chapters
            WHERE novel_id = ?
            """,
            (str(novel_id),),
        )
        return set(cursor.fetchall())

    def save_chapter(
        self,
        novel_id: str,
        branch_id: str,
        volume: str,
        number: str,
        name: Optional[str],
        html: str,
    ):
        """Сохранение главы в кэш."""
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO chapters (novel_id, branch_id, volume, number, name, html)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(novel_id), str(branch_id), str(volume), str(number), name, html),
            )

    def clear_novel_cache(self, novel_id: str, clear_images: bool = True):
        """Очистка кэша (и изображений) для конкретной новеллы."""
        with self.conn:
            self.conn.execute("DELETE FROM chapters WHERE novel_id = ?", (str(novel_id),))
            self.conn.execute("DELETE FROM novels WHERE novel_id = ?", (str(novel_id),))
        
        if clear_images:
            temp_dir = os.path.join(USER_DATA_DIR, "cache", f"cache_images_{novel_id}")
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except OSError:
                    pass

    def clear_all_cache(self, clear_images: bool = True):
        """Очистка всего кэша (и папки temp)."""
        with self.conn:
            self.conn.execute("DELETE FROM chapters")
            self.conn.execute("DELETE FROM novels")
        self.conn.execute("VACUUM")
        
        if clear_images:
            temp_dir = os.path.join(USER_DATA_DIR, "cache")
            if os.path.exists(temp_dir):
                for item in os.listdir(temp_dir):
                    if item.startswith("cache_images_"):
                        item_path = os.path.join(temp_dir, item)
                        try:
                            if os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                            else:
                                os.remove(item_path)
                        except OSError:
                            pass
