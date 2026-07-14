"""Shared test fixtures.

Each test starts from a clean slate: all provider env vars are cleared, the
metrics singleton is reset, and helpers are provided to build routers and mock
provider HTTP responses.
"""
from __future__ import annotations

import os
import sys

import pytest

# Make the backend package importable when running `pytest` from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.cache import ResponseCache  # noqa: E402
from llm.metrics import metrics  # noqa: E402
from llm.router import LLMRouter  # noqa: E402

_PROVIDER_ENV = [
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "GITHUB_TOKEN",
    "OPENROUTER_API_KEY",
    "OLLAMA_BASE_URL",
    "DEFAULT_PROVIDER",
    "REDIS_URL",
]

# Provider endpoint URLs (used to build respx mocks).
GEMINI_URL_RE = r"https://generativelanguage\.googleapis\.com/.*generateContent.*"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GITHUB_URL = "https://models.inference.ai.azure.com/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/v1/chat/completions"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Clear all provider credentials and reset metrics before every test."""
    for key in _PROVIDER_ENV:
        monkeypatch.delenv(key, raising=False)
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def make_router():
    """Factory building a router with a fresh, isolated in-memory cache."""

    def _factory(**kwargs) -> LLMRouter:
        cache = ResponseCache(ttl=60, redis_url="")
        return LLMRouter(cache=cache, **kwargs)

    return _factory


def openai_success(text: str = "hello", *, prompt=1, completion=1) -> dict:
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        },
    }


def gemini_success(text: str = "hello") -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {
            "promptTokenCount": 1,
            "candidatesTokenCount": 1,
            "totalTokenCount": 2,
        },
    }
