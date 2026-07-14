"""Keyword-based categorization with an optional LLM fallback (Phase 4).

The keyword dictionary is the deterministic first pass. Merchants not matched
are marked "Uncategorized" here; the LLM fallback (llm_categorize) is wired in
during Phase 4 and only runs when a Gemini key is configured.
"""
from __future__ import annotations

# Order matters only for readability; matching checks all keywords.
KEYWORD_CATEGORIES: dict[str, str] = {
    # Shopping
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "myntra": "Shopping",
    "ajio": "Shopping",
    # Food / delivery
    "swiggy": "Food",
    "zomato": "Food",
    "big basket": "Food",
    "bigbasket": "Food",
    "dominos": "Food",
    "mcdonald": "Food",
    "dinner": "Food",
    "restaurant": "Food",
    # Travel
    "uber": "Travel",
    "ola": "Travel",
    "rapido": "Travel",
    "makemytrip": "Travel",
    "flight": "Travel",
    "irctc": "Travel",
    "indigo": "Travel",
    # Entertainment
    "netflix": "Entertainment",
    "prime": "Entertainment",
    "hotstar": "Entertainment",
    "spotify": "Entertainment",
    "youtube": "Entertainment",
    "bookmyshow": "Entertainment",
    # Housing
    "rent": "Housing",
    "maintenance": "Housing",
    # Utilities
    "electricity": "Utilities",
    "bescom": "Utilities",
    "water": "Utilities",
    "gas": "Utilities",
    "indane": "Utilities",
    "broadband": "Utilities",
    "airtel": "Utilities",
    "jio": "Utilities",
    "mobile": "Utilities",
    "recharge": "Utilities",
    # Income
    "salary": "Income",
    "credit interest": "Income",
    "refund": "Income",
    "cashback": "Income",
}

UNCATEGORIZED = "Uncategorized"


def categorize_one(description: str) -> str:
    desc = description.lower()
    for keyword, category in KEYWORD_CATEGORIES.items():
        if keyword in desc:
            return category
    return UNCATEGORIZED


def categorize(transactions: list[dict]) -> list[dict]:
    """Return transactions with a 'category' field added.

    Positive amounts that fall through keyword matching are treated as Income;
    everything else that is unmatched stays Uncategorized.
    """
    result = []
    for txn in transactions:
        category = categorize_one(txn["description"])
        if category == UNCATEGORIZED and txn["amount"] > 0:
            category = "Income"
        result.append({**txn, "category": category})
    return result


def llm_categorize(description: str) -> str | None:
    """Phase 4 LLM fallback. Returns a category string or None if unavailable.

    Imported lazily so the deterministic pipeline never depends on the LLM.
    """
    try:
        from agents.llm_client import categorize_with_llm
    except Exception:  # noqa: BLE001
        return None
    return categorize_with_llm(description, sorted(set(KEYWORD_CATEGORIES.values())))
