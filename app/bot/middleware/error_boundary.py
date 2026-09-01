"""
Global error boundary for the Telegram bot.

Registered as python-telegram-bot's error handler. This is the single
choke point where "low-level error → logged with technical details →
safe user-facing response" (per the error-handling architecture) actually
happens, so individual handlers don't need try/except boilerplate for the
generic case. Handlers still catch and act on errors where they need
custom recovery behavior.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.core.exceptions import AppError, GENERIC_ERROR_MESSAGE
from app.core.logging import get_logger

logger = get_logger(__name__)


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    user_message = GENERIC_ERROR_MESSAGE

    if isinstance(error, AppError):
        user_message = error.user_message
        logger.warning("handled_app_error", extra={"error_type": type(error).__name__, "detail": str(error)})
    else:
        logger.error("unhandled_exception", exc_info=error)

    if isinstance(update, Update) and update.effective_chat is not None:
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=user_message)
        except Exception:
            logger.error("failed_to_send_error_message", exc_info=True)
