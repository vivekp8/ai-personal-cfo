"""Debate orchestration.

Builds a LangGraph where every specialist runs from START in parallel, writing
its opinion into a shared, reducer-merged ``opinions`` list, then a single
decider node synthesises the final recommendation. If LangGraph is not
installed, the same agents run concurrently via a thread pool and the decider
is called directly — identical results, no crash.
"""
from __future__ import annotations

import logging
import operator
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Annotated, TypedDict

from .base import AgentOpinion
from .decider import decide
from .specialists import PANEL

logger = logging.getLogger("agents.debate.graph")


def _agent_llm_enabled() -> bool:
    """Opt-in per-agent LLM enrichment. Default OFF: 8 LLM calls per debate is
    slow and hits provider rate limits. Set DEBATE_AGENT_LLM=1 for higher-tier
    keys. The decider always makes one LLM call for the final synthesis.
    """
    import os

    return os.getenv("DEBATE_AGENT_LLM", "0").strip().lower() in {"1", "true", "yes"}


class DebateState(TypedDict, total=False):
    data: dict
    question: str
    # Reducer merges concurrent writes from every specialist branch.
    opinions: Annotated[list, operator.add]
    decision: dict


def list_agents() -> list[dict]:
    """Metadata for the panel (used by the frontend / API)."""
    return [
        {"name": a.name, "role": a.role, "icon": a.icon, "focus": a.focus}
        for a in PANEL
    ] + [{"name": "Final Decision Agent", "role": "Panel Chair", "icon": "⚖️",
          "focus": "synthesise all specialist opinions into one prioritised recommendation"}]


def _make_specialist_node(agent):
    def _node(state: DebateState) -> dict:
        ctx = {
            "data": state.get("data", {}),
            "question": state.get("question"),
            "use_llm": _agent_llm_enabled(),
        }
        opinion = agent.analyze(ctx)
        return {"opinions": [opinion.model_dump()]}

    return _node


def _decider_node(state: DebateState) -> dict:
    opinions = [AgentOpinion(**o) for o in state.get("opinions", [])]
    return {"decision": decide(opinions, state.get("question"))}


def _build_graph():
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception:  # noqa: BLE001
        return None
    try:
        graph = StateGraph(DebateState)
        for agent in PANEL:
            graph.add_node(agent.name, _make_specialist_node(agent))
            graph.add_edge(START, agent.name)
            graph.add_edge(agent.name, "decider")
        graph.add_node("decider", _decider_node)
        graph.add_edge("decider", END)
        return graph.compile()
    except Exception as exc:  # noqa: BLE001
        logger.warning("LangGraph debate build failed, using fallback: %s", exc)
        return None


_COMPILED = _build_graph()


# Hard cap on the whole debate so the endpoint never hangs even if a provider
# stalls. On breach we return instant, data-grounded heuristic opinions.
OVERALL_TIMEOUT_S = 45.0


def _heuristic_opinions(data: dict) -> list[AgentOpinion]:
    """Instant, LLM-free opinions from each specialist's heuristic."""
    opinions: list[AgentOpinion] = []
    for a in PANEL:
        stance, summary, points, conf = a.heuristic(data)
        opinions.append(
            AgentOpinion(
                agent=a.name,
                role=a.role,
                icon=a.icon,
                stance=stance,
                summary=summary,
                key_points=points,
                confidence=conf,
                llm_used=False,
            )
        )
    return opinions


def _run_fallback(data: dict, question: str | None) -> dict:
    """Concurrent, dependency-free execution path (agents may still use the LLM)."""
    opinions: list[AgentOpinion] = []
    use_llm = _agent_llm_enabled()
    with ThreadPoolExecutor(max_workers=len(PANEL)) as pool:
        futures = [
            pool.submit(a.analyze, {"data": data, "question": question, "use_llm": use_llm})
            for a in PANEL
        ]
        for f in futures:
            opinions.append(f.result())
    decision = decide(opinions, question)
    return {"opinions": [o.model_dump() for o in opinions], "decision": decision}


def _run_core(data: dict, question: str | None) -> tuple[dict, bool]:
    """Execute the panel via LangGraph if available, else the concurrent path."""
    if _COMPILED is not None:
        try:
            state = _COMPILED.invoke({"data": data, "question": question, "opinions": []})
            return {
                "opinions": state.get("opinions", []),
                "decision": state.get("decision", {}),
            }, True
        except Exception as exc:  # noqa: BLE001
            logger.warning("LangGraph debate invoke failed, falling back: %s", exc)
    return _run_fallback(data, question), False


def run_debate(data: dict, question: str | None = None) -> dict:
    """Run the full panel and return {opinions, decision, meta}."""
    started = time.perf_counter()
    used_langgraph = _COMPILED is not None
    timed_out = False
    try:
        with ThreadPoolExecutor(max_workers=1) as guard:
            fut = guard.submit(_run_core, data, question)
            result, used_langgraph = fut.result(timeout=OVERALL_TIMEOUT_S)
    except FuturesTimeout:
        logger.warning(
            "debate exceeded %.0fs — returning heuristic opinions", OVERALL_TIMEOUT_S
        )
        timed_out = True
        opinions = _heuristic_opinions(data)
        result = {
            "opinions": [o.model_dump() for o in opinions],
            "decision": decide(opinions, question),
        }
        used_langgraph = False

    # Keep opinions in the canonical panel order for stable UI rendering.
    order = {a.name: i for i, a in enumerate(PANEL)}
    result["opinions"].sort(key=lambda o: order.get(o.get("agent"), 999))

    elapsed = (time.perf_counter() - started) * 1000
    decision_llm = bool((result.get("decision") or {}).get("llm_used"))
    result["meta"] = {
        "agent_count": len(PANEL),
        "langgraph": used_langgraph,
        "elapsed_ms": round(elapsed, 1),
        "llm_used": any(o.get("llm_used") for o in result["opinions"]) or decision_llm,
        "timed_out": timed_out,
    }
    logger.info(
        "debate complete agents=%d langgraph=%s elapsed=%.0fms",
        len(PANEL), used_langgraph, elapsed,
    )
    return result
