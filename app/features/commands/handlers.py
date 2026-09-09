from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.dependencies import get
from app.core.exceptions import AppError, InvalidInputError
from app.features.commands.service import LotteryData

LOTTERY_STATE = "lottery_state"
LOTTERY_FULL_NAME = "lottery_full_name"
LOTTERY_A_EMAIL = "lottery_a_email"


async def lottery_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return
    deps = get(context.application.bot_data)
    deps.core.authorizer.require_allowed(update.effective_user.id)
    existing = await deps.commands.command_service._lottery.get_registration(update.effective_user.id)
    if existing:
        await update.message.reply_text("You are already registered for the lottery.")
        return
    context.user_data[LOTTERY_STATE] = LOTTERY_FULL_NAME
    await update.message.reply_text("Lottery registration started. Please send your first and last name.")


async def lottery_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None or not update.message.text:
        return
    state = context.user_data.get(LOTTERY_STATE)
    if state not in {LOTTERY_FULL_NAME, LOTTERY_A_EMAIL, "lottery_b_email"}:
        return
    text = update.message.text.strip()
    if state == LOTTERY_FULL_NAME:
        context.user_data[LOTTERY_FULL_NAME] = text
        context.user_data[LOTTERY_STATE] = LOTTERY_A_EMAIL
        await update.message.reply_text("Now send the registration email you use at company A.")
        return
    if state == LOTTERY_A_EMAIL:
        context.user_data[LOTTERY_A_EMAIL] = text
        context.user_data[LOTTERY_STATE] = "lottery_b_email"
        await update.message.reply_text("Now send the registration email you use at company B.")
        return

    data = LotteryData(
        full_name=context.user_data.get(LOTTERY_FULL_NAME, ""),
        company_a_email=context.user_data.get(LOTTERY_A_EMAIL, ""),
        company_b_email=text,
    )
    try:
        await deps.commands.command_service.register_lottery(
            update.effective_user.id,
            update.effective_user.username,
            data,
        )
    except InvalidInputError as exc:
        await update.message.reply_text(exc.user_message)
        if "already registered" in exc.user_message:
            context.user_data.pop(LOTTERY_STATE, None)
        return
    except AppError as exc:
        await update.message.reply_text(exc.user_message)
        return
    except Exception:
        await update.message.reply_text("Lottery registration failed. No registration was saved. Please try again.")
        return

    context.user_data.pop(LOTTERY_STATE, None)
    context.user_data.pop(LOTTERY_FULL_NAME, None)
    context.user_data.pop(LOTTERY_A_EMAIL, None)
    await update.message.reply_text("Registration completed successfully. Good luck!")


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
    await content_command(update, context, "books_and_resources", "Books and Resources")
