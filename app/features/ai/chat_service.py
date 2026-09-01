"""
ChatService: business logic for "user sends a message, gets an AI reply".

This is where Telegram-agnostic orchestration lives — it takes plain
values in (user id, username, text) and returns a plain value out (reply
text), so it can be unit tested with a fake AIService and fake repository,
no Telegram objects involved.
"""

from __future__ import annotations

from app.core.exceptions import InvalidInputError
from app.core.logging import get_logger
from app.features.ai.provider import AIMessage, MessageRole
from app.features.ai.service import AIService
from app.repositories.user_repository import UserRepository

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a helpful, concise assistant integrated into a Telegram bot. "
    "Keep answers focused and avoid unnecessary preamble."
)


class ChatService:
    def __init__(
        self,
        ai_service: AIService,
        user_repository: UserRepository,
        max_message_length: int,
    ) -> None:
        self._ai_service = ai_service
        self._user_repository = user_repository
        self._max_message_length = max_message_length

    async def handle_user_message(
        self, telegram_user_id: int, username: str | None, text: str
    ) -> str:
        self._validate_text(text)

        await self._user_repository.get_or_create(telegram_user_id, username)

        messages = [
            AIMessage(role=MessageRole.SYSTEM, content=_SYSTEM_PROMPT),
            AIMessage(role=MessageRole.USER, content=text),
        ]
        response = await self._ai_service.generate_reply(messages)

        await self._user_repository.increment_message_count(telegram_user_id)

        logger.info(
            "chat_message_handled",
            extra={"telegram_user_id": telegram_user_id, "provider": response.provider},
        )
        return response.text

    def _validate_text(self, text: str) -> None:
        stripped = text.strip()
        if not stripped:
            raise InvalidInputError("empty message", user_message="Please send a non-empty message.")
        if len(stripped) > self._max_message_length:
            raise InvalidInputError(
                "message too long",
                user_message=(
                    f"Your message is too long ({len(stripped)} characters). "
                    f"Please keep it under {self._max_message_length} characters."
                ),
            )
