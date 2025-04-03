# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, unquote

from .base import StorageManager

try:
    import mariadb
except Exception:
    mariadb = None


class SQLStorage(StorageManager):
    """
    SQL storage implementation supporting SQLite and MariaDB/MySQL.

    URI formats
    -----------
    - SQLite:
        "sqlite:///:memory:"           -> in-memory
        "sqlite:///path/to/file.db"    -> file (relative with this implementation if netloc is empty)
        "sqlite:////absolute/path.db"  -> absolute
    - MariaDB/MySQL:
        "mariadb://user:pass@host:3306/dbname"
        "mysql://user:pass@host:3306/dbname"

    Table schema
    ------------
    telegram_messages(
        id           (PK, autoincrement),
        chat_id      BIGINT,
        user_id      BIGINT,
        user_name    TEXT/VARCHAR,
        message_id   BIGINT,
        text         TEXT,
        message_type TEXT/VARCHAR,
        date         TEXT (ISO datetime),
        reply_to     BIGINT,
        entities     TEXT (JSON),
        full_json    TEXT (original JSON payload)
    )
    """

    def __init__(self, uri: str) -> None:
        self._uri = uri
        self._db_type: str
        self._conn: Any
        self._lock = threading.Lock()
        self._paramstyle_qmark = False

        parsed = urlparse(uri)
        scheme = (parsed.scheme or "").lower()

        if scheme == "sqlite":
            self._db_type = "sqlite"
            self._paramstyle_qmark = True
            path = self._sqlite_path_from_uri(parsed)
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
        elif scheme in ("mariadb", "mysql"):
            if mariadb is None:
                raise ImportError(
                    "mariadb Python driver is not installed. "
                    "Install with: pip install mariadb"
                )
            self._db_type = "mariadb"
            self._paramstyle_qmark = False
            self._conn = self._connect_mariadb(parsed)
        else:
            raise ValueError(f"Unsupported SQL storage scheme: {scheme!r}")

        self._init_schema()


    @staticmethod
    def _sqlite_path_from_uri(parsed) -> str:
        """
        Interpret SQLite paths so that:

        - sqlite:///:memory: -> ':memory:' (in-memory DB)
        - sqlite:///relative.db -> 'relative.db' (relative to CWD)
        - sqlite:////absolute/path.db -> '/absolute/path.db' (absolute)

        This prevents accidental writes to the filesystem root ('/relative.db').
        """
        
        if parsed.path in ("", "/", "/:memory:"):
            return ":memory:"

        p = parsed.path

        if (parsed.netloc or "") == "" and p.startswith("/") and not p.startswith("//"):
            p = p[1:]

        return p

    @staticmethod
    def _connect_mariadb(parsed) -> Any:
        username = unquote(parsed.username) if parsed.username else ""
        password = unquote(parsed.password) if parsed.password else ""
        host = parsed.hostname or "localhost"
        port = parsed.port or 3306
        database = (parsed.path or "").lstrip("/")
        conn = mariadb.connect(
            user=username,
            password=password,
            host=host,
            port=port,
            database=database,
            autocommit=True,
        )
        return conn

    def _init_schema(self) -> None:
        if self._db_type == "sqlite":
            create = (
                "CREATE TABLE IF NOT EXISTS telegram_messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  chat_id INTEGER,"
                "  user_id INTEGER,"
                "  user_name TEXT,"
                "  message_id INTEGER,"
                "  text TEXT,"
                "  message_type TEXT,"
                "  date TEXT,"
                "  reply_to INTEGER,"
                "  entities TEXT,"
                "  full_json TEXT"
                ");"
            )
            idx1 = "CREATE INDEX IF NOT EXISTS idx_tm_chat_id ON telegram_messages (chat_id);"
            idx2 = "CREATE INDEX IF NOT EXISTS idx_tm_user_id ON telegram_messages (user_id);"
            idx3 = "CREATE INDEX IF NOT EXISTS idx_tm_date ON telegram_messages (date);"
            with self._lock:
                cur = self._conn.cursor()
                try:
                    cur.execute(create)
                    cur.execute(idx1)
                    cur.execute(idx2)
                    cur.execute(idx3)
                finally:
                    cur.close()
                self._conn.commit()
        else:
            create = (
                "CREATE TABLE IF NOT EXISTS telegram_messages ("
                "  id BIGINT PRIMARY KEY AUTO_INCREMENT,"
                "  chat_id BIGINT,"
                "  user_id BIGINT,"
                "  user_name VARCHAR(255),"
                "  message_id BIGINT,"
                "  text LONGTEXT,"
                "  message_type VARCHAR(32),"
                "  date VARCHAR(64),"
                "  reply_to BIGINT,"
                "  entities LONGTEXT,"
                "  full_json LONGTEXT"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
            )
            idx1 = "CREATE INDEX idx_tm_chat_id ON telegram_messages (chat_id);"
            idx2 = "CREATE INDEX idx_tm_user_id ON telegram_messages (user_id);"
            idx3 = "CREATE INDEX idx_tm_date ON telegram_messages (date);"
            with self._lock:
                cur = self._conn.cursor()
                try:
                    cur.execute(create)
                    try:
                        cur.execute(idx1)
                    except Exception:
                        pass
                    try:
                        cur.execute(idx2)
                    except Exception:
                        pass
                    try:
                        cur.execute(idx3)
                    except Exception:
                        pass
                finally:
                    cur.close()

    def _execute(self, sql: str, params: Tuple[Any, ...] = ()) -> None:
        """Execute a write statement under lock."""
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute(sql, params)
            finally:
                cur.close()

    def _query(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
        """Execute a read statement under lock and return rows."""
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
            finally:
                cur.close()
        return rows

    def _placeholder(self) -> str:
        return "?" if self._paramstyle_qmark else "%s"


    def save_update(self, data: Dict[str, Any]) -> None:
        chat_id = data.get("chat_id")
        user_id = data.get("user_id")
        user_name = data.get("user_name")
        message_id = data.get("message_id")
        text = data.get("text")
        message_type = data.get("message_type")
        date = data.get("date")
        reply_to = data.get("reply_to")
        entities_json = json.dumps(data.get("entities")) if data.get("entities") is not None else None
        full_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

        ph = self._placeholder()
        insert = (
            f"INSERT INTO telegram_messages "
            f"(chat_id, user_id, user_name, message_id, text, message_type, date, reply_to, entities, full_json) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph});"
        )

        params: Tuple[Any, ...] = (
            chat_id,
            user_id,
            user_name,
            message_id,
            text,
            message_type,
            date,
            reply_to,
            entities_json,
            full_json,
        )
        self._execute(insert, params)

        if self._db_type == "sqlite":
            with self._lock:
                self._conn.commit()

    def fetch_messages(self, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if chat_id is None:
            sql = "SELECT full_json FROM telegram_messages;"
            rows = self._query(sql)
        else:
            ph = self._placeholder()
            sql = f"SELECT full_json FROM telegram_messages WHERE chat_id = {ph};"
            rows = self._query(sql, (chat_id,))

        out: List[Dict[str, Any]] = []
        for (txt,) in rows:
            try:
                out.append(json.loads(txt))
            except Exception:
                continue
        return out
