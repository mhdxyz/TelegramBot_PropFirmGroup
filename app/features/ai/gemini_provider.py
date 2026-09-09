from __future__ import annotations

import asyncio
from typing import Any

from google import genai
from google.genai import types

from app.core.exceptions import (
    AIAuthError,
    AIInvalidResponseError,
    AIRateLimitError,
    AITimeoutError,
)
from app.core.logging import get_logger
from app.features.ai.provider import AIMessage, AIResponse, MessageRole
from app.features.ai.prompts import DOMAIN_SYSTEM_INSTRUCTION


logger = get_logger(__name__)


class GeminiProvider:
    """AIProvider implementation backed by the Google Gemini API."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        file_search_store_name: str | None,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        if not api_key:
            raise AIAuthError(
                self.name,
                "GEMINI_API_KEY is not configured",
            )

        self._model_name = model
        self._file_search_store_name = file_search_store_name
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)

        self._client = genai.Client(api_key=api_key)

    async def generate_reply(
        self,
        messages: list[AIMessage],
    ) -> AIResponse:
        """
        Generate a Gemini response.

        The application-level conversation history is converted to
        Gemini Content objects.

        The domain/system instruction is provided separately through
        GenerateContentConfig.

        If a File Search Store is configured, Gemini can retrieve
        relevant knowledge from that store.
        """

        contents = self._build_contents(messages)

        if not contents:
            raise AIInvalidResponseError(
                self.name,
                "No user/assistant messages to send",
            )

        config = self._build_generation_config()

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._client.models.generate_content,
                        model=self._model_name,
                        contents=contents,
                        config=config,
                    ),
                    timeout=self._timeout_seconds,
                )

                return self._parse_response(result)

            
            except asyncio.TimeoutError as exc:
                last_error = exc

                print("\n========== GEMINI ERROR ==========")
                print(f"Type: {type(exc).name}")
                print(f"Error: {exc!r}")
                print("==================================\n")

                logger.warning(
                    "gemini_request_failed",
                    extra={
                        "attempt": attempt,
                        "model": self._model_name,
                        "error_type": type(exc).name,
                        "error": str(exc),
                    },
                )

                if attempt < self._max_retries:
                    await self._backoff(attempt)
                    continue

                raise AITimeoutError(
                    self.name,
                    (
                        f"Gemini request timed out after "
                        f"{self._timeout_seconds}s"
                    ),
                ) from exc

            except Exception as exc:
                last_error = exc


                print("\n========== GEMINI ERROR ==========")
                print(f"Type: {type(exc).__name__}")
                print(f"Error: {exc!r}")
                print("==================================\n")

                logger.warning(
                    "gemini_request_failed",
                    extra={
                        "attempt": attempt,
                        "model": self._model_name,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )

                if self._is_auth_error(exc):
                    raise AIAuthError(
                        self.name,
                        str(exc),
                    ) from exc

                if self._is_rate_limit_error(exc):
                    if attempt < self._max_retries:
                        await self._backoff(attempt)
                        continue

                    raise AIRateLimitError(
                        self.name,
                        str(exc),
                    ) from exc

                if self._is_invalid_request_error(exc):
                    raise AIInvalidResponseError(
                        self.name,
                        str(exc),
                    ) from exc

                if self._is_retryable_error(exc):
                    if attempt < self._max_retries:
                        await self._backoff(attempt)
                        continue

                    raise AITimeoutError(
                        self.name,
                        str(exc),
                    ) from exc

                raise AIInvalidResponseError(
                    self.name,
                    (
                        f"Gemini request failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                ) from exc

        raise AITimeoutError(
            self.name,
            (
                str(last_error)
                if last_error
                else "Gemini request failed"
            ),
        )

    def _build_generation_config(self) -> types.GenerateContentConfig:
        """
        Build Gemini generation configuration.

        System instruction controls the assistant's domain and behavior.

        File Search is added only when a valid File Search Store is
        configured.
        """

        tools: list[types.Tool] = []

        if self._file_search_store_name:
            tools.append(
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[
                            self._file_search_store_name
                        ]
                    )
                )
            )

        return types.GenerateContentConfig(
            system_instruction=DOMAIN_SYSTEM_INSTRUCTION,
            tools=tools or None,
            
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
                ),
            )

    @staticmethod
    def _build_contents(
        messages: list[AIMessage],
    ) -> list[types.Content]:
        """
        Convert application AIMessage objects to Gemini Content objects.

        SYSTEM messages are intentionally excluded because the system
        instruction is controlled centrally by prompts.py.
        """

        contents: list[types.Content] = []

        for message in messages:
            if message.role == MessageRole.SYSTEM:
                continue

            if message.role == MessageRole.USER:
                role = "user"

            elif message.role == MessageRole.ASSISTANT:
                role = "model"

            else:
                raise AIInvalidResponseError(
                    "gemini",
                    f"Unsupported message role: {message.role}",
                )

            contents.append(
                types.Content(
                    role=role,
                    parts=[
                        types.Part.from_text(
                            text=message.content,
                        )
                    ],
                )
            )

        return contents

    def _parse_response(
        self,
        result: Any,
    ) -> AIResponse:
        """Convert Gemini response into the application's AIResponse."""

        try:
            text = result.text

        except (ValueError, AttributeError) as exc:
            logger.error(
                "gemini_response_text_extraction_failed",
                extra={
                    "model": self._model_name,
                    "error": str(exc),
                },
            )

            raise AIInvalidResponseError(
                self.name,
                f"Could not extract text from Gemini response: {exc}",
            ) from exc

        if not text or not text.strip():
            raise AIInvalidResponseError(
                self.name,
                "Gemini response text was empty",
            )

        finish_reason = None

        try:
            candidates = getattr(result, "candidates", None)

            if candidates:
                finish_reason_value = getattr(
                    candidates[0],
                    "finish_reason",
                    None,
                )

                if finish_reason_value is not None:
                    finish_reason = str(finish_reason_value)

        except Exception:
            # Finish reason is optional metadata.
            finish_reason = None

        return AIResponse(
            text=text.strip(),
            provider=self.name,
            model=self._model_name,
            finish_reason=finish_reason,
        )

    @staticmethod
    def _is_auth_error(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)

        if status_code in (401, 403):
            return True

        message = str(exc).lower()

        return any(
            keyword in message
            for keyword in (
                "unauthenticated",
                "authentication",
                "unauthorized",
                "permission denied",
                "invalid api key",
                "api key",
                "forbidden",
            )
        )

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)

        if status_code == 429:
            return True

        message = str(exc).lower()

        return any(
            keyword in message
            for keyword in (
                "resource exhausted",
                "rate limit",
                "quota",
                "too many requests",
                "429",
            )
        )

    @staticmethod
    def _is_invalid_request_error(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)

        if status_code == 400:
            return True

        message = str(exc).lower()

        return any(
            keyword in message
            for keyword in (
                "invalid argument",
                "invalid request",
                "bad request",
                "400",
                "not found",
                "model not found",
                "unsupported model",
            )
        )

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)

        if status_code in (408, 429, 500, 502, 503, 504):
            return True

        message = str(exc).lower()

        return any(
            keyword in message
            for keyword in (
                "deadline exceeded",
                "timeout",
                "timed out",
                "service unavailable",
                "temporarily unavailable",
                "internal server error",
                "bad gateway",
                "gateway timeout",
                "connection reset",
                "connection refused",
                "connection error",
            )
        )

    @staticmethod
    async def _backoff(attempt: int) -> None:
        delay = min(2**attempt * 0.5, 8.0)

        logger.warning(
            "gemini_retry",
            extra={
                "attempt": attempt,
                "delay_seconds": delay,
            },
        )

        await asyncio.sleep(delay)