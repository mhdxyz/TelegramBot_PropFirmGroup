"""
Verifies the actual enable/disable mechanism: which handler gets
registered and whether AI dependencies get constructed, driven purely by
AI_ENABLED. No network call happens here — `Application.builder().build()`
does not contact Telegram; only `.initialize()` would, and these tests
never call it.

Requires `python-telegram-bot` to be installed; run via `pytest`.
"""

from __future__ import annotations

import dataclasses

import pytest
from telegram.ext import MessageHandler

from app.bot import dependencies
from app.bot.handlers.fallback import ai_disabled_handler
from app.core.config import AppConfig, ConfigurationError
from app.database.connection import Database
from app.features.ai.handler import ai_message_handler
from app.main import _build_telegram_application


def _text_handler_callback(application):
    for group_handlers in application.handlers.values():
        for handler in group_handlers:
            if isinstance(handler, MessageHandler):
                return handler.callback
    raise AssertionError("No MessageHandler registered")


def test_ai_disabled_registers_fallback_handler_and_no_ai_deps():
    config = AppConfig.from_env(
        {"TELEGRAM_BOT_TOKEN": "dummy", "WEBHOOK_SECRET": "s", "AI_ENABLED": "false"}
    )
    database = Database(":memory:")

    application = _build_telegram_application(config, database)

    assert _text_handler_callback(application) is ai_disabled_handler
    deps = dependencies.get(application.bot_data)
    assert deps.ai is None
    assert deps.core is not None


def test_ai_enabled_registers_ai_handler_and_builds_ai_deps():
    config = AppConfig.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "dummy",
            "WEBHOOK_SECRET": "s",
            "AI_ENABLED": "true",
            "GEMINI_API_KEY": "fake-key",
        }
    )
    database = Database(":memory:")

    application = _build_telegram_application(config, database)

    assert _text_handler_callback(application) is ai_message_handler
    deps = dependencies.get(application.bot_data)
    assert deps.ai is not None
    assert deps.ai.chat_service is not None


def test_ai_enabled_without_provider_credentials_fails_fast():
    config = AppConfig.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "dummy",
            "WEBHOOK_SECRET": "s",
            "AI_ENABLED": "true",
            "GEMINI_API_KEY": "fake-key",
        }
    )
    # Simulate a config object that somehow reached this point without a key
    # (e.g. constructed directly rather than via from_env) — the wiring code
    # itself must still refuse to silently proceed with a disabled AI.
    config = dataclasses.replace(config, ai=dataclasses.replace(config.ai, gemini_api_key=None))
    database = Database(":memory:")

    with pytest.raises(ConfigurationError):
        _build_telegram_application(config, database)
