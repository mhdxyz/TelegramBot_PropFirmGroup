"""
Centralized, validated configuration.

Everything sensitive comes from environment variables — never hard-coded.
Configuration is loaded once at startup and passed explicitly to whatever
needs it (dependency injection), rather than imported as a global from
random modules. This keeps every component's dependencies visible in its
constructor signature, which is what makes them mockable in tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class AIProviderName(str, Enum):
    """Only GEMINI is implemented today. Kept as an enum (rather than a
    bare string) so a second provider is a one-line addition here plus a
    new branch in features/ai/factory.py — nothing else needs to change
    shape."""

    GEMINI = "gemini"


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""


def _require(env: dict, key: str) -> str:
    value = env.get(key)
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {key}")
    return value


def _optional(env: dict, key: str, default: str) -> str:
    return env.get(key, default)


def _optional_int(env: dict, key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"Environment variable {key} must be an integer, got: {raw!r}") from exc


def _optional_float(env: dict, key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"Environment variable {key} must be a number, got: {raw!r}") from exc


def _optional_bool(env: dict, key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in ("true", "1", "yes", "on"):
        return True
    if normalized in ("false", "0", "no", "off"):
        return False
    raise ConfigurationError(f"Environment variable {key} must be a boolean (true/false), got: {raw!r}")


def _parse_id_list(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    try:
        return frozenset(int(part.strip()) for part in raw.split(",") if part.strip())
    except ValueError as exc:
        raise ConfigurationError(f"ALLOWED_TELEGRAM_USER_IDS must be comma-separated integers, got: {raw!r}") from exc


@dataclass(frozen=True)
class AIConfig:
    enabled: bool
    default_provider: AIProviderName
    gemini_api_key: str | None
    gemini_model: str
    request_timeout_seconds: float
    max_retries: int


@dataclass(frozen=True)
class SecurityConfig:
    allowed_user_ids: frozenset[int]
    admin_user_ids: frozenset[int]
    rate_limit_max_requests: int
    rate_limit_window_seconds: float
    max_message_length: int


@dataclass(frozen=True)
class DatabaseConfig:
    url: str


@dataclass(frozen=True)
class WebhookConfig:
    """Everything the webhook layer needs. `secret_token` is verified
    against Telegram's `X-Telegram-Bot-Api-Secret-Token` header on every
    incoming request — Telegram's own mechanism for authenticating that a
    request actually came from Telegram's servers, so we don't need to
    invent a bespoke scheme. `public_url`, when set, is used at startup to
    register the webhook with Telegram; when unset, webhook registration is
    assumed to be handled externally (e.g. by deployment tooling)."""

    path: str
    secret_token: str
    public_url: str | None
    max_payload_bytes: int


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    environment: str
    log_level: str
    ai: AIConfig
    security: SecurityConfig
    database: DatabaseConfig
    webhook: WebhookConfig

    @staticmethod
    def from_env(env: dict | None = None) -> "AppConfig":
        env = dict(os.environ if env is None else env)

        telegram_bot_token = _require(env, "TELEGRAM_BOT_TOKEN")

        ai_enabled = _optional_bool(env, "AI_ENABLED", False)

        default_provider_raw = _optional(env, "DEFAULT_AI_PROVIDER", AIProviderName.GEMINI.value)
        try:
            default_provider = AIProviderName(default_provider_raw)
        except ValueError as exc:
            valid = ", ".join(p.value for p in AIProviderName)
            raise ConfigurationError(
                f"DEFAULT_AI_PROVIDER must be one of [{valid}], got: {default_provider_raw!r}"
            ) from exc

        gemini_key = env.get("GEMINI_API_KEY")
        # GEMINI_API_KEY is only required when AI is actually enabled — this
        # is what lets the bot start with zero AI configuration when
        # AI_ENABLED=false, per the enable/disable requirement.
        if ai_enabled and not gemini_key:
            raise ConfigurationError("GEMINI_API_KEY is required when AI_ENABLED=true")

        webhook_secret = _require(env, "WEBHOOK_SECRET")

        return AppConfig(
            telegram_bot_token=telegram_bot_token,
            environment=_optional(env, "ENVIRONMENT", "development"),
            log_level=_optional(env, "LOG_LEVEL", "INFO"),
            ai=AIConfig(
                enabled=ai_enabled,
                default_provider=default_provider,
                gemini_api_key=gemini_key,
                gemini_model=_optional(env, "GEMINI_MODEL", "gemini-1.5-flash"),
                request_timeout_seconds=_optional_float(env, "AI_REQUEST_TIMEOUT_SECONDS", 30.0),
                max_retries=_optional_int(env, "AI_MAX_RETRIES", 2),
            ),
            security=SecurityConfig(
                allowed_user_ids=_parse_id_list(env.get("ALLOWED_TELEGRAM_USER_IDS")),
                admin_user_ids=_parse_id_list(env.get("ADMIN_TELEGRAM_USER_IDS")),
                rate_limit_max_requests=_optional_int(env, "RATE_LIMIT_MAX_REQUESTS", 10),
                rate_limit_window_seconds=_optional_float(env, "RATE_LIMIT_WINDOW_SECONDS", 60.0),
                max_message_length=_optional_int(env, "MAX_MESSAGE_LENGTH", 4000),
            ),
            database=DatabaseConfig(url=_optional(env, "DATABASE_URL", "sqlite+aiosqlite:///./bot.db")),
            webhook=WebhookConfig(
                path=_optional(env, "WEBHOOK_PATH", "/webhook"),
                secret_token=webhook_secret,
                public_url=env.get("WEBHOOK_URL") or None,
                max_payload_bytes=_optional_int(env, "WEBHOOK_MAX_PAYLOAD_BYTES", 1_000_000),
            ),
        )
