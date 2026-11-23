"""Simple in-memory rate limiter for sensitive endpoints (login).

Sliding window per client IP. Limitation: memory is per process, so with several
backend processes/servers each has its own counter. That's acceptable for one
server; a shared store (e.g. Redis) would be needed when scaling out.
Account lockout in auth_service is the second, database-backed protection layer.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

WINDOW_SECONDS = 60
MAX_ATTEMPTS = 10

_attempts: dict[str, deque[float]] = defaultdict(deque)


def login_rate_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _attempts[key]
    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()
    if len(window) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts. Wait a minute and try again.")
    window.append(now)


def reset() -> None:  # used by tests
    _attempts.clear()
