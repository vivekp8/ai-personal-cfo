"""Legacy LLM client facade — now backed by the multi-provider router.

Historically this talked to Gemini directly. It now delegates to the ``llm``
package so every caller transparently gets automatic provider failover
(Gemini -> Groq -> GitHub -> OpenRouter -> Ollama), retries, caching and
metrics — with no change to the existing call sites in the agents.

Never fabricates: if no provider is configured, callers get a clear
"not configured" signal (None) instead of a fake answer.
"""
from __future__ import annotations

import llm


def is_configured() -> bool:
    """True if any provider has credentials."""
    return llm.is_configured()


def generate(prompt: str) -> str | None:
    """Return generated text, None if unconfigured, or ``[LLM error: ...]``."""
    return llm.generate(prompt)


def categorize_with_llm(description: str, categories: list[str]) -> str | None:
    """Categorise a transaction description via the router.

    Returns a validated category string, or None if unavailable/errored.
    """
    if not is_configured():
        return None
    cat_list = ", ".join(categories)
    prompt = (
        "You are a bank-transaction categorizer. Choose the single best category "
        f"for this merchant/description from this list: {cat_list}, Uncategorized.\n"
        f"Description: {description!r}\n"
        "Reply with ONLY the category word, nothing else."
    )
    text = llm.generate(prompt)
    if not text or text.startswith("[LLM error"):
        return None
    answer = text.strip().splitlines()[0].strip()
    valid = {c.lower(): c for c in categories}
    return valid.get(answer.lower(), answer if answer else None)
