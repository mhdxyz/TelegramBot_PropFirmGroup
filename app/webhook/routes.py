"""
The webhook endpoint.

Deliberately minimal: verify the request is really from Telegram, verify
it's a reasonably-sized well-formed JSON payload, hand it to the existing
python-telegram-bot `Application` for processing, and return quickly.
No AI logic, no database logic, no authorization/business rules — those
live in the handler → service → provider chain that `Application` already
dispatches to (see app/main.py for registration, app/bot/middleware for
cross-cutting checks).

Returning 200 even for updates the bot can't act on (e.g. unauthorized
sender) is intentional: that's an application-level outcome, not a
transport-level failure, and Telegram would otherwise retry-storm us for a
200-shaped situation it can't fix by retrying.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response
from telegram import Update
from telegram.ext import Application

from app.core.logging import get_logger
from app.webhook.security import TELEGRAM_SECRET_HEADER, is_valid_secret_token

logger = get_logger(__name__)

router = APIRouter()


@router.post("/webhook")
async def receive_update(request: Request) -> Response:
    config = request.app.state.config
    application: Application = request.app.state.telegram_application

    secret_header = request.headers.get(TELEGRAM_SECRET_HEADER)
    if not is_valid_secret_token(secret_header, config.webhook.secret_token):
        logger.warning("webhook_unauthorized", extra={"reason": "invalid_secret_token"})
        # 401 without any detail — never confirm/deny *why* to the caller.
        return Response(status_code=401)

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > config.webhook.max_payload_bytes:
        logger.warning("webhook_payload_too_large", extra={"content_length": content_length})
        return Response(status_code=413)

    body = await request.body()
    if len(body) > config.webhook.max_payload_bytes:
        logger.warning("webhook_payload_too_large", extra={"actual_bytes": len(body)})
        return Response(status_code=413)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("webhook_malformed_json")
        return Response(status_code=400)

    try:
        update = Update.de_json(payload, application.bot)
    except Exception:
        logger.warning("webhook_invalid_update_shape", exc_info=True)
        return Response(status_code=400)

    if update is None:
        return Response(status_code=400)

    # Hand off and return immediately; handler failures are caught by the
    # bot's own error_boundary middleware, not here.
    await application.process_update(update)
    return Response(status_code=200)
