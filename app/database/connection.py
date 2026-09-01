"""
Database connection management.

SQLite via aiosqlite is used as the default because it requires no external
service for development/small deployments, while `UserRepository` (see
repositories/user_repository.py) is defined as an interface so a Postgres
implementation can be dropped in later without touching business logic.
"""

from __future__ import annotations

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_active_at TEXT NOT NULL DEFAULT (datetime('now')),
    message_count INTEGER NOT NULL DEFAULT 0
);
"""


class Database:
    """Thin wrapper owning the connection lifecycle."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._connection = await aiosqlite.connect(self._path)
        await self._connection.execute("PRAGMA foreign_keys = ON;")
        await self._connection.executescript(_SCHEMA)
        await self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database.connect() must be called before use")
        return self._connection


def sqlite_path_from_url(database_url: str) -> str:
    """Extract a filesystem path from a `sqlite+aiosqlite:///path` URL.

    A minimal, explicit parser rather than pulling in SQLAlchemy for a
    single string transformation.
    """
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(f"Unsupported DATABASE_URL scheme: {database_url}")
    return database_url[len(prefix) :]
