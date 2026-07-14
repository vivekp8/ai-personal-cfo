"""Exponential-backoff retry helper for provider calls.

Only retries errors flagged ``retryable`` (429, timeouts, 5xx, connection
errors). Non-retryable errors (missing creds, quota exhausted, bad request)
propagate immediately so the router can fail over without wasting time.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

from .base import ProviderError

logger = logging.getLogger("llm.retry")

T = TypeVar("T")


async def with_retry(
    func: Callable[[], Awaitable[T]],
    *,
    provider: str,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    jitter: float = 0.25,
) -> T:
    """Call ``func`` with exponential backoff on retryable provider errors.

    Args:
        func: Zero-arg async callable performing one attempt.
        provider: Provider name (for logging).
        max_attempts: Total attempts before giving up.
        base_delay: Initial backoff in seconds.
        max_delay: Cap on backoff.
        jitter: Fractional random jitter added to each delay.

    Returns:
        Whatever ``func`` returns on first success.

    Raises:
        ProviderError: The last error if all attempts fail, or immediately for
        non-retryable errors.
    """
    attempt = 0
    last_error: ProviderError | None = None

    while attempt < max_attempts:
        attempt += 1
        try:
            return await func()
        except ProviderError as exc:
            last_error = exc
            if not exc.retryable or attempt >= max_attempts:
                logger.warning(
                    "provider=%s attempt=%d/%d giving up: %s",
                    provider,
                    attempt,
                    max_attempts,
                    exc,
                )
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0, delay * jitter)
            logger.info(
                "provider=%s attempt=%d/%d retryable error (%s); backing off %.2fs",
                provider,
                attempt,
                max_attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    # Unreachable, but keeps type checkers happy.
    assert last_error is not None
    raise last_error
