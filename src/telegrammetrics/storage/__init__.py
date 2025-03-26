# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

"""
Storage package facade.

This module exposes:
- `StorageManager`: the abstract interface all backends must implement
- `create_storage(storage_uri)`: a small factory to construct backends from a URI

Supported URIs
--------------
- None                                    -> JSONL file "telegram_metrics.jsonl" (sensible default)
- "memory"                                -> in-memory storage (ephemeral)
- "file:///absolute/or/relative/path"     -> JSONL file-based storage
- "sqlite:///path/to/file.db"             -> SQLite database
- "mariadb://user:pass@host:port/dbname"  -> MariaDB (or "mysql://...")
- "mongodb://user:pass@host:port/dbname"  -> MongoDB backend
"""

from typing import Optional

from .base import StorageManager

__all__ = ["StorageManager", "create_storage"]


def create_storage(storage_uri: Optional[str]) -> StorageManager:
    """
    Factory to construct a storage backend based on a URI-ish string.

    Parameters
    ----------
    storage_uri:
        None or "memory", "file://...", "sqlite://...", "mariadb://...", "mysql://...", "mongodb://..."

    Returns
    -------
    StorageManager
        A concrete storage backend instance.

    Raises
    ------
    ValueError
        If the scheme is unsupported.
    ImportError
        If a required backend module is not available.
    NotImplementedError
        For scaffolded backends not yet implemented.
    """
    if storage_uri is None:
        try:
            from .file import JSONFileStorage
        except Exception as exc:
            class _InlineMemoryStorage(StorageManager):
                def __init__(self) -> None:
                    self._msgs = []

                def save_update(self, data: dict) -> None:
                    self._msgs.append(dict(data))

                def fetch_messages(self, chat_id: int = None):
                    if chat_id is None:
                        return list(self._msgs)
                    return [m for m in self._msgs if m.get("chat_id") == chat_id]

            return _InlineMemoryStorage()
        else:
            return JSONFileStorage("telegram_metrics.jsonl")

    uri = str(storage_uri).strip()
    lo = uri.lower()

    if lo == "memory" or lo.startswith("memory://"):
        class _InlineMemoryStorage(StorageManager):
            def __init__(self) -> None:
                self._msgs = []

            def save_update(self, data: dict) -> None:
                self._msgs.append(dict(data))

            def fetch_messages(self, chat_id: int = None):
                if chat_id is None:
                    return list(self._msgs)
                return [m for m in self._msgs if m.get("chat_id") == chat_id]

        return _InlineMemoryStorage()

    if lo.startswith("file://"):
        try:
            from .file import JSONFileStorage
        except Exception as exc:
            raise ImportError(
                "File storage backend is not available. Ensure src/telegrammetrics/storage/file.py exists."
            ) from exc
        path = uri[len("file://") :]
        return JSONFileStorage(path)

    if lo.startswith("sqlite://") or lo.startswith("mariadb://") or lo.startswith("mysql://"):
        try:
            from .sql import SQLStorage
        except Exception as exc:
            raise ImportError(
                "SQL storage backend is not available. Ensure src/telegrammetrics/storage/sql.py exists "
                "and required drivers are installed (e.g., mariadb)."
            ) from exc
        return SQLStorage(uri)

    if lo.startswith("mongodb://") or lo.startswith("mongo://"):
        try:
            from .mongo import MongoStorage
        except Exception as exc:
            raise ImportError(
                "MongoDB backend is not available. Ensure pymongo is installed and "
                "src/telegrammetrics/storage/mongo.py exists."
            ) from exc
        return MongoStorage(uri)

    raise ValueError(f"Unsupported storage URI: {storage_uri!r}")
