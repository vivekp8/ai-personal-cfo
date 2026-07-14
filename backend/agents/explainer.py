"""Explainer / Chat agent (Phase 4).

Takes a user query + retrieved RAG context + the relevant slice of computed
state, and asks Gemini to phrase a grounded answer. The LLM only narrates
numbers that were already computed deterministically; it must not invent them.

If the LLM is not configured, returns a deterministic templated answer so the
app still responds (clearly marked as non-LLM).
"""
from __future__ import annotations

import json

from agents import llm_client
from orchestrator.intent_router import route_intent


def _relevant_slice(intent: str, result: dict) -> dict:
    if intent == "score":
        return {"health_score": result.get("health_score")}
    if intent == "forecast":
        return {"forecast": result.get("forecast")}
    if intent == "anomaly":
        return {"anomalies": result.get("anomalies")}
    if intent == "savings":
        return {"savings_suggestions": result.get("savings_suggestions")}
    if intent == "whatif":
        return {"whatif_result": result.get("whatif_result")}
    # spending / default
    return {
        "monthly_summary": result.get("monthly_summary"),
        "health_score": result.get("health_score"),
    }


def _fallback_answer(intent: str, data: dict) -> str:
    if intent == "score":
        hs = data.get("health_score") or {}
        return (
            f"Your financial health score is {hs.get('score', 'N/A')} "
            f"({hs.get('rating', 'unknown')}), with a savings rate of "
            f"{hs.get('savings_rate', 0):.0%}. (LLM not configured — showing computed values.)"
        )
    if intent == "anomaly":
        anoms = data.get("anomalies") or []
        if not anoms:
            return "No spending anomalies were detected. (LLM not configured.)"
        lines = "\n".join(f"- {a.get('message')}" for a in anoms[:5])
        return f"Detected anomalies:\n{lines}\n(LLM not configured — showing computed values.)"
    if intent == "forecast":
        fc = data.get("forecast") or {}
        return (
            f"Forecast for {fc.get('next_month')}: expenses ~Rs."
            f"{fc.get('total_expense_forecast', 0):,.0f}. (LLM not configured.)"
        )
    if intent == "savings":
        sugg = data.get("savings_suggestions") or []
        lines = "\n".join(f"- {s.get('title')}: {s.get('detail')}" for s in sugg)
        return f"Savings suggestions:\n{lines}\n(LLM not configured.)"
    return (
        "Here is your computed financial data. Configure GEMINI_API_KEY for "
        "natural-language explanations.\n" + json.dumps(data, indent=2)
    )


def explain(query: str, result: dict, rag: dict) -> dict:
    """Return {response, intent, retrieved_context, llm_used}."""
    intent = route_intent(query)
    data_slice = _relevant_slice(intent, result)

    context = rag.get("context", "")
    prompt = f"""You are "AI Personal CFO", a friendly, precise personal finance assistant.

You must ONLY use the numbers provided below. Never invent or recompute financial
figures. If a number is not present, say you don't have it. Be concise and warm.

Retrieved financial knowledge and user memory:
{context or "(none)"}

Computed financial data (the source of truth for all numbers):
{json.dumps(data_slice, indent=2, default=str)}

User question: {query}

Answer in 2-5 sentences, referencing the user's actual numbers where relevant."""

    llm_response = llm_client.generate(prompt) if llm_client.is_configured() else None

    if llm_response and not llm_response.startswith("[LLM error"):
        return {
            "response": llm_response,
            "intent": intent,
            "retrieved_context": rag.get("sources", []),
            "llm_used": True,
        }

    return {
        "response": _fallback_answer(intent, data_slice),
        "intent": intent,
        "retrieved_context": rag.get("sources", []),
        "llm_used": False,
        "llm_error": llm_response if llm_response else None,
    }
