"""
Application-wide exception hierarchy.

Design rule: every exception that can surface to a Telegram user carries a
`user_message` that is safe to display. Technical details (original
exception, provider payloads, stack traces) are never put into
`user_message` — they belong in logs only. See core/logging.py and
bot/middleware/error_boundary.py for how the two are kept separate.
"""

from __future__ import annotations

GENERIC_ERROR_MESSAGE = "Something went wrong on our side. Please try again in a moment."


class AppError(Exception):
    """Base class for all application-defined errors."""

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or GENERIC_ERROR_MESSAGE


# --- User-caused errors: input was invalid, or the user isn't allowed to do this. ---


class UserFacingError(AppError):
    """Base for errors caused by the user, safe to explain plainly."""


class UnauthorizedError(UserFacingError):
    def __init__(self, telegram_user_id: int) -> None:
        super().__init__(
            f"Unauthorized access attempt by telegram_user_id={telegram_user_id}",
            user_message="You're not authorized to use this bot. Contact the administrator for access.",
        )


class RateLimitExceededError(UserFacingError):
    def __init__(self, telegram_user_id: int, retry_after_seconds: float) -> None:
        super().__init__(
            f"Rate limit exceeded by telegram_user_id={telegram_user_id}",
            user_message=(
                f"You're sending messages too quickly. "
                f"Please wait {retry_after_seconds:.0f}s and try again."
            ),
        )
        self.retry_after_seconds = retry_after_seconds


class InvalidInputError(UserFacingError):
    def __init__(self, reason: str, *, user_message: str) -> None:
        super().__init__(f"Invalid input: {reason}", user_message=user_message)


# --- AI provider errors: translated from provider SDK exceptions. ---


class AIProviderError(AppError):
    """Base for all AI-provider-related failures."""

    def __init__(self, provider: str, detail: str, *, user_message: str | None = None) -> None:
        super().__init__(f"[{provider}] {detail}", user_message=user_message)
        self.provider = provider


class AIAuthError(AIProviderError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            provider,
            detail,
            user_message="The AI service is temporarily misconfigured. We've been notified.",
        )


class AITimeoutError(AIProviderError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            provider,
            detail,
            user_message="The AI service took too long to respond. Please try again.",
        )


class AIRateLimitError(AIProviderError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            provider,
            detail,
            user_message="The AI service is busy right now. Please try again shortly.",
        )


class AIInvalidResponseError(AIProviderError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            provider,
            detail,
            user_message="The AI service returned an unexpected response. Please try again.",
        )


class AllProvidersUnavailableError(AIProviderError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            "ai-service",
            detail,
            user_message="The AI service is currently unavailable. Please try again later.",
        )


# --- Persistence errors ---


class RepositoryError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, user_message=GENERIC_ERROR_MESSAGE)
