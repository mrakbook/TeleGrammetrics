#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Minimal example bot using TeleGrammetrics with python-telegram-bot (v20+).
#
# Usage:
#   export BOT_TOKEN="123456:ABC-DEF..."
#   python examples/example_bot.py
#
# The bot will:
#   - Log every incoming message to storage (SQLite by default here)
#   - Auto-log outgoing bot messages (via TeleGrammetrics PTB wrapper)
#   - Apply two moderation rules (delete 'spam'/'scam', warn on .ru/.cn links)
#   - Provide /stats to show top 3 active users in the current chat

from __future__ import annotations

import logging
import os
from typing import Final

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from telegrammetrics import TeleGrammetrics

# Config

LOG_LEVEL: Final = os.getenv("LOG_LEVEL", "INFO").upper()
BOT_TOKEN: Final = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("example_bot")


# TeleGrammetrics

# Use SQLite file for quick start. Switch to MariaDB/Mongo with:
#  storage_uri="mariadb://user:pass@host:3306/dbname"
#  storage_uri="mongodb://localhost:27017/telegram_metrics"
# NOTE: With the library's SQLite URI handling, "sqlite:///telegram_metrics.db" is relative.
telem = TeleGrammetrics(storage_uri="sqlite:///telegram_metrics.db", enable_moderation=True)

# Delete messages containing 'spam' or 'scam'
telem.add_text_filter(name="no_offensive", keywords=["spam", "scam"], action="delete")

# Warn (don't delete) when a link to .ru or .cn TLD appears
telem.add_text_filter(name="warn_ru_cn", pattern=r"http[s]?://.*\.(ru|cn)\b", action="warn")


# Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Hi! I'm a TeleGrammetrics example bot. Send /stats to see the top users."
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat:
        return
    # Use the async analytics helper to avoid blocking the event loop
    top = await telem.a_get_top_users(chat_id=chat.id, n=3)
    if not top:
        await update.effective_message.reply_text("No data yet. Say hi! 👋")
        return

    lines = [f"👥 Top {len(top)} active users:"]
    for i, u in enumerate(top, start=1):
        lines.append(f"{i}. {u['user_name']} — {u['message_count']} messages")
    await update.effective_message.reply_text("\n".join(lines))


# Main

def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        log.warning("Set your BOT_TOKEN environment variable before running the example.")
    app = Application.builder().token(BOT_TOKEN).build()

    # Auto-log outgoing bot messages by patching PTB Bot send methods
    telem.enable_outgoing_logging_ptb(app)

    # TeleGrammetrics logging/moderation should run first
    app.add_handler(MessageHandler(filters.ALL, telem.log_update), group=0)

    # Other bot commands/handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))

    log.info("Bot starting... Press Ctrl+C to stop.")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
