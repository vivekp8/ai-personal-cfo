"""Keyword-based intent router (Phase 2 step 4).

Routes a chat query to a coarse intent so the explainer can pull the right
slice of state. LLM handles final phrasing.
"""
from __future__ import annotations

_INTENTS = {
    "whatif": ["what if", "what-if", "should i buy", "afford", "emi", "loan", "purchase"],
    "forecast": ["predict", "forecast", "next month", "will i", "future"],
    "anomaly": ["anomaly", "unusual", "spike", "why did", "why is", "strange"],
    "score": ["score", "health", "rating", "how am i doing"],
    "savings": ["save", "cut back", "reduce", "budget", "advice", "suggest"],
    "spending": ["spend", "spent", "how much", "category", "food", "shopping"],
}


def route_intent(query: str) -> str:
    q = query.lower()
    for intent, keywords in _INTENTS.items():
        if any(kw in q for kw in keywords):
            return intent
    return "spending"
