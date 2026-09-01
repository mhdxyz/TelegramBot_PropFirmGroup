"""
AIService is deliberately tested against generic provider identifiers, not
just AIProviderName.GEMINI. Its fallback logic is provider-count-agnostic —
today's config only ever configures one provider (Gemini), but the service
itself supports N providers, and that's the behavior these tests protect,
independent of how many providers the project currently ships.
"""

from __future__ import annotations

import pytest

from app.core.config import AIProviderName
from app.core.exceptions import AITimeoutError, AllProvidersUnavailableError
from app.features.ai.provider import AIMessage, MessageRole
from app.features.ai.service import AIService
from tests.fakes import FakeAIProvider

MESSAGES = [AIMessage(role=MessageRole.USER, content="hello")]


async def test_uses_default_provider_when_no_preference_given():
    provider = FakeAIProvider("gemini", response_text="hi")
    service = AIService({AIProviderName.GEMINI: provider}, AIProviderName.GEMINI)

    response = await service.generate_reply(MESSAGES)

    assert response.text == "hi"
    assert response.provider == "gemini"


async def test_falls_back_to_second_provider_when_first_fails():
    failing = FakeAIProvider("provider-a", error=AITimeoutError("provider-a", "timed out"))
    healthy = FakeAIProvider("provider-b", response_text="fallback reply")
    service = AIService({"provider-a": failing, "provider-b": healthy}, "provider-a")

    response = await service.generate_reply(MESSAGES)

    assert response.text == "fallback reply"
    assert response.provider == "provider-b"
    assert len(failing.calls) == 1


async def test_raises_when_all_providers_fail():
    failing_a = FakeAIProvider("provider-a", error=AITimeoutError("provider-a", "down"))
    failing_b = FakeAIProvider("provider-b", error=AITimeoutError("provider-b", "down"))
    service = AIService({"provider-a": failing_a, "provider-b": failing_b}, "provider-a")

    with pytest.raises(AllProvidersUnavailableError):
        await service.generate_reply(MESSAGES)


async def test_preferred_provider_is_tried_first():
    provider_a = FakeAIProvider("provider-a", response_text="a reply")
    provider_b = FakeAIProvider("provider-b", response_text="b reply")
    service = AIService({"provider-a": provider_a, "provider-b": provider_b}, "provider-a")

    response = await service.generate_reply(MESSAGES, preferred_provider="provider-b")

    assert response.provider == "provider-b"
    assert len(provider_a.calls) == 0


def test_rejects_default_provider_without_implementation():
    with pytest.raises(ValueError):
        AIService({}, AIProviderName.GEMINI)
