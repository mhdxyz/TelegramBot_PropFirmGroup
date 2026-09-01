"""
Guard functions applied at the top of handlers to enforce authorization and
rate limiting uniformly.

These raise the appropriate UserFacingError subclasses (see
core/exceptions.py), which the error_boundary middleware turns into a safe
reply. Keeping this as small composable functions — rather than a
decorator with hidden control flow — keeps handler code explicit about
what checks run and in what order.
"""

from __future__ import annotations

from app.security.authorization import Authorizer
from app.security.rate_limiter import RateLimiter


def enforce_access(telegram_user_id: int, authorizer: Authorizer, rate_limiter: RateLimiter) -> None:
    authorizer.require_allowed(telegram_user_id)
    rate_limiter.check(telegram_user_id)
