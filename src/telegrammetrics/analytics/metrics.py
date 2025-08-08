# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _coalesce_ts(msg: Dict[str, Any]) -> Optional[str]:
    """
    Return ISO timestamp from 'date' or 'ts' field if present.
    """
    ts = msg.get("date") or msg.get("ts")
    if not ts or not isinstance(ts, str):
        return None
    return ts


def calculate_top_users(messages: Sequence[Dict[str, Any]], top_n: int = 5) -> List[Tuple[int, str, int]]:
    """
    Compute top-N users by message count.

    Returns: list of tuples (user_id, user_name, count), sorted by count desc.
    """
    counts: Dict[int, Dict[str, Any]] = {}
    for m in messages:
        uid = m.get("user_id")
        if uid is None:
            continue
        uid = int(uid)
        d = counts.setdefault(uid, {"user_name": m.get("user_name", str(uid)), "count": 0})
        d["count"] += 1

    ordered = sorted(counts.items(), key=lambda kv: kv[1]["count"], reverse=True)[: max(top_n, 0)]
    return [(uid, data["user_name"], data["count"]) for uid, data in ordered]


def message_frequency(
    messages: Sequence[Dict[str, Any]],
    *,
    interval: str = "daily",
) -> List[Tuple[str, int]]:
    """
    Count messages per time bucket (daily or hourly).

    Returns: list of tuples (bucket_label, count) sorted by bucket label.
    - daily bucket example: "2025-11-09"
    - hourly bucket example: "2025-11-09 14"
    """
    if interval not in {"daily", "hourly"}:
        raise ValueError("interval must be 'daily' or 'hourly'")

    buckets: Dict[str, int] = defaultdict(int)
    for m in messages:
        ts = _coalesce_ts(m)
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        if interval == "daily":
            label = dt.date().isoformat()
        else:
            label = f"{dt.date().isoformat()} {dt.hour:02d}"
        buckets[label] += 1

    return sorted(buckets.items(), key=lambda kv: kv[0])


_WORD_SPLIT = re.compile(r"[^\w@/#]+")


def most_common_words(
    messages: Sequence[Dict[str, Any]],
    *,
    top_n: int = 20,
    stopwords: Optional[Iterable[str]] = None,
    include_hashtags: bool = True,
    include_mentions: bool = False,
) -> List[Tuple[str, int]]:
    """
    Compute most common tokens across message texts.

    Parameters
    ----------
    top_n : number of tokens to return
    stopwords : iterable of words to exclude (case-insensitive)
    include_hashtags : keep tokens starting with '#'
    include_mentions : if False, drop tokens starting with '@'
    """
    sw = set(w.lower() for w in (stopwords or _default_stopwords()))
    counts: Counter[str] = Counter()

    for m in messages:
        text = (m.get("text") or "").lower()
        if not text:
            continue
        text = re.sub(r"/\w+", " ", text)
        for tok in _WORD_SPLIT.split(text):
            if not tok:
                continue
            if tok.startswith("#") and not include_hashtags:
                continue
            if tok.startswith("@") and not include_mentions:
                continue
            if tok in sw:
                continue
            if tok.isdigit():
                continue
            counts[tok] += 1

    return counts.most_common(max(top_n, 0))


def command_usage(messages: Sequence[Dict[str, Any]]) -> List[Tuple[str, int]]:
    """
    Count occurrences of bot commands (e.g., '/start', '/help').

    Strategy:
    - prefer parsing message 'entities' where type == 'bot_command'
    - fallback: regex over the beginning of text segments
    """
    counts: Counter[str] = Counter()

    for m in messages:
        text = (m.get("text") or "").strip()
        entities = m.get("entities") or []

        if entities:
            for e in entities:
                if (e.get("type") or "").lower() != "bot_command":
                    continue
                offset = int(e.get("offset", 0))
                length = int(e.get("length", 0))
                cmd = text[offset : offset + length] if 0 <= offset < len(text) else ""
                if cmd:
                    counts[cmd.lower()] += 1
            continue

        for mobj in re.finditer(r"(^|\s)(/\w+)", text):
            cmd = mobj.group(2).lower()
            counts[cmd] += 1

    return counts.most_common()


def search_messages(
    messages: Sequence[Dict[str, Any]],
    query: str,
    *,
    case_sensitive: bool = False,
) -> List[Dict[str, Any]]:
    """
    Naive substring search over message text. Returns matching message dicts.
    """
    if not query:
        return []
    q = query if case_sensitive else query.lower()
    out: List[Dict[str, Any]] = []
    for m in messages:
        t = m.get("text") or ""
        hay = t if case_sensitive else t.lower()
        if q in hay:
            out.append(m)
    return out


def _default_stopwords() -> List[str]:
    return [
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "of",
        "to",
        "and",
        "or",
        "but",
        "on",
        "in",
        "for",
        "with",
        "at",
        "by",
        "from",
        "as",
        "that",
        "this",
        "these",
        "those",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "not",
        "no",
        "so",
        "if",
        "then",
        "than",
        "too",
        "very",
        "can",
        "could",
        "should",
        "would",
        "will",
        "just",
        "about",
        "into",
        "over",
        "under",
        "more",
        "most",
        "less",
        "least",
        "up",
        "down",
        "out",
        "off",
        "again",
        "once",
    ]
