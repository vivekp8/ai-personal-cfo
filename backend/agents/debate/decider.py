"""Final Decision Agent: synthesises all specialist opinions into one
confidence-weighted, prioritised recommendation.
"""
from __future__ import annotations

import json
import logging

from agents import llm_client

from .base import AgentOpinion, _safe_generate

logger = logging.getLogger("agents.debate.decider")


def _weighted_confidence(opinions: list[AgentOpinion]) -> float:
    if not opinions:
        return 0.0
    return round(sum(o.confidence for o in opinions) / len(opinions), 2)


def _priorities(opinions: list[AgentOpinion]) -> list[dict]:
    """Rank the specialists' positions by confidence to form an action list."""
    ranked = sorted(opinions, key=lambda o: o.confidence, reverse=True)
    return [
        {"agent": o.agent, "icon": o.icon, "action": o.stance, "confidence": o.confidence}
        for o in ranked
    ]


def _deterministic_summary(opinions: list[AgentOpinion]) -> str:
    top = sorted(opinions, key=lambda o: o.confidence, reverse=True)[:3]
    parts = [f"{o.agent} — {o.stance} ({o.confidence:.0%})" for o in top]
    if not parts:
        return "No opinions were available to synthesise."
    joined = "; ".join(parts)
    return (
        f"Panel consensus, highest-confidence first: {joined}. "
        f"Act on these in order — secure the emergency fund and savings rate before "
        f"optimising budget, lifestyle, taxes, and investments."
    )


def decide(opinions: list[AgentOpinion], question: str | None) -> dict:
    """Return the final decision dict."""
    if not opinions:
        return {
            "summary": "No specialist opinions were produced.",
            "consensus_confidence": 0.0,
            "priorities": [],
            "llm_used": False,
        }

    consensus_conf = _weighted_confidence(opinions)
    priorities = _priorities(opinions)

    llm_summary = None
    if llm_client.is_configured():
        panel = [
            {"agent": o.agent, "stance": o.stance, "summary": o.summary, "confidence": o.confidence}
            for o in opinions
        ]
        prompt = f"""You are the Chair of a financial advisory panel. Below are the
specialists' opinions (each grounded in the user's real computed numbers).

Panel opinions:
{json.dumps(panel, indent=2)}

Panel question: {question or "What should this user do?"}

Write a single, concise final recommendation (3-5 sentences) that:
- reconciles the opinions and resolves any tension between them,
- states the top 2-3 prioritised actions in order,
- never invents numbers and does not expose step-by-step reasoning.
Return plain text only."""
        text, _retries, err = _safe_generate(prompt, timeout_s=14.0, attempts=1)
        if text and not text.startswith("[LLM error"):
            llm_summary = text.strip()
        else:
            logger.info("decider fell back to deterministic summary (%s)", err)

    return {
        "summary": llm_summary or _deterministic_summary(opinions),
        "consensus_confidence": consensus_conf,
        "priorities": priorities,
        "llm_used": bool(llm_summary),
    }
