"""In-memory metrics for the LLM layer.

Thread-safe enough for a single-process async app. Tracks per-provider latency,
token usage, errors, retries, cache hits/misses and a rough cost estimate, and
exposes an aggregate snapshot for the FastAPI metrics endpoint.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field

# Rough USD cost per 1K tokens (prompt+completion averaged) for estimation only.
# Free tiers are 0.0; these are ballpark and easy to tune.
COST_PER_1K_TOKENS: dict[str, float] = {
    "gemini": 0.0,        # free flash tier
    "groq": 0.0,          # free tier
    "github": 0.0,        # free during preview
    "openrouter": 0.0,    # free models
    "ollama": 0.0,        # local
}


@dataclass
class ProviderStats:
    requests: int = 0
    successes: int = 0
    errors: int = 0
    retries: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    cost_estimate_usd: float = 0.0
    error_types: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def as_dict(self) -> dict:
        avg_latency = self.total_latency_ms / self.successes if self.successes else 0.0
        success_rate = self.successes / self.requests if self.requests else 0.0
        return {
            "requests": self.requests,
            "successes": self.successes,
            "errors": self.errors,
            "retries": self.retries,
            "success_rate": round(success_rate, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_estimate_usd": round(self.cost_estimate_usd, 6),
            "error_types": dict(self.error_types),
        }


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._providers: dict[str, ProviderStats] = defaultdict(ProviderStats)
        self.cache_hits = 0
        self.cache_misses = 0

    def record_success(
        self,
        provider: str,
        *,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        retries: int = 0,
    ) -> None:
        total = prompt_tokens + completion_tokens
        with self._lock:
            s = self._providers[provider]
            s.requests += 1
            s.successes += 1
            s.retries += retries
            s.prompt_tokens += prompt_tokens
            s.completion_tokens += completion_tokens
            s.total_tokens += total
            s.total_latency_ms += latency_ms
            s.cost_estimate_usd += (total / 1000.0) * COST_PER_1K_TOKENS.get(provider, 0.0)

    def record_error(self, provider: str, *, error_type: str, retries: int = 0) -> None:
        with self._lock:
            s = self._providers[provider]
            s.requests += 1
            s.errors += 1
            s.retries += retries
            s.error_types[error_type] += 1

    def record_cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1

    def snapshot(self) -> dict:
        with self._lock:
            providers = {name: s.as_dict() for name, s in self._providers.items()}
            total_requests = sum(s.requests for s in self._providers.values())
            total_tokens = sum(s.total_tokens for s in self._providers.values())
            total_cost = sum(s.cost_estimate_usd for s in self._providers.values())
            cache_total = self.cache_hits + self.cache_misses
            return {
                "providers": providers,
                "totals": {
                    "requests": total_requests,
                    "total_tokens": total_tokens,
                    "cost_estimate_usd": round(total_cost, 6),
                },
                "cache": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_rate": round(self.cache_hits / cache_total, 4) if cache_total else 0.0,
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._providers.clear()
            self.cache_hits = 0
            self.cache_misses = 0


# Module-level singleton used across the app.
metrics = Metrics()
