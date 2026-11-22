"""API key authentication and an in-memory per-key rate limiter.

The limiter is deliberately process-local. For a multi-replica deployment,
replace it with Redis or an API gateway; the interface is intentionally small.
"""
from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque


def verify_api_key(provided: str | None, keys: tuple[str, ...]) -> bool:
    if not provided or not keys:
        return False
    # Compare against every key in constant time; do not short-circuit on the
    # first match, which could leak which key matched via timing.
    matched = False
    for key in keys:
        if secrets.compare_digest(provided, key):
            matched = True
    return matched


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit = max(1, limit)
        self.window_s = window_s
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            cutoff = now - self.window_s
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(0.0, self.window_s - (now - events[0]))
                return False, retry_after
            events.append(now)
            return True, 0.0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
