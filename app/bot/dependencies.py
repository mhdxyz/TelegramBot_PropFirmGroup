"""Typed dependency bundles for Telegram handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.security.authorization import Authorizer
from app.security.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from app.features.ai.chat_service import ChatService
    from app.features.commands.service import CommandService

_KEY = "dependencies"


@dataclass(frozen=True)
class CoreDependencies:
    authorizer: Authorizer
    rate_limiter: RateLimiter


@dataclass(frozen=True)
class CommandDependencies:
    command_service: "CommandService"


@dataclass(frozen=True)
class AIDependencies:
    chat_service: "ChatService"


@dataclass(frozen=True)
class Dependencies:
    core: CoreDependencies
    commands: CommandDependencies
    ai: AIDependencies | None


def store(bot_data: dict, dependencies: Dependencies) -> None:
    bot_data[_KEY] = dependencies


def get(bot_data: dict) -> Dependencies:
    return bot_data[_KEY]
