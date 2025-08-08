# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageManager(ABC):
    """
    Abstract storage interface for TeleGrammetrics.

    Backends (e.g., in-memory, file, SQL, Mongo) must implement the synchronous
    methods `save_update` and `fetch_messages`. Asynchronous wrappers are provided
    to avoid blocking the event loop inside async handlers.
    """

    @abstractmethod
    def save_update(self, data: Dict[str, Any]) -> None:
        """
        Persist a structured log entry (one message/update).

        Parameters
        ----------
        data:
            JSON-serializable dictionary produced by TeleGrammetrics._build_log_entry.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_messages(self, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Return a list of logged messages. Backends may return messages for all chats
        or restrict to a specific chat if `chat_id` is provided.
        """
        raise NotImplementedError

    async def a_save_update(self, data: Dict[str, Any]) -> None:
        """
        Async wrapper around `save_update` using a thread pool to avoid blocking.
        """
        await asyncio.to_thread(self.save_update, data)

    async def a_fetch_messages(self, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Async wrapper around `fetch_messages` using a thread pool to avoid blocking.
        """
        return await asyncio.to_thread(self.fetch_messages, chat_id)
