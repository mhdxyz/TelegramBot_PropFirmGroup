"""
Authorization: decides whether a given Telegram user may use the bot / a
given action.

Kept deliberately simple and centralized so every future role/permission
change happens in one place, not scattered across handlers. Enforcement
happens server-side only — Telegram user IDs are supplied by Telegram
itself and cannot be spoofed by the client without controlling the account.
"""

from __future__ import annotations

from app.core.exceptions import UnauthorizedError


class Authorizer:
    def __init__(self, allowed_user_ids: frozenset[int], admin_user_ids: frozenset[int]) -> None:
        # Empty allow-list means "everyone allowed" — an explicit choice so
        # the bot is usable out of the box in development. Operators who
        # want to restrict access set ALLOWED_TELEGRAM_USER_IDS.
        self._allowed_user_ids = allowed_user_ids
        self._admin_user_ids = admin_user_ids

    def is_allowed(self, telegram_user_id: int) -> bool:
        if not self._allowed_user_ids:
            return True
        return telegram_user_id in self._allowed_user_ids

    def is_admin(self, telegram_user_id: int) -> bool:
        return telegram_user_id in self._admin_user_ids

    def require_allowed(self, telegram_user_id: int) -> None:
        if not self.is_allowed(telegram_user_id):
            raise UnauthorizedError(telegram_user_id)

    def require_admin(self, telegram_user_id: int) -> None:
        if not self.is_admin(telegram_user_id):
            raise UnauthorizedError(telegram_user_id)
