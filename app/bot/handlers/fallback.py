"""
Registered instead of the AI handler when AI_ENABLED=false, so plain text
messages still get a clear response rather than being silently ignored.
This is a normal-bot concern (user-facing behavior), not an AI concern —
it has no dependency on the AI feature module.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

AI_DISABLED_TEXT = "AI replies are currently turned off. Try /help to see what's available."


async def ai_disabled_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        await update.message.reply_text(AI_DISABLED_TEXT)
