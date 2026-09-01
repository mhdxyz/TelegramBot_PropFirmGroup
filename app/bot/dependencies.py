"""
Bundles the services handlers need, stored on `Application.bot_data` so
wiring stays in one typed place instead of stringly-typed dict lookups
scattered across handlers.

`core` is always present. `ai` is `None` whenever AI_ENABLED=false — this
is the mechanism that makes AI genuinely optional: the AI handler is never
registered in that case (see app/main.py), so `ai` is never dereferenced,
and nothing in this module or the normal bot handlers imports anything
Gemini-specific.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.security.authorization import Authorizer
from app.security.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from app.features.ai.chat_service import ChatService

_KEY = "dependencies"


@dataclass(frozen=True)
class CoreDependencies:
    authorizer: Authorizer
    rate_limiter: RateLimiter


@dataclass(frozen=True)
class AIDependencies:
    chat_service: "ChatService"


@dataclass(frozen=True)
class Dependencies:
    core: CoreDependencies
    ai: AIDependencies | None


def store(bot_data: dict, dependencies: Dependencies) -> None:
    bot_data[_KEY] = dependencies


def get(bot_data: dict) -> Dependencies:
    return bot_data[_KEY]
