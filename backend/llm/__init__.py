"""Multi-provider LLM layer.

Public surface the rest of the app should use:

    from llm import router, agenerate, generate, is_configured

- ``router``        : the async :class:`LLMRouter` singleton (chat/stream/etc.)
- ``agenerate``     : async single-prompt helper -> :class:`LLMResponse`
- ``generate``      : sync single-prompt helper -> str | None (legacy bridge)
- ``is_configured`` : True if any provider has credentials

Everything else in the app depends only on this module, never on a concrete
provider.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Awaitable, TypeVar

from .base import (  # noqa: F401
    BaseProvider,
    LLMResponse,
    Message,
    ProviderError,
)
from .metrics import metrics  # noqa: F401
from .router import LLMRouter, router  # noqa: F401

T = TypeVar("T")

__all__ = [
    "router",
    "LLMRouter",
    "Message",
    "LLMResponse",
    "ProviderError",
    "metrics",
    "agenerate",
    "achat",
    "generate",
    "is_configured",
    "run_sync",
]


def is_configured() -> bool:
    """True if at least one provider is configured."""
    return bool(router.available_providers())


async def agenerate(prompt: str, **kwargs) -> LLMResponse:
    """Async single-prompt helper."""
    return await router.generate(prompt, **kwargs)


async def achat(messages: list[Message], **kwargs) -> LLMResponse:
    """Async chat helper."""
    return await router.chat(messages, **kwargs)


def run_sync(coro: Awaitable[T]) -> T:
    """Run an async coroutine from sync code, even under a running loop.

    FastAPI runs plain ``def`` endpoints in a threadpool (no running loop), so
    ``asyncio.run`` normally works. If a loop *is* already running in this
    thread, we execute the coroutine in a separate thread with its own loop to
    avoid "loop already running" errors.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # type: ignore[arg-type]

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()  # type: ignore[arg-type]


def generate(prompt: str) -> str | None:
    """Sync single-prompt helper returning plain text (legacy bridge).

    Returns None if no provider is configured, or ``"[LLM error: ...]"`` if all
    configured providers fail — matching the previous llm_client contract.
    """
    if not is_configured():
        return None
    try:
        resp = run_sync(router.generate(prompt))
        return resp.text
    except ProviderError as exc:
        return f"[LLM error: {exc}]"
    except Exception as exc:  # noqa: BLE001
        return f"[LLM error: {exc}]"
