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


def categorize_with_llm(descriptions: list[str]) -> dict[str, str]:
    """Categorise a list of transaction descriptions via the router.

    Returns a dict mapping the description to a generated category string.
    """
    if not is_configured() or not descriptions:
        return {}
        
    desc_list = "\n".join(f"- {d}" for d in descriptions)
    prompt = (
        "You are a bank-transaction categorizer. For each of the following descriptions, "
        "assign a short, logical category (e.g., Groceries, Food, Travel, Shopping, Salary, Utilities). "
        "Return the output strictly as a JSON dictionary mapping the EXACT description string to its category.\n\n"
        f"Descriptions:\n{desc_list}"
    )
    
    text = llm.generate(prompt)
    if not text or text.startswith("[LLM error"):
        return {}
        
    import json
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
    except Exception:
        pass
        
    return {}
