from __future__ import annotations

import pytest

from app.core.config import AIProviderName
from app.core.exceptions import InvalidInputError
from app.features.ai.chat_service import ChatService
from app.features.ai.service import AIService
from tests.fakes import FakeAIProvider, FakeUserRepository


def make_chat_service(provider_response: str = "AI reply") -> tuple[ChatService, FakeUserRepository, FakeAIProvider]:
    provider = FakeAIProvider("gemini", response_text=provider_response)
    ai_service = AIService({AIProviderName.GEMINI: provider}, AIProviderName.GEMINI)
    user_repository = FakeUserRepository()
    chat_service = ChatService(ai_service, user_repository, max_message_length=100)
    return chat_service, user_repository, provider


async def test_handle_user_message_returns_ai_reply_and_updates_user():
    chat_service, user_repository, _ = make_chat_service("Hello there")

    reply = await chat_service.handle_user_message(telegram_user_id=1, username="alice", text="hi")

    assert reply == "Hello there"
    assert 1 in user_repository.users
    assert user_repository.increment_calls == [1]


async def test_rejects_empty_message():
    chat_service, _, _ = make_chat_service()

    with pytest.raises(InvalidInputError):
        await chat_service.handle_user_message(telegram_user_id=1, username=None, text="   ")


async def test_rejects_message_over_max_length():
    chat_service, _, _ = make_chat_service()

    with pytest.raises(InvalidInputError):
        await chat_service.handle_user_message(telegram_user_id=1, username=None, text="x" * 101)


async def test_does_not_increment_count_when_ai_call_fails():
    from app.core.exceptions import AITimeoutError

    provider = FakeAIProvider("gemini", error=AITimeoutError("gemini", "down"))
    ai_service = AIService({AIProviderName.GEMINI: provider}, AIProviderName.GEMINI)
    user_repository = FakeUserRepository()
    chat_service = ChatService(ai_service, user_repository, max_message_length=100)

    with pytest.raises(Exception):
        await chat_service.handle_user_message(telegram_user_id=1, username=None, text="hi")

    assert user_repository.increment_calls == []
