# Copyright (c) 2025 Boris Karaoglanov
# TeleGrammetrics: Telegram Bot Analytics & Moderation Library
# Project: https://github.com/mrakbook/TeleGrammetrics
# SPDX-License-Identifier: MIT
# See AUTHORS for full list of contributors.

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from .storage import StorageManager, create_storage

try:
    from telegrammetrics.moderation.filters import ContentFilter, TextFilter
except Exception:
    import re

    class ContentFilter:
        def __init__(self, name: str, action: str = "delete") -> None:
            self.name = name
            self.action = action

        def matches(self, update_obj: Any) -> bool:
            return False

    class TextFilter(ContentFilter):
        def __init__(
            self,
            name: str,
            keywords: Optional[Iterable[str]] = None,
            pattern: Optional[str] = None,
            action: str = "delete",
        ) -> None:
            super().__init__(name, action)
            self._keywords = [k.lower() for k in (keywords or [])]
            self._regex = re.compile(pattern) if pattern else None

        def matches(self, update_obj: Any) -> bool:
            text = ""
            msg = getattr(update_obj, "effective_message", None)
            if msg is not None:
                text = getattr(msg, "text", None) or getattr(msg, "caption", "") or ""
            elif hasattr(update_obj, "text"):
                text = getattr(update_obj, "text", "") or ""
            text_l = text.lower()
            if any(k in text_l for k in self._keywords):
                return True
            if self._regex and self._regex.search(text):
                return True
            return False


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _maybe_await(result: Any) -> Any:
    """Await the value if it is awaitable; otherwise return it."""
    if inspect.isawaitable(result):
        return await result
    return result


