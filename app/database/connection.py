"""
Database connection management.

SQLite via aiosqlite is the default persistence layer. Business services use
repository interfaces so storage can be replaced without changing handlers.
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

CREATE TABLE IF NOT EXISTS lottery_registrations (
    telegram_user_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    company_a_email TEXT NOT NULL,
    company_b_email TEXT NOT NULL,
    telegram_username TEXT,
    registered_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (telegram_user_id) REFERENCES users(telegram_user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bot_content (
    content_key TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
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
        await self._connection.execute("PRAGMA journal_mode = WAL;")
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
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(f"Unsupported DATABASE_URL scheme: {database_url}")
    return database_url[len(prefix) :]
