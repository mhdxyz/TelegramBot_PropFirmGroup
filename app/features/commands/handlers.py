from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.dependencies import get
from app.core.exceptions import AppError, InvalidInputError
from app.features.commands.service import LotteryData



async def content_command(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, label: str) -> None:
    if update.effective_user is None or update.message is None:
        return
    deps = get(context.application.bot_data)
    deps.core.authorizer.require_allowed(update.effective_user.id)
    if context.args:
        if not deps.core.authorizer.is_admin(update.effective_user.id):
            await update.message.reply_text("Only an administrator can update this content.")
            return
        try:
            await deps.commands.command_service.set_content(key, " ".join(context.args))
            await update.message.reply_text(f"{label} updated successfully.")
        except AppError as exc:
            await update.message.reply_text(exc.user_message)
        return
    content = await deps.commands.command_service.get_content(key)
    await update.message.reply_text(content or f"No {label.lower()} are available yet.")


async def discount_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await content_command(update, context, "discount", "Discounts")


async def books_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await content_command(update, context, "resources", "Books and Resources")
