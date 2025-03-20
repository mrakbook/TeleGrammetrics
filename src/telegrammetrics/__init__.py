# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

"""
Top-level package for TeleGrammetrics.

This package exposes the main orchestration class `TeleGrammetrics` and the
library version. Import it like:

    from telegrammetrics import TeleGrammetrics, __version__
"""

__all__ = ["TeleGrammetrics", "__version__"]

__version__ = "0.1.0"

from .core import TeleGrammetrics
