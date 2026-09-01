"""
Builds AIProvider instances from configuration.

Only Gemini is implemented at this stage (per project requirements), but
provider construction stays behind this factory and the `AIProvider`
protocol in `provider.py` — adding a second provider later means writing
one new file and one new branch here, not touching AIService, the AI
handler, or anything in the normal bot.
"""

from __future__ import annotations

from app.core.config import AIConfig, AIProviderName
from app.core.exceptions import AIAuthError
from app.features.ai.gemini_provider import GeminiProvider
from app.features.ai.provider import AIProvider


def build_provider(name: AIProviderName, config: AIConfig) -> AIProvider:
    if name == AIProviderName.GEMINI:
        if not config.gemini_api_key:
            raise AIAuthError("gemini", "GEMINI_API_KEY is not configured")
        return GeminiProvider(
            api_key=config.gemini_api_key,
            model=config.gemini_model,
            timeout_seconds=config.request_timeout_seconds,
            max_retries=config.max_retries,
        )

    raise ValueError(f"Unknown AI provider: {name}")


def build_all_available_providers(config: AIConfig) -> dict[AIProviderName, AIProvider]:
    """Build every provider that has credentials configured.

    Today this can only ever return Gemini (or nothing, if unconfigured).
    Kept as a dict/loop rather than a single direct call so that adding a
    second provider is additive: it starts showing up here automatically
    once a branch exists in `build_provider`.
    """
    providers: dict[AIProviderName, AIProvider] = {}
    for name in AIProviderName:
        try:
            providers[name] = build_provider(name, config)
        except AIAuthError:
            continue
    return providers
