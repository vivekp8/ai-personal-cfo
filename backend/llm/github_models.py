"""GitHub Models provider (Azure AI inference, OpenAI-compatible).

Authenticates with a GitHub personal-access token (``GITHUB_TOKEN``).
"""
from __future__ import annotations

import os

from ._openai_compat import OpenAICompatProvider


class GitHubModelsProvider(OpenAICompatProvider):
    name = "github"
    chat_url = "https://models.inference.ai.azure.com/chat/completions"

    def __init__(self) -> None:
        self.model = os.getenv("GITHUB_MODEL", "gpt-4o-mini")

    def _api_key(self) -> str | None:
        return os.getenv("GITHUB_TOKEN")
