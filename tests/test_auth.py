# -*- coding: utf-8 -*-
from __future__ import annotations

import time

from agentic_rag.auth import InMemoryRateLimiter, verify_api_key


def test_verify_api_key_requires_exact_match():
    keys = ("alpha", "beta")
    assert verify_api_key("alpha", keys) is True
    assert verify_api_key("beta", keys) is True
    assert verify_api_key("gamma", keys) is False
    assert verify_api_key(None, keys) is False
    assert verify_api_key("alpha", ()) is False


def test_rate_limiter_blocks_after_limit():
    limiter = InMemoryRateLimiter(limit=2, window_s=60)
    assert limiter.allow("k")[0] is True
    assert limiter.allow("k")[0] is True
    allowed, retry_after = limiter.allow("k")
    assert allowed is False
    assert 0 <= retry_after <= 60
    assert limiter.allow("other")[0] is True


def test_rate_limiter_window_expires():
    limiter = InMemoryRateLimiter(limit=1, window_s=0.02)
    assert limiter.allow("k")[0] is True
    assert limiter.allow("k")[0] is False
    time.sleep(0.05)
    assert limiter.allow("k")[0] is True
