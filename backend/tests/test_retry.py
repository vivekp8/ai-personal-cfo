"""Retry/backoff behaviour."""
from __future__ import annotations

import pytest

from llm.base import InvalidRequest, ProviderServerError
from llm.retry import with_retry


async def test_succeeds_first_try():
    calls = {"n": 0}

    async def ok():
        calls["n"] += 1
        return "done"

    result = await with_retry(ok, provider="test", base_delay=0.0)
    assert result == "done"
    assert calls["n"] == 1


async def test_retries_retryable_then_succeeds():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ProviderServerError("boom", provider="test")
        return "recovered"

    result = await with_retry(flaky, provider="test", max_attempts=5, base_delay=0.0)
    assert result == "recovered"
    assert calls["n"] == 3


async def test_gives_up_after_max_attempts():
    calls = {"n": 0}

    async def always_fail():
        calls["n"] += 1
        raise ProviderServerError("boom", provider="test")

    with pytest.raises(ProviderServerError):
        await with_retry(always_fail, provider="test", max_attempts=3, base_delay=0.0)
    assert calls["n"] == 3


async def test_non_retryable_not_retried():
    calls = {"n": 0}

    async def bad_request():
        calls["n"] += 1
        raise InvalidRequest("nope", provider="test")

    with pytest.raises(InvalidRequest):
        await with_retry(bad_request, provider="test", max_attempts=5, base_delay=0.0)
    assert calls["n"] == 1  # not retried
