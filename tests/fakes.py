"""
Lightweight fakes used across tests instead of mocking frameworks.

These satisfy the AIProvider / UserRepository protocols directly, so tests
exercise real interface contracts rather than mock configuration.
"""

from __future__ import annotations

from app.core.exceptions import AIProviderError
from app.features.ai.provider import AIMessage, AIResponse
from app.repositories.user_repository import User


class FakeAIProvider:
    def __init__(self, name: str, *, response_text: str | None = None, error: AIProviderError | None = None) -> None:
        self.name = name
        self._response_text = response_text
        self._error = error
        self.calls: list[list[AIMessage]] = []

    async def generate_reply(self, messages: list[AIMessage]) -> AIResponse:
        self.calls.append(messages)
        if self._error is not None:
            raise self._error
        return AIResponse(text=self._response_text or "fake reply", provider=self.name, model="fake-model")


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}
        self.increment_calls: list[int] = []

    async def get_or_create(self, telegram_user_id: int, username: str | None) -> User:
        if telegram_user_id not in self.users:
            self.users[telegram_user_id] = User(telegram_user_id=telegram_user_id, username=username, message_count=0)
        return self.users[telegram_user_id]

    async def increment_message_count(self, telegram_user_id: int) -> None:
        self.increment_calls.append(telegram_user_id)
