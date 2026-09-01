"""
AIService: the single entry point business logic uses to talk to "the AI".

It owns provider selection and fallback. Callers never see individual
providers — this is the seam where "add a provider" and "change fallback
policy" both live, isolated from everything else.
"""

from __future__ import annotations

from app.core.config import AIProviderName
from app.core.exceptions import AIProviderError, AllProvidersUnavailableError
from app.core.logging import get_logger
from app.features.ai.provider import AIMessage, AIProvider, AIResponse

logger = get_logger(__name__)


class AIService:
    def __init__(
        self,
        providers: dict[AIProviderName, AIProvider],
        default_provider: AIProviderName,
    ) -> None:
        if default_provider not in providers:
            raise ValueError(f"Default provider {default_provider} has no configured implementation")
        self._providers = providers
        self._default_provider = default_provider

    async def generate_reply(
        self, messages: list[AIMessage], *, preferred_provider: AIProviderName | None = None
    ) -> AIResponse:
        """Generate a reply, trying the preferred/default provider first and
        falling back to any other configured provider on failure.

        Fallback exists because a single provider outage shouldn't take the
        whole bot down when a second provider is configured. If only one
        provider is configured, this behaves like a direct call to it.
        """
        ordered = self._provider_order(preferred_provider)
        last_error: AIProviderError | None = None

        for provider_name in ordered:
            provider = self._providers[provider_name]
            try:
                return await provider.generate_reply(messages)
            except AIProviderError as exc:
                last_error = exc
                logger.error(
                    "ai_provider_failed",
                    extra={"provider": str(provider_name), "error": str(exc)},
                )
                continue

        detail = str(last_error) if last_error else "no providers configured"
        raise AllProvidersUnavailableError(detail)

    def _provider_order(self, preferred: AIProviderName | None) -> list[AIProviderName]:
        first = preferred if preferred in self._providers else self._default_provider
        rest = [name for name in self._providers if name != first]
        return [first, *rest]
