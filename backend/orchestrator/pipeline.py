"""Phase 2: wrap the deterministic pipeline in LangGraph nodes.

Each node reads/writes the shared CFOState. The math is identical to the
plain Phase 1 functions; LangGraph is orchestration only. If LangGraph is not
installed, we fall back to running the same nodes sequentially so the app
still works.
"""
from __future__ import annotations

from agents.aggregation import aggregate_monthly
from agents.anomaly import detect_anomalies
from agents.categorization import categorize
from agents.forecasting import forecast_next_month
from agents.health_score import build_health_score
from agents.ingestion_agent import parse_statement
from agents.savings_advisor import suggest_savings
from orchestrator.state import CFOState


# --- Nodes ---
def node_ingestion(state: CFOState) -> CFOState:
    filename = state.get("filename")
    raw = state.get("raw_bytes")
    if raw is None:
        content = state.get("raw_csv_content")
        if content is None and state.get("raw_csv_path"):
            with open(state["raw_csv_path"], "rb") as fh:
                raw = fh.read()
        else:
            raw = content or ""
    state["transactions"] = parse_statement(raw, filename)
    return state


def node_categorization(state: CFOState) -> CFOState:
    state["categorized"] = categorize(state["transactions"])
    return state


def node_aggregation(state: CFOState) -> CFOState:
    state["monthly_summary"] = aggregate_monthly(state["categorized"])
    return state


def node_anomaly(state: CFOState) -> CFOState:
    state["anomalies"] = detect_anomalies(state["categorized"], state["monthly_summary"])
    return state


def node_forecast(state: CFOState) -> CFOState:
    state["forecast"] = forecast_next_month(state["monthly_summary"])
    return state


def node_health_score(state: CFOState) -> CFOState:
    state["health_score"] = build_health_score(
        state["monthly_summary"], state["anomalies"]
    )
    return state


def node_savings(state: CFOState) -> CFOState:
    state["savings_suggestions"] = suggest_savings(
        state["categorized"], state["monthly_summary"]
    )
    return state


_ORDER = [
    node_ingestion,
    node_categorization,
    node_aggregation,
    node_anomaly,
    node_forecast,
    node_health_score,
    node_savings,
]


def _build_langgraph():
    """Build a compiled LangGraph if the library is available, else None."""
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception:  # noqa: BLE001
        return None

    graph = StateGraph(CFOState)
    names = [
        "ingestion_node",
        "categorization_node",
        "aggregation_node",
        "anomaly_node",
        "forecast_node",
        "health_score_node",
        "savings_node",
    ]
    for name, fn in zip(names, _ORDER):
        graph.add_node(name, fn)
    graph.add_edge(START, names[0])
    for a, b in zip(names, names[1:]):
        graph.add_edge(a, b)
    graph.add_edge(names[-1], END)
    return graph.compile()


_COMPILED = _build_langgraph()


def run_pipeline(
    content: str | bytes, user_id: str, filename: str | None = None
) -> CFOState:
    """Run the full upload pipeline and return the populated state.

    ``content`` may be decoded text (CSV) or raw bytes (any supported format).
    ``filename`` is used to pick the right parser for binary formats.
    """
    state: CFOState = {"user_id": user_id, "filename": filename or ""}
    if isinstance(content, bytes):
        state["raw_bytes"] = content
    else:
        state["raw_csv_content"] = content
    if _COMPILED is not None:
        return _COMPILED.invoke(state)  # type: ignore[return-value]
    for node in _ORDER:
        state = node(state)
    return state


def using_langgraph() -> bool:
    return _COMPILED is not None


# --- Phase 7: traced execution (same nodes, instrumented) ---
# (node_id, node_fn, detail extractor) — reuses the exact production nodes.
_TRACED_STEPS = [
    ("parser", node_ingestion, lambda s: f"{len(s.get('transactions', []))} transactions"),
    ("categorizer", node_categorization, lambda s: f"{len(s.get('categorized', []))} tagged"),
    ("aggregator", node_aggregation,
     lambda s: f"{len(s.get('monthly_summary', {}).get('months', []))} months"),
    ("anomaly", node_anomaly, lambda s: f"{len(s.get('anomalies', []))} anomalies"),
    ("forecast", node_forecast,
     lambda s: f"next: {s.get('forecast', {}).get('next_month', '?')}"),
    ("health_score", node_health_score,
     lambda s: f"score {s.get('health_score', {}).get('score', '?')}"),
    ("savings", node_savings, lambda s: f"{len(s.get('savings_suggestions', []))} tips"),
]


def run_pipeline_traced(
    content: str | bytes, user_id: str, filename: str | None, tracer
) -> CFOState:
    """Run the same pipeline nodes sequentially with per-node tracing.

    Produces identical results to ``run_pipeline`` (LangGraph is orchestration
    only over these same functions) while capturing timing/status/errors.
    """
    state: CFOState = {"user_id": user_id, "filename": filename or ""}
    if isinstance(content, bytes):
        state["raw_bytes"] = content
    else:
        state["raw_csv_content"] = content

    for node_id, fn, detail in _TRACED_STEPS:
        state = tracer.step(
            node_id,
            (lambda f=fn, s=state: f(s)),
            detail_fn=(lambda out, d=detail: d(out)),
        )
    return state
