from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

WELCOME_TEXT = (
    "Welcome!\n\n"
    "Commands:\n"
    "/start - show this menu\n"
    "/Lottery - register for the lottery\n"
    "/Discount - view current discounts\n"
    "/Books_and_Resources - books and resources\n"
    "/help - show help"
)

HELP_TEXT = (
    "Use /Lottery to register for the lottery.\n"
    "Use /Discount for current discounts.\n"
    "Use /Books_and_Resources for books and resources.\n\n"
    "If you need help, contact the administrator."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(WELCOME_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT)
