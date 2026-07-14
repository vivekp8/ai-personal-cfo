"""Core abstractions for the multi-provider LLM layer.

Defines the standard interface every provider implements, the shared request/
response models, and a typed exception hierarchy the router uses to decide
whether to fail over to the next provider.
"""
from __future__ import annotations

import abc
from typing import AsyncIterator, Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #
class Message(BaseModel):
    """A single chat message."""

    role: Role
    content: str


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """Normalised response returned by every provider."""

    text: str
    provider: str
    model: str
    usage: Usage = Field(default_factory=Usage)
    latency_ms: float = 0.0
    cached: bool = False
    finish_reason: Optional[str] = None


# --------------------------------------------------------------------------- #
# Exception hierarchy
# --------------------------------------------------------------------------- #
class ProviderError(Exception):
    """Base class for all provider errors.

    ``retryable`` tells the retry layer whether another attempt on the *same*
    provider might succeed. ``failover`` tells the router whether it should give
    up on this provider and move to the next one.
    """

    retryable: bool = False
    failover: bool = True

    def __init__(self, message: str, *, provider: str | None = None):
        super().__init__(message)
        self.provider = provider


class MissingCredentials(ProviderError):
    """Provider has no configured credentials; skip it entirely."""

    retryable = False
    failover = True


class RateLimitError(ProviderError):
    """HTTP 429 — back off and, if it persists, fail over."""

    retryable = True
    failover = True


class QuotaExceeded(ProviderError):
    """Quota / resource exhausted — do not retry, fail over immediately."""

    retryable = False
    failover = True


class ProviderTimeout(ProviderError):
    """Request timed out."""

    retryable = True
    failover = True


class ProviderServerError(ProviderError):
    """HTTP 5xx from the provider."""

    retryable = True
    failover = True


class ProviderConnectionError(ProviderError):
    """Could not connect to the provider."""

    retryable = True
    failover = True


class InvalidRequest(ProviderError):
    """HTTP 4xx (not 429) — the request itself is bad; do not fail over blindly.

    A malformed request will fail on every provider, so retrying elsewhere is
    usually pointless. The router still moves on so one bad provider mapping
    doesn't take down the call, but this is logged distinctly.
    """

    retryable = False
    failover = True


# --------------------------------------------------------------------------- #
# Provider interface
# --------------------------------------------------------------------------- #
class BaseProvider(abc.ABC):
    """Standard interface every provider must implement.

    The rest of the application never talks to a concrete provider directly —
    only through the router, which in turn depends only on this interface.
    """

    #: Stable short name used in config, metrics and logs (e.g. "gemini").
    name: str = "base"
    #: Default model identifier for this provider.
    model: str = ""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return True if credentials/config are present for this provider."""

    @abc.abstractmethod
    async def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return a normalised response."""

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Convenience single-prompt wrapper around :meth:`chat`."""
        return await self.chat(
            [Message(role="user", content=prompt)],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @abc.abstractmethod
    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Yield response tokens/chunks as they arrive.

        Concrete implementations are async generators that ``yield`` strings.
        """
        raise NotImplementedError

    async def embeddings(self, text: str | list[str]) -> list[list[float]]:
        """Return embedding vectors. Providers without support raise."""
        raise ProviderError(
            f"{self.name} does not support embeddings", provider=self.name
        )

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Lightweight liveness probe. Returns True if the provider responds."""
