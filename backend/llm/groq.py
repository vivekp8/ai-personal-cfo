"""Groq provider (OpenAI-compatible, very low latency)."""
from __future__ import annotations

import os

from ._openai_compat import OpenAICompatProvider


class GroqProvider(OpenAICompatProvider):
    name = "groq"
    chat_url = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self) -> None:
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def _api_key(self) -> str | None:
        return os.getenv("GROQ_API_KEY")
