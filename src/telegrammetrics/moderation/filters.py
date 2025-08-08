# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

import re
from typing import Any, Iterable, Optional


class ContentFilter:
    """
    Base class for content moderation filters.

    A filter inspects an incoming update/message and decides whether it matches.
    If it matches, the `action` field indicates what to do (e.g., "delete", "warn").

    Subclasses must implement `matches(update_obj) -> bool`.
    """

    def __init__(self, name: str, action: str = "delete", description: str = "") -> None:
        self.name = name
        self.action = action
        self.description = description

    def matches(self, update_obj: Any) -> bool:
        """
        Return True if this filter should trigger on the provided update object.

        `update_obj` can be:
          - python-telegram-bot Update (preferred)
          - Telethon event (NewMessage)
          - a plain dict or object as long as a text can be derived
        """
        raise NotImplementedError("Subclasses must implement matches()")


class TextFilter(ContentFilter):
    """
    A text-based filter matching against keywords and/or a regex pattern.

    Examples
    --------
    # Delete messages containing 'spam' or 'scam'
    TextFilter(name="no_spam", keywords=["spam", "scam"], action="delete")

    # Warn on links to certain TLDs
    TextFilter(name="warn_ru_cn", pattern=r"http[s]?://.*\\.(ru|cn)", action="warn")
    """

    def __init__(
        self,
        name: str,
        keywords: Optional[Iterable[str]] = None,
        pattern: Optional[str] = None,
        action: str = "delete",
        description: str = "",
    ) -> None:
        super().__init__(name=name, action=action, description=description)
        self._keywords = [k.lower() for k in (keywords or [])]
        self._regex = re.compile(pattern) if pattern else None

    @staticmethod
    def _extract_text(update_obj: Any) -> str:
        """
        Attempt to extract message text from common update shapes.

        Supports:
          - python-telegram-bot Update: update.effective_message.{text|caption}
          - Telethon event: event.message.{message|text|raw_text}
          - plain dict with 'text'
        """
        msg = getattr(update_obj, "effective_message", None)
        if msg is not None:
            return (getattr(msg, "text", None) or getattr(msg, "caption", None) or "") or ""

        if hasattr(update_obj, "message"):
            tele_msg = getattr(update_obj, "message", None)
            if tele_msg is not None:
                t = getattr(tele_msg, "message", None) or getattr(tele_msg, "text", None) or getattr(
                    tele_msg, "raw_text", None
                )
                return t or ""

        if isinstance(update_obj, dict):
            v = update_obj.get("text")
            return v or ""

        return str(update_obj) if update_obj is not None else ""


    def matches(self, update_obj: Any) -> bool:
        text = self._extract_text(update_obj)
        if not text:
            return False

        t_lower = text.lower()

        for kw in self._keywords:
            if kw and kw in t_lower:
                return True

        if self._regex and self._regex.search(text):
            return True

        return False
