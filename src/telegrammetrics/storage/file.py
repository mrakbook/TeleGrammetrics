# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from .base import StorageManager


class JSONFileStorage(StorageManager):
    """
    JSON Lines file-based storage backend.

    Each logged update is written as a single line containing a JSON object.
    This is human-readable and convenient for small to medium datasets or for
    debugging/auditing. For heavy analytics, prefer SQL.

    Notes
    -----
    - Appends synchronously; guarded by a lock for thread-safety.
    - Reading scans the file; for large files, consider rotating or migrating to SQL.
    """

    def __init__(self, file_path: str) -> None:
        self._path = file_path
        self._lock = threading.Lock()
        parent = os.path.dirname(os.path.abspath(self._path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        open(self._path, "a", encoding="utf-8").close()


    def save_update(self, data: Dict[str, Any]) -> None:
        line = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")

    def fetch_messages(self, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if chat_id is None or msg.get("chat_id") == chat_id:
                        results.append(msg)
        except FileNotFoundError:
            return []
        return results
