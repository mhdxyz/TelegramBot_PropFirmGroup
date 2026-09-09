"""Composition root for the bot."""

from __future__ import annotations

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.bot import dependencies
from app.bot.handlers.fallback import ai_disabled_handler
from app.bot.handlers.start import help_command, start_command
from app.bot.middleware.error_boundary import handle_error
from app.core.config import AppConfig, ConfigurationError
from app.core.logging import configure_logging, get_logger
from app.database.connection import Database, sqlite_path_from_url
from app.features.ai.chat_service import ChatService
from app.features.ai.factory import build_all_available_providers
from app.features.ai.handler import ai_message_handler
from app.features.ai.service import AIService
from app.features.commands.handlers import books_command, discount_command, lottery_command, lottery_input
from app.features.commands.service import CommandService
from app.repositories.command_repository import SQLiteCommandRepository
from app.repositories.user_repository import SQLiteUserRepository
from app.security.authorization import Authorizer
from app.security.rate_limiter import SlidingWindowRateLimiter
from app.webhook.app import create_app

logger = get_logger(__name__)


def _build_telegram_application(config: AppConfig, database: Database) -> Application:
    user_repository = SQLiteUserRepository(database)
    command_repository = SQLiteCommandRepository(database)
    command_service = CommandService(command_repository, command_repository)

    authorizer = Authorizer(config.security.allowed_user_ids, config.security.admin_user_ids)
    rate_limiter = SlidingWindowRateLimiter(
        max_requests=config.security.rate_limit_max_requests,
        window_seconds=config.security.rate_limit_window_seconds,
    )
    core_deps = dependencies.CoreDependencies(authorizer=authorizer, rate_limiter=rate_limiter)
    command_deps = dependencies.CommandDependencies(command_service=command_service)

    application = Application.builder().token(config.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("lottery", lottery_command))
    application.add_handler(CommandHandler("discount", discount_command))
    # Telegram command names cannot contain spaces; the menu label remains
    # "Books and Resources" while the executable command is /books_and_resources.
    application.add_handler(CommandHandler("books_and_resources", books_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_input), group=-1)

    ai_deps: dependencies.AIDependencies | None = None
    if config.ai.enabled:
        providers = build_all_available_providers(config.ai)
        if not providers:
            raise ConfigurationError("AI_ENABLED=true but no AI provider is configured (set GEMINI_API_KEY).")
        ai_service = AIService(providers, config.ai.default_provider)
        chat_service = ChatService(
            ai_service=ai_service,
            user_repository=user_repository,
            max_message_length=config.security.max_message_length,
        )
        ai_deps = dependencies.AIDependencies(chat_service=chat_service)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_message_handler))
        logger.info("ai_feature_enabled", extra={"provider": config.ai.default_provider.value})
    else:
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_disabled_handler))
        logger.info("ai_feature_disabled")

    dependencies.store(
        application.bot_data,
        dependencies.Dependencies(core=core_deps, commands=command_deps, ai=ai_deps),
    )
    application.add_error_handler(handle_error)
    return application


def create_asgi_app():
    try:
        config = AppConfig.from_env()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        raise SystemExit(1) from exc
    configure_logging(config.log_level)
    database = Database(sqlite_path_from_url(config.database.url))
    telegram_application = _build_telegram_application(config, database)
    return create_app(config, telegram_application, database)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_asgi_app(), host="0.0.0.0", port=8000)
