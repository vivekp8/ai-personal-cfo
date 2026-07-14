"""AI Financial Copilot (Phase 1).

A memory-aware, multi-turn conversational layer on top of the deterministic
financial data. It extends the single-shot ``explainer.explain`` with:

  - Conversation history (follow-up questions resolve against prior turns).
  - RAG grounding (financial knowledge + per-user memory).
  - Intent-scoped data slices so the model only sees relevant numbers.
  - Strict "never invent numbers" grounding — the LLM narrates computed values
    only; if a figure is absent it must say so.

If no LLM provider is configured, it degrades to the deterministic templated
answer from the explainer, clearly marked as computed (not LLM-generated).
"""
from __future__ import annotations

import json
import logging

from agents import llm_client
from agents.explainer import _fallback_answer, _relevant_slice
from orchestrator.intent_router import route_intent

logger = logging.getLogger("agents.copilot")

# How many prior turns (user+assistant messages) to feed back into the prompt.
MAX_HISTORY_MESSAGES = 10


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(This is the first message in the conversation.)"
    recent = history[-MAX_HISTORY_MESSAGES:]
    lines: list[str] = []
    for m in recent:
        who = "User" if m.get("role") == "user" else "CFO"
        content = (m.get("content") or "").strip()
        if content:
            lines.append(f"{who}: {content}")
    return "\n".join(lines) if lines else "(This is the first message.)"


def _build_prompt(
    query: str, data_slice: dict, context: str, history: list[dict], memory_context: str = ""
) -> str:
    return f"""You are "AI Personal CFO", a friendly, precise personal finance copilot.

STRICT RULES:
- Use ONLY the numbers in "Computed financial data" below. Never invent, guess,
  or recompute financial figures. If a number is not present, say you don't have it.
- Resolve follow-up questions (e.g. "why?", "what about last month?", "and that one?")
  using the conversation so far.
- Use "What you remember about this user" for durable context (goals, habits,
  subscriptions, preferences) but never override the computed figures with it.
- Be concise, warm, and concrete. Reference the user's actual numbers.
- Do not reveal your internal reasoning steps; give the answer directly.

What you remember about this user (long-term memory):
{memory_context or "(nothing remembered yet)"}

Conversation so far:
{_format_history(history)}

Retrieved financial knowledge and user memory:
{context or "(none)"}

Computed financial data (the source of truth for all numbers):
{json.dumps(data_slice, indent=2, default=str)}

User's new question: {query}

Answer in 2-5 sentences, grounded in the user's numbers and the conversation above."""


def converse(
    query: str,
    result: dict,
    rag: dict,
    history: list[dict] | None = None,
    memory_context: str = "",
) -> dict:
    """Return {response, intent, retrieved_context, llm_used}.

    ``history`` is the prior conversation (chronological list of
    ``{role, content}``). ``memory_context`` is a compact string of durable
    long-term memories. Both are prompt context only; persistence is the
    caller's responsibility.
    """
    history = history or []
    intent = route_intent(query)
    data_slice = _relevant_slice(intent, result)
    context = rag.get("context", "")

    prompt = _build_prompt(query, data_slice, context, history, memory_context)

    llm_response = llm_client.generate(prompt) if llm_client.is_configured() else None

    if llm_response and not llm_response.startswith("[LLM error"):
        logger.info(
            "copilot answered intent=%s history_len=%d llm_used=True", intent, len(history)
        )
        return {
            "response": llm_response,
            "intent": intent,
            "retrieved_context": rag.get("sources", []),
            "llm_used": True,
        }

    if llm_response:
        logger.warning("copilot LLM error, using fallback: %s", llm_response)
    else:
        logger.info("copilot LLM not configured, using deterministic fallback")

    return {
        "response": _fallback_answer(intent, data_slice),
        "intent": intent,
        "retrieved_context": rag.get("sources", []),
        "llm_used": False,
        "llm_error": llm_response if llm_response else None,
    }
