from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.dependencies import get


async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.effective_user is None or update.message is None:
        return

    deps = get(context.application.bot_data)

    if not deps.core.authorizer.is_admin(update.effective_user.id):
        await update.message.reply_text(
            "⛔ You are not authorized to use the admin panel."
        )
        return

    await update.message.reply_text(
        "🛡 Admin Panel\n\n"
        "Available commands:\n"
        "/discount <text> - Update discounts\n"
        "/books_and_resources <text> - Update books/resources"
    )