def _safe_to_dict(entity: Any) -> Dict[str, Any]:
    """
    Convert a telegram entity (MessageEntity, etc.) to dict.
    Falls back to extracting common attributes if .to_dict() is unavailable.
    """
    if entity is None:
        return {}
    to_dict = getattr(entity, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:
            pass

    out: Dict[str, Any] = {}
    for attr in ("type", "offset", "length", "url", "user", "language"):
        if hasattr(entity, attr):
            val = getattr(entity, attr)
            out[attr] = getattr(val, "id", val) if attr == "user" else val
    return out


def _extract_media_ptb(message: Any) -> Optional[Dict[str, Any]]:
    """
    Build a compact media descriptor for PTB Message objects, when media is present.
    Returns None for pure text messages.
    """
    try:
        if getattr(message, "photo", None):
            best = None
            for s in message.photo:
                if best is None:
                    best = s
                else:
                    s0 = getattr(best, "file_size", 0) or 0
                    s1 = getattr(s, "file_size", 0) or 0
                    if s1 > s0:
                        best = s
            file_id = getattr(best, "file_id", None) if best is not None else None
            return {"type": "photo", "file_id": file_id}

        if getattr(message, "video", None):
            vid = message.video
            return {"type": "video", "file_id": getattr(vid, "file_id", None)}

        if getattr(message, "document", None):
            doc = message.document
            media: Dict[str, Any] = {"type": "document", "file_id": getattr(doc, "file_id", None)}
            mime = getattr(doc, "mime_type", None)
            if mime:
                media["mime_type"] = mime
            fname = getattr(doc, "file_name", None)
            if fname:
                media["file_name"] = fname
            return media

        if getattr(message, "sticker", None):
            stk = message.sticker
            media = {"type": "sticker", "file_id": getattr(stk, "file_id", None)}
            emo = getattr(stk, "emoji", None)
            if emo:
                media["emoji"] = emo
            return media
    except Exception:
        pass
    return None


def _build_log_entry_telethon(event: Any) -> Optional[Dict[str, Any]]:
    """
    Minimal Telethon event serializer (no hard Telethon import, uses duck-typing).
    Supports events.NewMessage; avoids network round-trips.
    """
    if event is None or not hasattr(event, "message"):
        return None

    msg = getattr(event, "message", None)
    if msg is None:
        return None

    entry: Dict[str, Any] = {
        "ts": _iso_now(),
        "bot_response": False,
    }

    chat_id = getattr(event, "chat_id", None)
    if chat_id is not None:
        entry["chat_id"] = chat_id

    sender_id = getattr(event, "sender_id", None)
    if sender_id is not None:
        entry["user_id"] = sender_id
        entry["sender_id"] = sender_id

    sender = getattr(event, "sender", None)
    if sender is not None:
        first = getattr(sender, "first_name", "") or ""
        last = getattr(sender, "last_name", "") or ""
        username = getattr(sender, "username", None)
        full_name = (first + " " + last).strip() or username
        if full_name:
            entry["user_name"] = full_name
            entry["sender_name"] = full_name

    entry["message_id"] = getattr(msg, "id", None)
    dt = getattr(msg, "date", None)
    entry["date"] = dt.isoformat() if dt is not None else None
    entry["timestamp"] = entry["date"]

    text = getattr(msg, "message", None) or getattr(msg, "raw_text", None) or ""
    entry["text"] = text

    if getattr(msg, "photo", None):
        entry["message_type"] = "photo"
    elif getattr(msg, "video", None):
        entry["message_type"] = "video"
    elif getattr(msg, "document", None) or getattr(msg, "media", None) is not None:
        entry["message_type"] = "document"
    else:
        entry["message_type"] = "text"

    rpl = getattr(msg, "reply_to_msg_id", None)
    if rpl is None:
        r = getattr(msg, "reply_to", None)
        rpl = getattr(r, "reply_to_msg_id", None) if r is not None else None
    if rpl is not None:
        entry["reply_to"] = rpl

    ents = getattr(msg, "entities", None) or []
    if ents:
        out: List[Dict[str, Any]] = []
        for e in ents:
            d: Dict[str, Any] = {}
            for k in ("offset", "length"):
                if hasattr(e, k):
                    d[k] = getattr(e, k)
            t = getattr(e, "type", None)
            d["type"] = str(t if t is not None else e.__class__.__name__)
            out.append(d)
        if out:
            entry["entities"] = out

    if all(k not in entry for k in ("chat_id", "user_id", "message_id", "text")):
        return None

    return entry


class TeleGrammetrics:
    """
    TeleGrammetrics orchestrates logging/persistence, analytics helpers,
    and optional content moderation for Telegram bots.

    Parameters
    ----------
    storage_uri:
        Location/driver for the storage backend, e.g.
        - "memory" (explicit)
        - "file:///path/to/logs.jsonl"
        - "sqlite:///path/to/metrics.db"
        - "mariadb://user:pass@host:3306/dbname"
        - "mongodb://user:pass@host:27017/dbname"

        If None, defaults to a local JSONL file "telegram_metrics.jsonl".

    enable_moderation:
        If True, incoming updates are checked by registered filters before logging.
    """

    def __init__(
        self,
        storage_uri: Optional[str] = None,
        *,
        enable_moderation: bool = False,
    ) -> None:
        self.storage: StorageManager = create_storage(storage_uri)
        self.enable_moderation: bool = bool(enable_moderation)
        self.filters: List[ContentFilter] = []


    def add_text_filter(
        self,
        *,
        name: str,
        keywords: Optional[Iterable[str]] = None,
        pattern: Optional[str] = None,
        action: str = "delete",
    ) -> None:
        """
        Register a text-based moderation rule.

        Example
        -------
        >>> tgm.add_text_filter(
        ...     name="block_spam",
        ...     keywords=["spam", "scam"],
        ...     action="delete",
        ... )
        """
        self.filters.append(TextFilter(name=name, keywords=keywords, pattern=pattern, action=action))

    async def _apply_moderation(self, update: Any, context: Any = None) -> bool:
        """
        Run all filters; execute actions as needed.

        Returns
        -------
        bool
            False if the message was handled (e.g., deleted) and should not be processed further.
            True if the message can continue to be processed/logged.

        Notes
        -----
        - PTB: after a 'delete' we raise ApplicationHandlerStop so downstream handlers do not run.
        - Telethon: after a 'delete' we return False to indicate the event was handled.
        """
        if not self.enable_moderation or not self.filters or update is None:
            return True


        is_ptb = hasattr(update, "effective_message")
        is_tele = (not is_ptb) and hasattr(update, "message")


        message = getattr(update, "effective_message", None)
        chat = getattr(update, "effective_chat", None)

        for filt in self.filters:
            try:
                if not filt.matches(update):
                    continue
            except Exception:
                continue

            action = getattr(filt, "action", "delete")

            if action == "delete":
                if is_ptb and message is not None:
                    try:
                        await _maybe_await(message.delete())
                    except Exception:
                        pass
                    try:
                        from telegram.ext import ApplicationHandlerStop
                    except Exception:
                        return False
                    else:
                        raise ApplicationHandlerStop

                if is_tele and hasattr(update, "delete"):
                    try:
                        await _maybe_await(update.delete())
                    except Exception:
                        pass
                    return False

            if action == "warn":
                warn_text = "⚠️ Please avoid posting that content."

                if is_ptb:
                    try:
                        if message is not None and hasattr(message, "reply_text"):
                            await _maybe_await(message.reply_text(warn_text))
                        elif context is not None and hasattr(context, "bot") and hasattr(chat, "id"):
                            await _maybe_await(context.bot.send_message(chat_id=chat.id, text=warn_text))
                    except Exception:
                        pass
                    continue

                if is_tele:
                    try:
                        if hasattr(update, "respond"):
                            await _maybe_await(update.respond(warn_text))
                        elif hasattr(update, "reply"):
                            await _maybe_await(update.reply(warn_text))
                    except Exception:
                        pass
                    continue

        return True


    def enable_outgoing_logging_ptb(self, app: Any) -> None:
        """
        Monkey-patch common PTB v20+ Bot send methods to auto-log outgoing messages.
        This provides the "automatic capture of outgoing responses" promised
        in the spec without requiring users to change their bot code.

        Supported methods: send_message, send_photo, send_document, send_video, send_sticker
        """
        bot = getattr(app, "bot", None)
        if bot is None or getattr(bot, "_tgm_outgoing_wrapped", False):
            return

        def _patch(method_name: str, msg_type: str, text_arg_name: str = "text", caption_fallback: bool = False):
            original = getattr(bot, method_name, None)
            if not callable(original):
                return

            async def _wrapped(*args, **kwargs):
                res = await original(*args, **kwargs)
                try:
                    chat_obj = getattr(res, "chat", None)
                    chat_id = getattr(chat_obj, "id", None) or kwargs.get("chat_id")
                    if caption_fallback:
                        text = getattr(res, "caption", None) or kwargs.get("caption", "")
                    else:
                        text = getattr(res, "text", None) or kwargs.get(text_arg_name, "")
                    extra: Optional[Dict[str, Any]] = None
                    if msg_type != "text":
                        media = _extract_media_ptb(res)
                        if media:
                            extra = {"media": media}
                    await self.log_bot_message(
                        chat_id=chat_id,
                        text=text or "",
                        message_id=getattr(res, "message_id", None),
                        reply_to_message_id=kwargs.get("reply_to_message_id"),
                        message_type=msg_type,
                        extra=extra,
                    )
                except Exception:
                    pass
                return res

            setattr(bot, method_name, _wrapped)

        _patch("send_message", "text", "text", caption_fallback=False)
        _patch("send_photo", "photo", "caption", caption_fallback=True)
        _patch("send_document", "document", "caption", caption_fallback=True)
        _patch("send_video", "video", "caption", caption_fallback=True)
        _patch("send_sticker", "sticker", "emoji", caption_fallback=False)

        setattr(bot, "_tgm_outgoing_wrapped", True)

    async def log_bot_message(
        self,
        *,
        chat_id: Optional[int],
        text: str = "",
        message_id: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
        message_type: str = "text",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an outgoing bot response (used internally by patched PTB methods,
        but can also be called manually if desired).
        """
        if chat_id is None:
            return
        entry: Dict[str, Any] = {
            "ts": _iso_now(),
            "bot_response": True,
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "message_type": message_type,
        }
        if reply_to_message_id is not None:
            entry["reply_to"] = reply_to_message_id
        if extra:
            for k, v in extra.items():
                if k not in entry:
                    entry[k] = v

        try:
            await self.storage.a_save_update(entry)
        except Exception:
            pass

    async def log_update(self, update: Any, context: Any = None) -> None:
        """
        PTB-first async handler (v20+) to moderate + log updates.
        Add as a high-priority (group=0) handler:

            app.add_handler(MessageHandler(filters.ALL, telem.log_update), group=0)
        """
        proceed = await self._apply_moderation(update, context)
        if not proceed:
            return

        entry = self._build_log_entry(update)
        if entry is None:
            return

        try:
            await self.storage.a_save_update(entry)
        except Exception:
            pass

    async def log_event(self, update_or_event: Any, context: Any = None) -> None:
        """
        Generic async logger that accepts either:
          - PTB Update (delegates to log_update)
          - Telethon events.NewMessage (duck-typed), with optional moderation

        This mirrors the spec's example:

            @client.on(events.NewMessage)
            async def handle_msg(event):
                await telem.log_event(event)
        """
        if hasattr(update_or_event, "effective_message"):
            await self.log_update(update_or_event, context)
            return

        proceed = await self._apply_moderation(update_or_event, None)
        if not proceed:
            return
        entry = _build_log_entry_telethon(update_or_event)
        if entry is None:
            return
        try:
            await self.storage.a_save_update(entry)
        except Exception:
            pass


    def get_top_users(self, *, chat_id: int, n: int = 5) -> List[Dict[str, Any]]:
        """
        Synchronous helper to compute top-N users by message count in a chat.
        """
        messages = self.storage.fetch_messages(chat_id=chat_id) or []
        return self._aggregate_top_users(messages, n=n)

    async def a_get_top_users(self, *, chat_id: int, n: int = 5) -> List[Dict[str, Any]]:
        """
        Async variant of `get_top_users`, suitable for async bot commands.
        """
        messages = await self.storage.a_fetch_messages(chat_id=chat_id)
        return self._aggregate_top_users(messages or [], n=n)


    @staticmethod
    def _aggregate_top_users(messages: List[Dict[str, Any]], *, n: int) -> List[Dict[str, Any]]:
        counts: Dict[int, Dict[str, Any]] = {}
        for m in messages:
            uid = m.get("user_id")
            if uid is None:
                continue
            d = counts.setdefault(int(uid), {"user_name": m.get("user_name", str(uid)), "count": 0})
            d["count"] += 1

        top = sorted(counts.items(), key=lambda kv: kv[1]["count"], reverse=True)[: max(n, 0)]
        return [
            {"user_id": uid, "user_name": data["user_name"], "message_count": data["count"]}
            for uid, data in top
        ]

    @staticmethod
    def _build_log_entry(update: Any) -> Optional[Dict[str, Any]]:
        """
        Extract a structured, JSON-serializable log entry from an incoming (PTB) update.

        The function is defensive and only relies on common PTB attributes.
        """
        if update is None:
            return None

        chat = getattr(update, "effective_chat", None)
        user = getattr(update, "effective_user", None)
        message = getattr(update, "effective_message", None)

        entry: Dict[str, Any] = {
            "ts": _iso_now(),
            "bot_response": False,
            "update_id": getattr(update, "update_id", None),
        }

        if chat is not None:
            entry["chat_id"] = getattr(chat, "id", None)
            entry["chat_title"] = getattr(chat, "title", None)

        if user is not None:
            uid = getattr(user, "id", None)
            full_name = getattr(user, "full_name", None)
            if not full_name:
                first = getattr(user, "first_name", "") or ""
                last = getattr(user, "last_name", "") or ""
                full_name = (first + " " + last).strip() or getattr(user, "username", None)
            entry["user_id"] = uid
            entry["user_name"] = full_name
            entry["sender_id"] = uid
            entry["sender_name"] = full_name

        if message is not None:
            entry["message_id"] = getattr(message, "message_id", None)
            msg_dt = getattr(message, "date", None)
            entry["date"] = msg_dt.isoformat() if msg_dt is not None else None
            entry["timestamp"] = entry["date"]

            text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
            entry["text"] = text

            msg_type = "text"
            if getattr(message, "photo", None):
                msg_type = "photo"
            elif getattr(message, "video", None):
                msg_type = "video"
            elif getattr(message, "sticker", None):
                msg_type = "sticker"
            elif getattr(message, "document", None):
                msg_type = "document"
            entry["message_type"] = msg_type

            reply_to = getattr(message, "reply_to_message", None)
            if reply_to is not None:
                entry["reply_to"] = getattr(reply_to, "message_id", None)

            entities = getattr(message, "entities", None) or []
            entry["entities"] = [_safe_to_dict(e) for e in entities] if entities else []

            media = _extract_media_ptb(message)
            if media:
                entry["media"] = media

            to_dict = getattr(message, "to_dict", None)
            if callable(to_dict):
                try:
                    entry["raw_message"] = to_dict()
                except Exception:
                    pass

        if all(k not in entry for k in ("chat_id", "user_id", "message_id", "text")):
            return None

        if not entry.get("entities"):
            entry.pop("entities", None)

        return entry
