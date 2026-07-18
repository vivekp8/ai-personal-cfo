"""Keyword-based categorization with an optional LLM fallback (Phase 4).

The keyword dictionary is the deterministic first pass. Merchants not matched
are marked "Uncategorized" here; the LLM fallback (llm_categorize) is wired in
during Phase 4 and only runs when a Gemini key is configured.
"""
from __future__ import annotations

# Order matters only for readability; matching checks all keywords.
UNCATEGORIZED = "Uncategorized"

def categorize(transactions: list[dict]) -> list[dict]:
    """Return transactions with a 'category' field added.

    If a category is already present (e.g. from LLM ingestion), it is kept.
    Otherwise, unique uncategorized descriptions are batched and categorized via LLM.
    """
    # 1. Identify which descriptions need categorization
    missing_descriptions = set()
    for txn in transactions:
        cat = txn.get("category", "")
        if not cat or cat == UNCATEGORIZED:
            missing_descriptions.add(txn["description"])

    # 2. Batch categorize via LLM
    category_map = {}
    if missing_descriptions:
        try:
            from agents.llm_client import categorize_with_llm
            category_map = categorize_with_llm(list(missing_descriptions))
        except Exception:  # noqa: BLE001
            pass

    # 3. Apply categories
    result = []
    for txn in transactions:
        cat = txn.get("category", "")
        if not cat or cat == UNCATEGORIZED:
            desc = txn["description"]
            cat = category_map.get(desc, UNCATEGORIZED)
            if cat == UNCATEGORIZED and txn["amount"] > 0:
                cat = "Income"
        result.append({**txn, "category": cat})
    return result
