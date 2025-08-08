# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

"""
Moderation package.

Exports common filter primitives so users can do:

    from telegrammetrics.moderation import TextFilter, ContentFilter
"""

from .filters import ContentFilter, TextFilter

__all__ = ["ContentFilter", "TextFilter"]
