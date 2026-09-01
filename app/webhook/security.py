"""
Verifies that an incoming webhook request actually came from Telegram.

Uses Telegram's built-in secret-token mechanism: when a webhook is
registered with a `secret_token`, Telegram includes it on every request as
the `X-Telegram-Bot-Api-Secret-Token` header. Comparing with `hmac.compare_digest`
avoids leaking timing information about how much of the token matched.
"""

from __future__ import annotations

import hmac

TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


def is_valid_secret_token(received: str | None, expected: str) -> bool:
    if received is None:
        return False
    return hmac.compare_digest(received, expected)
