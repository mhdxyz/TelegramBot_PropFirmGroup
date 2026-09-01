from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

WELCOME_TEXT = (
    "Hi! I'm an AI assistant bot. Send me any message and I'll reply using an AI model.\n\n"
    "Commands:\n"
    "/start - show this message\n"
    "/help - show usage help"
)

HELP_TEXT = (
    "Just send a text message and I'll reply.\n"
    "There's a limit on message length and how many messages you can send per minute — "
    "if you hit it, I'll let you know how long to wait."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)
