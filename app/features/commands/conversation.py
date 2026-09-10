from __future__ import annotations

from telegram import Update
from telegram.ext import CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters

from app.bot.dependencies import get
from app.core.exceptions import AppError, InvalidInputError
from app.features.commands.service import LotteryData


WAITING_NAME = 1
WAITING_COMPANY_A_EMAIL = 2
WAITING_COMPANY_B_EMAIL = 3

LOTTERY_FULL_NAME = "lottery_full_name"
LOTTERY_A_EMAIL = "lottery_a_email"


async def lottery_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    deps = get(context.application.bot_data)
    deps.core.authorizer.require_allowed(update.effective_user.id)

    if await deps.commands.command_service.is_lottery_registered(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "You are already registered for the lottery."
        )
        return ConversationHandler.END

    # Clear any stale values from a previous/aborted conversation.
    context.user_data.pop(LOTTERY_FULL_NAME, None)
    context.user_data.pop(LOTTERY_A_EMAIL, None)

    await update.message.reply_text(
        "Lottery registration started. Please send your first and last name."
    )

    return WAITING_NAME


async def lottery_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.message is None or not update.message.text:
        return WAITING_NAME

    text = update.message.text.strip()

    if not text or len(text.split()) < 2 or len(text) > 200:
        await update.message.reply_text(
            "Please enter a valid first and last name."
        )
        return WAITING_NAME

    context.user_data[LOTTERY_FULL_NAME] = text

    await update.message.reply_text(
        "Now send the registration email you use at company A."
    )

    return WAITING_COMPANY_A_EMAIL


async def lottery_company_a_email(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.message is None or not update.message.text:
        return WAITING_COMPANY_A_EMAIL

    text = update.message.text.strip()

    context.user_data[LOTTERY_A_EMAIL] = text

    await update.message.reply_text(
        "Now send the registration email you use at company B."
    )

    return WAITING_COMPANY_B_EMAIL


async def lottery_company_b_email(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if (
        update.effective_user is None
        or update.message is None
        or not update.message.text
    ):
        return WAITING_COMPANY_B_EMAIL

    deps = get(context.application.bot_data)

    data = LotteryData(
        full_name=context.user_data.get(LOTTERY_FULL_NAME, ""),
        company_a_email=context.user_data.get(LOTTERY_A_EMAIL, ""),
        company_b_email=update.message.text.strip(),
    )

    try:
        await deps.commands.command_service.register_lottery(
            update.effective_user.id,
            update.effective_user.username,
            data,
        )

    except InvalidInputError as exc:
        await update.message.reply_text(exc.user_message)
        return WAITING_COMPANY_B_EMAIL

    except AppError as exc:
        await update.message.reply_text(exc.user_message)
        return WAITING_COMPANY_B_EMAIL

    except Exception:
        await update.message.reply_text(
            "Lottery registration failed. "
            "No registration was saved. Please try again."
        )
        return WAITING_COMPANY_B_EMAIL

    context.user_data.pop(LOTTERY_FULL_NAME, None)
    context.user_data.pop(LOTTERY_A_EMAIL, None)

    await update.message.reply_text(
        "Registration completed successfully. Good luck!"
    )

    return ConversationHandler.END


async def lottery_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data.pop(LOTTERY_FULL_NAME, None)
    context.user_data.pop(LOTTERY_A_EMAIL, None)

    if update.message is not None:
        await update.message.reply_text(
            "Lottery registration cancelled."
        )

    return ConversationHandler.END


def build_lottery_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("lottery", lottery_start),
        ],
        states={
            WAITING_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lottery_name,
                ),
            ],
            WAITING_COMPANY_A_EMAIL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lottery_company_a_email,
                ),
            ],
            WAITING_COMPANY_B_EMAIL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lottery_company_b_email,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", lottery_cancel),
        ],
        allow_reentry=False,
        per_user=True,
        per_chat=True,
    )