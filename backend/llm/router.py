"""The LLM Router: single entry point the whole app depends on.

Selects providers by priority, skips those without credentials, retries
retryable failures with backoff, fails over on quota/rate-limit/server/timeout
errors, caches responses, records metrics, and logs every attempt. One provider
failing never crashes a request as long as another can answer.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import AsyncIterator, Optional

from .base import (
    BaseProvider,
    LLMResponse,
    Message,
    MissingCredentials,
    ProviderError,
)
from .cache import ResponseCache, make_key
from .gemini import GeminiProvider
from .github_models import GitHubModelsProvider
from .groq import GroqProvider
from .metrics import metrics
from .ollama import OllamaProvider
from .openrouter import OpenRouterProvider
from .retry import with_retry

logger = logging.getLogger("llm.router")

# Priority order: Groq > GitHub > Ollama > OpenRouter > Gemini (Gemini last).
_PROVIDER_ORDER: list[tuple[str, type[BaseProvider]]] = [
    ("groq", GroqProvider),
    ("github", GitHubModelsProvider),
    ("ollama", OllamaProvider),
    ("openrouter", OpenRouterProvider),
    ("gemini", GeminiProvider),
]


class LLMRouter:
    def __init__(
        self,
        *,
        cache: ResponseCache | None = None,
        max_attempts_per_provider: int = 3,
    ) -> None:
        self._providers: dict[str, BaseProvider] = {
            name: cls() for name, cls in _PROVIDER_ORDER
        }
        self._order: list[str] = [name for name, _ in _PROVIDER_ORDER]
        self.cache = cache or ResponseCache()
        self.max_attempts = max_attempts_per_provider
        self._last_provider: Optional[str] = None
        # Runtime override of the preferred provider (None → fall back to env).
        self._forced_override: Optional[str] = None

    # ---- provider selection --------------------------------------------- #
    def available_providers(self) -> list[str]:
        """Names of providers with credentials/config, in priority order."""
        return [n for n in self._order if self._providers[n].is_available()]

    def all_providers(self) -> list[str]:
        """All known provider names in priority order (available or not)."""
        return list(self._order)

    def preferred(self) -> str:
        """The currently preferred provider ('auto' means full priority chain).

        A runtime override (set via set_preferred) takes precedence over the
        DEFAULT_PROVIDER environment variable.
        """
        if self._forced_override is not None:
            return self._forced_override
        return os.getenv("DEFAULT_PROVIDER", "auto").strip().lower() or "auto"

    def set_preferred(self, name: str | None) -> str:
        """Set the preferred provider at runtime. 'auto'/None restores the chain.

        Raises ValueError for an unknown provider name.
        """
        if name is None or name.strip().lower() in ("", "auto"):
            self._forced_override = "auto"
            return "auto"
        key = name.strip().lower()
        if key not in self._providers:
            raise ValueError(
                f"Unknown provider '{name}'. Known: {', '.join(self._order)}"
            )
        self._forced_override = key
        return key

    def _selection(self) -> list[str]:
        """Ordered provider names to attempt, honouring the preferred provider.

        preferred == 'auto' → full priority chain.
        preferred == <name> → that provider first, then the rest as fallback so
        a forced choice is still resilient.
        """
        avail = self.available_providers()
        forced = self.preferred()
        if forced and forced != "auto" and forced in avail:
            return [forced] + [n for n in avail if n != forced]
        return avail

    @property
    def last_provider(self) -> Optional[str]:
        return self._last_provider

    # ---- core calls ------------------------------------------------------ #
    async def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        use_cache: bool = True,
    ) -> LLMResponse:
        """Return the first successful response across the provider chain."""
        selection = self._selection()
        if not selection:
            raise MissingCredentials(
                "No LLM providers are configured. Set at least one API key."
            )

        cache_key = make_key(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_hint="chat",
        )
        if use_cache:
            hit = self.cache.get(cache_key)
            if hit is not None:
                metrics.record_cache_hit()
                logger.info("cache hit provider=%s", hit.provider)
                self._last_provider = hit.provider
                return hit
            metrics.record_cache_miss()

        last_error: ProviderError | None = None
        for name in selection:
            provider = self._providers[name]
            logger.info("attempting provider=%s model=%s", name, provider.model)
            try:
                response = await with_retry(
                    lambda p=provider: p.chat(
                        messages, temperature=temperature, max_tokens=max_tokens
                    ),
                    provider=name,
                    max_attempts=self.max_attempts,
                )
            except ProviderError as exc:
                last_error = exc
                metrics.record_error(name, error_type=type(exc).__name__)
                logger.warning("provider=%s failed (%s); failing over", name, exc)
                if not exc.failover:
                    break
                continue

            metrics.record_success(
                name,
                latency_ms=response.latency_ms,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )
            self._last_provider = name
            logger.info(
                "provider=%s success latency=%.0fms tokens=%d",
                name,
                response.latency_ms,
                response.usage.total_tokens,
            )
            if use_cache:
                self.cache.set(cache_key, response)
            return response

        raise ProviderError(
            f"All providers failed. Last error: {last_error}"
        ) from last_error

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        use_cache: bool = True,
    ) -> LLMResponse:
        return await self.chat(
            [Message(role="user", content=prompt)],
            temperature=temperature,
            max_tokens=max_tokens,
            use_cache=use_cache,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from the first provider that starts successfully.

        Streaming is not cached. If a provider errors before yielding, we fail
        over to the next one.
        """
        selection = self._selection()
        if not selection:
            raise MissingCredentials("No LLM providers are configured.")

        last_error: ProviderError | None = None
        for name in selection:
            provider = self._providers[name]
            logger.info("streaming attempt provider=%s", name)
            try:
                gen = provider.stream(
                    messages, temperature=temperature, max_tokens=max_tokens
                )
                # Pull the first chunk to surface early errors before committing.
                first = await gen.__anext__()
                self._last_provider = name
                metrics.record_success(
                    name, latency_ms=0.0, prompt_tokens=0, completion_tokens=0
                )
                yield first
                async for chunk in gen:
                    yield chunk
                return
            except StopAsyncIteration:
                # Empty stream — treat as success with no content.
                self._last_provider = name
                return
            except ProviderError as exc:
                last_error = exc
                metrics.record_error(name, error_type=type(exc).__name__)
                logger.warning("stream provider=%s failed (%s); failing over", name, exc)
                continue

        raise ProviderError(f"All providers failed to stream. Last error: {last_error}")

    async def embeddings(self, text: str | list[str]) -> list[list[float]]:
        """Return embeddings from the first provider that supports them."""
        last_error: Exception | None = None
        for name in self._selection():
            try:
                return await self._providers[name].embeddings(text)
            except ProviderError as exc:
                last_error = exc
                continue
        raise ProviderError(f"No provider produced embeddings. Last error: {last_error}")

    # ---- health ---------------------------------------------------------- #
    async def health_check(self) -> dict:
        """Probe every configured provider concurrently.

        Returns a mapping of provider -> "healthy" | "unhealthy" | "not_configured"
        plus the currently active provider (first healthy in priority order).
        """
        async def probe(name: str) -> tuple[str, str]:
            provider = self._providers[name]
            if not provider.is_available():
                return name, "not_configured"
            try:
                ok = await provider.health_check()
                return name, "healthy" if ok else "unhealthy"
            except Exception:  # noqa: BLE001
                return name, "unhealthy"

        results = await asyncio.gather(*(probe(n) for n in self._order))
        status = dict(results)
        active = next((n for n in self._order if status.get(n) == "healthy"), None)
        status["active_provider"] = active or "none"
        return status


# App-wide singleton.
router = LLMRouter()
