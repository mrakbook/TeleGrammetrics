# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from .base import StorageManager


class MemoryStorage(StorageManager):
    """
    Simple in-memory storage backend.

    - Thread-safe for basic append + read operations via a single Lock.
    - Intended for tests and ephemeral runs; data is lost on process exit.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: List[Dict[str, Any]] = []

    def save_update(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._messages.append(dict(data))

    def fetch_messages(self, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if chat_id is None:
                return list(self._messages)
            return [m for m in self._messages if m.get("chat_id") == chat_id]
