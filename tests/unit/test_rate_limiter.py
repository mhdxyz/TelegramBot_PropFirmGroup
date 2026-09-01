from __future__ import annotations

import pytest

from app.core.exceptions import RateLimitExceededError
from app.security.rate_limiter import SlidingWindowRateLimiter


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_allows_requests_under_the_limit():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60, clock=clock)

    limiter.check(user_key := 1)
    limiter.check(user_key)
    limiter.check(user_key)  # third request still within limit


def test_blocks_requests_over_the_limit():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60, clock=clock)

    limiter.check(1)
    limiter.check(1)

    with pytest.raises(RateLimitExceededError):
        limiter.check(1)


def test_window_expiry_allows_requests_again():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10, clock=clock)

    limiter.check(1)
    with pytest.raises(RateLimitExceededError):
        limiter.check(1)

    clock.advance(10.01)
    limiter.check(1)  # should succeed now that the window has passed


def test_limits_are_tracked_independently_per_key():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60, clock=clock)

    limiter.check(1)
    limiter.check(2)  # different user, independent quota


@pytest.mark.parametrize("max_requests,window_seconds", [(0, 60), (-1, 60), (5, 0), (5, -1)])
def test_rejects_invalid_configuration(max_requests, window_seconds):
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(max_requests=max_requests, window_seconds=window_seconds)
