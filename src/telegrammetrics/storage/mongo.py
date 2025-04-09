# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .base import StorageManager

try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
except Exception as exc:
    MongoClient = None
    Collection = None
    _IMPORT_ERROR = exc


class MongoStorage(StorageManager):
    """
    MongoDB storage backend.

    URI format
    ----------
    "mongodb://user:pass@host:27017/dbname"

    Notes
    -----
    - Uses collection "telegram_messages" in the provided database.
    - Ensures basic indexes on chat_id and user_id for common analytics queries.
    """

    def __init__(self, uri: str) -> None:
        if MongoClient is None:
            raise ImportError(
                "pymongo is required for MongoDB storage. Install with: pip install 'pymongo>=4.6'"
            ) from _IMPORT_ERROR

        parsed = urlparse(uri)
        dbname = (parsed.path or "").lstrip("/") or "telegrammetrics"

        self._client = MongoClient(uri)
        self._db = self._client[dbname]
        self._coll: Collection = self._db["telegram_messages"]

        try:
            self._coll.create_index("chat_id")
        except Exception:
            pass
        try:
            self._coll.create_index("user_id")
        except Exception:
            pass

    def save_update(self, data: Dict[str, Any]) -> None:
        doc = dict(data)
        try:
            self._coll.insert_one(doc)
        except Exception:
            pass

    def fetch_messages(self, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if chat_id is not None:
            query["chat_id"] = chat_id
        out: List[Dict[str, Any]] = []
        try:
            for doc in self._coll.find(query):
                doc.pop("_id", None)
                out.append(doc)
        except Exception:
            return []
        return out
