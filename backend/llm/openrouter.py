"""OpenRouter provider (OpenAI-compatible aggregator, free models available)."""
from __future__ import annotations

import os

from ._openai_compat import OpenAICompatProvider


class OpenRouterProvider(OpenAICompatProvider):
    name = "openrouter"
    chat_url = "https://openrouter.ai/api/v1/chat/completions"
    # OpenRouter recommends attribution headers; harmless if generic.
    extra_headers = {
        "HTTP-Referer": "https://ai-personal-cfo.local",
        "X-Title": "AI Personal CFO",
    }

    def __init__(self) -> None:
        self.model = os.getenv(
            "OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
        )

    def _api_key(self) -> str | None:
        return os.getenv("OPENROUTER_API_KEY")
