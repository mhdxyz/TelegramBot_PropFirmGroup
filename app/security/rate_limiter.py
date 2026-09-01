"""
Per-user sliding-window rate limiter.

In-memory by design: it protects the bot process itself from abuse/flooding
and doesn't need to survive restarts or be shared across processes at this
project's scale. If the bot is ever run with multiple worker processes,
this is the component to swap for a Redis-backed implementation — the
`RateLimiter` interface below is the seam for that.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Protocol

from app.core.exceptions import RateLimitExceededError


class RateLimiter(Protocol):
    def check(self, key: int) -> None:
        """Raise RateLimitExceededError if `key` has exceeded its quota."""
        ...


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float, *, clock=time.monotonic) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._clock = clock
        self._requests_by_key: dict[int, deque[float]] = defaultdict(deque)

    def check(self, key: int) -> None:
        now = self._clock()
        timestamps = self._requests_by_key[key]
        cutoff = now - self._window_seconds

        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

        if len(timestamps) >= self._max_requests:
            retry_after = self._window_seconds - (now - timestamps[0])
            raise RateLimitExceededError(key, max(retry_after, 0.0))

        timestamps.append(now)
