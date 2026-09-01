"""
Handles plain text messages by delegating to the AI feature's ChatService.

This handler is only registered with the Telegram Application when
AI_ENABLED=true (see app/main.py) — that's the actual enable/disable
mechanism, not a runtime `if` check buried in here. When AI is disabled,
this module is still importable (it has no Gemini import of its own) but
is simply never wired up, so no AI code path executes.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.bot import dependencies
from app.bot.middleware.guards import enforce_access


async def ai_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or message.text is None or update.effective_user is None:
        return

    deps = dependencies.get(context.bot_data)
    if deps.ai is None:
        # Defensive guard: should be unreachable, since this handler is only
        # registered when AI is enabled. Kept explicit rather than silently
        # doing nothing, so a wiring mistake fails loudly instead of hanging.
        raise RuntimeError("ai_message_handler invoked while AI feature is disabled")

    user = update.effective_user
    enforce_access(user.id, deps.core.authorizer, deps.core.rate_limiter)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    reply_text = await deps.ai.chat_service.handle_user_message(
        telegram_user_id=user.id,
        username=user.username,
        text=message.text,
    )
    await message.reply_text(reply_text)
