"""Ollama provider (local models via the OpenAI-compatible endpoint).

Ollama needs no API key; it is considered "available" whenever a base URL is
configured, and acts as the final local fallback in the router chain.
"""
from __future__ import annotations

import os

import httpx

from ._openai_compat import DEFAULT_TIMEOUT, OpenAICompatProvider


class OllamaProvider(OpenAICompatProvider):
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.chat_url = f"{self.base_url}/v1/chat/completions"
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2")

    def _api_key(self) -> str | None:
        # Ollama is unauthenticated; return a sentinel so the OpenAI-compat base
        # doesn't add an Authorization header but still treats us as configured.
        return None

    def is_available(self) -> bool:
        # Available when a base URL is configured (the daemon may still be down,
        # in which case the call fails and the router has already exhausted the
        # cloud providers before reaching here).
        return bool(self.base_url)

    async def health_check(self) -> bool:
        if not self.is_available():
            return False
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False
