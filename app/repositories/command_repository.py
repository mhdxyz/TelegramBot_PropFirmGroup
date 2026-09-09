from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import aiosqlite

from app.core.exceptions import RepositoryError
from app.database.connection import Database


@dataclass(frozen=True)
class LotteryRegistration:
    telegram_user_id: int
    full_name: str
    company_a_email: str
    company_b_email: str
    telegram_username: str | None
    registered_at: str


@dataclass(frozen=True)
class LotteryExportJob:
    telegram_user_id: int
    full_name: str
    company_a_email: str
    company_b_email: str
    telegram_username: str | None
    registered_at: str
    attempts: int


class LotteryRepository(Protocol):
    async def create_registration(
        self,
        *,
        telegram_user_id: int,
        full_name: str,
        company_a_email: str,
        company_b_email: str,
        telegram_username: str | None,
    ) -> LotteryRegistration: ...

    async def get_registration(self, telegram_user_id: int) -> LotteryRegistration | None: ...


class LotteryExportQueueRepository(Protocol):
    async def enqueue_registration(self, telegram_user_id: int) -> None: ...
    async def get_pending_exports(self, limit: int = 20) -> list[LotteryExportJob]: ...
    async def mark_export_succeeded(self, telegram_user_id: int) -> None: ...
    async def mark_export_failed(self, telegram_user_id: int, error: str) -> None: ...


class ContentRepository(Protocol):
    async def set_content(self, key: str, content: str) -> None: ...
    async def get_content(self, key: str) -> str | None: ...


class SQLiteCommandRepository(LotteryRepository, LotteryExportQueueRepository, ContentRepository):
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create_registration(self, *, telegram_user_id: int, full_name: str,
                                   company_a_email: str, company_b_email: str,
                                   telegram_username: str | None) -> LotteryRegistration:
        connection = self._database.connection
        try:
            await connection.execute("BEGIN IMMEDIATE")
            cursor = await connection.execute(
                """
                INSERT INTO lottery_registrations
                    (telegram_user_id, full_name, company_a_email, company_b_email, telegram_username)
                VALUES (?, ?, ?, ?, ?)
                """,
                (telegram_user_id, full_name, company_a_email, company_b_email, telegram_username),
            )
            if cursor.rowcount != 1:
                raise RepositoryError("Lottery registration was not inserted")

            await connection.execute(
                "INSERT INTO lottery_export_outbox (telegram_user_id) VALUES (?)",
                (telegram_user_id,),
            )
            await connection.commit()

            result = await self.get_registration(telegram_user_id)
            if result is None:
                raise RepositoryError("Lottery registration disappeared after commit")
            return result
        except RepositoryError:
            await connection.rollback()
            raise
        except aiosqlite.IntegrityError as exc:
            await connection.rollback()
            if "lottery_registrations" in str(exc):
                raise RepositoryError("Lottery registration already exists") from exc
            raise RepositoryError(f"Lottery registration transaction failed: {exc}") from exc
        except aiosqlite.Error as exc:
            await connection.rollback()
            raise RepositoryError(f"Lottery registration transaction failed: {exc}") from exc

    async def get_registration(self, telegram_user_id: int) -> LotteryRegistration | None:
        try:
            cursor = await self._database.connection.execute(
                """SELECT telegram_user_id, full_name, company_a_email, company_b_email,
                          telegram_username, registered_at
                   FROM lottery_registrations WHERE telegram_user_id = ?""",
                (telegram_user_id,),
            )
            row = await cursor.fetchone()
        except aiosqlite.Error as exc:
            raise RepositoryError(f"Lottery lookup failed: {exc}") from exc
        if row is None:
            return None
        return LotteryRegistration(*row)

    async def enqueue_registration(self, telegram_user_id: int) -> None:
        try:
            await self._database.connection.execute(
                "INSERT OR IGNORE INTO lottery_export_outbox (telegram_user_id) VALUES (?)",
                (telegram_user_id,),
            )
            await self._database.connection.commit()
        except aiosqlite.Error as exc:
            raise RepositoryError(f"Lottery export queue update failed: {exc}") from exc

    async def get_pending_exports(self, limit: int = 20) -> list[LotteryExportJob]:
        try:
            cursor = await self._database.connection.execute(
                """
                SELECT r.telegram_user_id, r.full_name, r.company_a_email,
                       r.company_b_email, r.telegram_username, r.registered_at,
                       o.attempts
                FROM lottery_export_outbox o
                JOIN lottery_registrations r ON r.telegram_user_id = o.telegram_user_id
                WHERE o.next_attempt_at <= datetime('now')
                ORDER BY o.created_at ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
        except aiosqlite.Error as exc:
            raise RepositoryError(f"Lottery export queue lookup failed: {exc}") from exc
        return [LotteryExportJob(*row) for row in rows]

    async def mark_export_succeeded(self, telegram_user_id: int) -> None:
        try:
            await self._database.connection.execute(
                "DELETE FROM lottery_export_outbox WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
            await self._database.connection.commit()
        except aiosqlite.Error as exc:
            raise RepositoryError(f"Lottery export queue completion failed: {exc}") from exc

    async def mark_export_failed(self, telegram_user_id: int, error: str) -> None:
        safe_error = error[:2000]
        try:
            await self._database.connection.execute(
                """
                UPDATE lottery_export_outbox
                SET attempts = attempts + 1,
                    last_error = ?,
                    next_attempt_at = datetime('now', '+' || MIN(3600, CAST(POWER(2, attempts) AS INTEGER)) || ' seconds')
                WHERE telegram_user_id = ?
                """,
                (safe_error, telegram_user_id),
            )
            await self._database.connection.commit()
        except aiosqlite.Error as exc:
            raise RepositoryError(f"Lottery export retry scheduling failed: {exc}") from exc

    async def set_content(self, key: str, content: str) -> None:
        try:
            await self._database.connection.execute(
                """INSERT INTO bot_content(content_key, content) VALUES (?, ?)
                   ON CONFLICT(content_key) DO UPDATE SET content=excluded.content,
                   updated_at=datetime('now')""",
                (key, content),
            )
            await self._database.connection.commit()
        except aiosqlite.Error as exc:
            raise RepositoryError(f"Content update failed: {exc}") from exc

    async def get_content(self, key: str) -> str | None:
        try:
            cursor = await self._database.connection.execute(
                "SELECT content FROM bot_content WHERE content_key = ?", (key,),
            )
            row = await cursor.fetchone()
        except aiosqlite.Error as exc:
            raise RepositoryError(f"Content lookup failed: {exc}") from exc
        return None if row is None else row[0]
