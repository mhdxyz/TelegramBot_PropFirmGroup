"""
Exercises the webhook endpoint over real HTTP (via FastAPI's TestClient),
using a fake Telegram Application double instead of a real one — this
tests routing/validation/security behavior without making any network call
to Telegram, and without needing a real bot token.

Requires `fastapi`, `httpx` (TestClient's transport), and `python-telegram-bot`
to be installed; run via `pytest tests/integration`.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from telegram import Update

from app.core.config import AppConfig
from app.webhook.routes import router
from app.webhook.security import TELEGRAM_SECRET_HEADER

WEBHOOK_SECRET = "test-secret-token"

VALID_UPDATE_PAYLOAD = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 0,
        "chat": {"id": 123, "type": "private"},
        "from": {"id": 123, "is_bot": False, "first_name": "Test"},
        "text": "hello",
    },
}


class FakeBot:
    pass


class FakeTelegramApplication:
    """Minimal stand-in for telegram.ext.Application — only implements what
    routes.py actually touches: `.bot` and `.process_update()`."""

    def __init__(self) -> None:
        self.bot = FakeBot()
        self.processed_updates: list[Update] = []

    async def process_update(self, update: Update) -> None:
        self.processed_updates.append(update)

    # No-ops so this fake can also stand in for the lifespan-managed
    # Application in tests that exercise app startup/shutdown (e.g. /health).
    async def initialize(self) -> None:
        pass

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


def make_test_client(fake_application: FakeTelegramApplication) -> TestClient:
    config = AppConfig.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "dummy-token",
            "WEBHOOK_SECRET": WEBHOOK_SECRET,
        }
    )
    app = FastAPI()
    app.state.config = config
    app.state.telegram_application = fake_application
    app.include_router(router)
    return TestClient(app)


def test_valid_update_with_correct_secret_is_processed():
    fake_app = FakeTelegramApplication()
    client = make_test_client(fake_app)

    response = client.post(
        "/webhook",
        json=VALID_UPDATE_PAYLOAD,
        headers={TELEGRAM_SECRET_HEADER: WEBHOOK_SECRET},
    )

    assert response.status_code == 200
    assert len(fake_app.processed_updates) == 1


def test_missing_secret_header_is_rejected():
    client = make_test_client(FakeTelegramApplication())

    response = client.post("/webhook", json=VALID_UPDATE_PAYLOAD)

    assert response.status_code == 401


def test_wrong_secret_header_is_rejected():
    client = make_test_client(FakeTelegramApplication())

    response = client.post(
        "/webhook",
        json=VALID_UPDATE_PAYLOAD,
        headers={TELEGRAM_SECRET_HEADER: "wrong-secret"},
    )

    assert response.status_code == 401


def test_malformed_json_is_rejected():
    client = make_test_client(FakeTelegramApplication())

    response = client.post(
        "/webhook",
        content=b"{not valid json",
        headers={TELEGRAM_SECRET_HEADER: WEBHOOK_SECRET, "content-type": "application/json"},
    )

    assert response.status_code == 400


def test_oversized_payload_is_rejected():
    fake_app = FakeTelegramApplication()
    client = make_test_client(fake_app)
    huge_text = "x" * 2_000_000

    response = client.post(
        "/webhook",
        content=json.dumps({**VALID_UPDATE_PAYLOAD, "message": {**VALID_UPDATE_PAYLOAD["message"], "text": huge_text}}),
        headers={TELEGRAM_SECRET_HEADER: WEBHOOK_SECRET, "content-type": "application/json"},
    )

    assert response.status_code == 413
    assert len(fake_app.processed_updates) == 0


def test_get_method_is_not_allowed():
    client = make_test_client(FakeTelegramApplication())

    response = client.get("/webhook")

    assert response.status_code == 405


def test_health_endpoint_reports_ai_status():
    from app.webhook.app import create_app
    from app.database.connection import Database

    config = AppConfig.from_env(
        {"TELEGRAM_BOT_TOKEN": "dummy-token", "WEBHOOK_SECRET": WEBHOOK_SECRET, "AI_ENABLED": "false"}
    )
    app = create_app(config, FakeTelegramApplication(), Database(":memory:"))
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "ai_enabled": False}
