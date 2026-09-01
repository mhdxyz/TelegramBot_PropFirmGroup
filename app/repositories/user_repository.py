from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import aiosqlite

from app.core.exceptions import RepositoryError
from app.core.logging import get_logger
from app.database.connection import Database

logger = get_logger(__name__)


@dataclass(frozen=True)
class User:
    telegram_user_id: int
    username: str | None
    message_count: int


class UserRepository(Protocol):
    """Persistence contract for user records.

    Defined as a Protocol so services depend on this interface, not on
    SQLite/aiosqlite — a future PostgresUserRepository just needs to satisfy
    the same shape.
    """

    async def get_or_create(self, telegram_user_id: int, username: str | None) -> User: ...
    async def increment_message_count(self, telegram_user_id: int) -> None: ...


class SQLiteUserRepository:
    """Holds a reference to the `Database` wrapper, not a raw connection.

    This is deliberate: it lets `SQLiteUserRepository` be constructed before
    the database connection is actually opened (connection happens inside
    the ASGI lifespan, on the event loop the server will actually run on).
    Each method fetches `self._database.connection` at call time instead of
    caching it at construction time.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_or_create(self, telegram_user_id: int, username: str | None) -> User:
        connection = self._database.connection
        try:
            await connection.execute(
                """
                INSERT INTO users (telegram_user_id, username)
                VALUES (?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    username = excluded.username,
                    last_active_at = datetime('now')
                """,
                (telegram_user_id, username),
            )
            await connection.commit()

            cursor = await connection.execute(
                "SELECT telegram_user_id, username, message_count FROM users WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
            row = await cursor.fetchone()
        except aiosqlite.Error as exc:
            logger.error("user_repository_error", extra={"operation": "get_or_create", "error": str(exc)})
            raise RepositoryError(f"get_or_create failed: {exc}") from exc

        if row is None:
            raise RepositoryError("User row missing immediately after upsert")
        return User(telegram_user_id=row[0], username=row[1], message_count=row[2])

    async def increment_message_count(self, telegram_user_id: int) -> None:
        connection = self._database.connection
        try:
            await connection.execute(
                """
                UPDATE users
                SET message_count = message_count + 1, last_active_at = datetime('now')
                WHERE telegram_user_id = ?
                """,
                (telegram_user_id,),
            )
            await connection.commit()
        except aiosqlite.Error as exc:
            logger.error(
                "user_repository_error",
                extra={"operation": "increment_message_count", "error": str(exc)},
            )
            raise RepositoryError(f"increment_message_count failed: {exc}") from exc
