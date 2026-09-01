from __future__ import annotations

import asyncio

import google.generativeai as genai
from google.api_core.exceptions import (
    DeadlineExceeded,
    GoogleAPIError,
    InvalidArgument,
    PermissionDenied,
    ResourceExhausted,
    ServiceUnavailable,
    Unauthenticated,
)

from app.core.exceptions import (
    AIAuthError,
    AIInvalidResponseError,
    AIRateLimitError,
    AITimeoutError,
)
from app.core.logging import get_logger
from app.features.ai.provider import AIMessage, AIResponse, MessageRole

logger = get_logger(__name__)

# Gemini has no "system" role in the chat history; system instructions are
# passed separately at model-construction time.
_GEMINI_ROLE_MAP = {MessageRole.USER: "user", MessageRole.ASSISTANT: "model"}


class GeminiProvider:
    """AIProvider implementation backed by the Google Gemini API."""

    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout_seconds: float, max_retries: int) -> None:
        genai.configure(api_key=api_key)
        self._model_name = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    async def generate_reply(self, messages: list[AIMessage]) -> AIResponse:
        system_instruction = next(
            (m.content for m in messages if m.role == MessageRole.SYSTEM), None
        )
        history = [
            {"role": _GEMINI_ROLE_MAP[m.role], "parts": [m.content]}
            for m in messages
            if m.role != MessageRole.SYSTEM
        ]
        if not history:
            raise AIInvalidResponseError(self.name, "No user/assistant messages to send")

        model = genai.GenerativeModel(self._model_name, system_instruction=system_instruction)
        *history_turns, last_turn = history

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                chat = model.start_chat(history=history_turns)
                result = await asyncio.to_thread(
                    chat.send_message,
                    last_turn["parts"][0],
                    request_options={"timeout": self._timeout_seconds},
                )
                return self._parse_response(result)
            except (Unauthenticated, PermissionDenied) as exc:
                raise AIAuthError(self.name, str(exc)) from exc
            except InvalidArgument as exc:
                raise AIInvalidResponseError(self.name, str(exc)) from exc
            except ResourceExhausted as exc:
                last_error = exc
                await self._backoff(attempt)
            except (DeadlineExceeded, ServiceUnavailable) as exc:
                last_error = exc
                await self._backoff(attempt)
            except GoogleAPIError as exc:
                last_error = exc
                await self._backoff(attempt)

        if isinstance(last_error, ResourceExhausted):
            raise AIRateLimitError(self.name, str(last_error))
        raise AITimeoutError(self.name, str(last_error) if last_error else "exhausted retries")

    def _parse_response(self, result) -> AIResponse:
        try:
            text = result.text
        except (ValueError, AttributeError) as exc:
            # `.text` raises if the response was blocked or has no candidates.
            raise AIInvalidResponseError(self.name, f"Could not extract text: {exc}") from exc
        if not text:
            raise AIInvalidResponseError(self.name, "Response text was empty")

        finish_reason = None
        if getattr(result, "candidates", None):
            finish_reason = str(result.candidates[0].finish_reason)

        return AIResponse(text=text, provider=self.name, model=self._model_name, finish_reason=finish_reason)

    @staticmethod
    async def _backoff(attempt: int) -> None:
        delay = min(2**attempt * 0.5, 8.0)
        logger.warning("gemini_retry", extra={"attempt": attempt, "delay_seconds": delay})
        await asyncio.sleep(delay)
