from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.exceptions import InvalidInputError, RepositoryError
from app.repositories.command_repository import ContentRepository, LotteryRepository

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class LotteryData:
    full_name: str
    company_a_email: str
    company_b_email: str


class CommandService:
    """Application use-cases for normal bot commands; contains no AI dependency."""

    def __init__(self, lottery_repository: LotteryRepository, content_repository: ContentRepository) -> None:
        self._lottery = lottery_repository
        self._content = content_repository

    async def register_lottery(self, telegram_user_id: int, telegram_username: str | None, data: LotteryData) -> None:
        full_name = data.full_name.strip()
        company_a_email = data.company_a_email.strip().lower()
        company_b_email = data.company_b_email.strip().lower()
        if not full_name or len(full_name) > 200:
            raise InvalidInputError("invalid full name", user_message="Please enter a valid first and last name.")
        if not _EMAIL_RE.fullmatch(company_a_email) or not _EMAIL_RE.fullmatch(company_b_email):
            raise InvalidInputError("invalid email", user_message="Please enter valid email addresses.")
        try:
            await self._lottery.create_registration(
                telegram_user_id=telegram_user_id,
                full_name=full_name,
                company_a_email=company_a_email,
                company_b_email=company_b_email,
                telegram_username=telegram_username,
            )
        except RepositoryError as exc:
            if "already exists" in str(exc):
                raise InvalidInputError("duplicate lottery registration", user_message="You are already registered for the lottery.") from exc
            raise

    async def get_content(self, key: str) -> str | None:
        return await self._content.get_content(key)

    async def set_content(self, key: str, content: str) -> None:
        value = content.strip()
        if not value:
            raise InvalidInputError("empty content", user_message="The content cannot be empty.")
        if len(value) > 4000:
            raise InvalidInputError("content too long", user_message="The content is too long. Please keep it under 4000 characters.")
        await self._content.set_content(key, value)
