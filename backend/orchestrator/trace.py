"""Phase 7 — Workflow tracing.

Captures per-node execution status, duration, retries, and errors as the
analysis pipeline runs, so the frontend can animate the real LangGraph
execution. Works for ANY supported upload format — the parser node reports the
detected format and every downstream node runs identically.
"""
from __future__ import annotations

import time
from typing import Callable

# The full analysis graph. Upload → parse → analyse → remember → persist are
# executed on upload; the chat stages (retriever/llm/response) run per question
# and are shown as "deferred" until the user asks something.
WORKFLOW_NODES: list[dict] = [
    {"id": "upload", "label": "Upload", "group": "ingest",
     "desc": "Receive the file — any supported format"},
    {"id": "parser", "label": "Parser", "group": "ingest",
     "desc": "Detect format and extract transactions"},
    {"id": "categorizer", "label": "Categorizer", "group": "analyze",
     "desc": "Tag each transaction to a category"},
    {"id": "aggregator", "label": "Aggregator", "group": "analyze",
     "desc": "Monthly totals by category"},
    {"id": "anomaly", "label": "Anomaly Detector", "group": "analyze",
     "desc": "Flag unusual spikes"},
    {"id": "forecast", "label": "Forecaster", "group": "analyze",
     "desc": "Predict next month's expenses"},
    {"id": "health_score", "label": "Health Score", "group": "analyze",
     "desc": "Compute the financial health score"},
    {"id": "savings", "label": "Savings Advisor", "group": "analyze",
     "desc": "Suggest savings opportunities"},
    {"id": "memory", "label": "Memory", "group": "memory",
     "desc": "Embed + remember durable facts"},
    {"id": "persist", "label": "Persist", "group": "memory",
     "desc": "Save results to the database"},
    {"id": "retriever", "label": "Retriever", "group": "chat", "deferred": True,
     "desc": "RAG over knowledge + your memory (on each question)"},
    {"id": "llm", "label": "LLM Router", "group": "chat", "deferred": True,
     "desc": "Gemini → Groq → GitHub → OpenRouter → Ollama failover"},
    {"id": "response", "label": "Response", "group": "chat", "deferred": True,
     "desc": "Grounded, spoken/typed answer"},
]

WORKFLOW_EDGES = [
    {"from": a["id"], "to": b["id"]}
    for a, b in zip(WORKFLOW_NODES, WORKFLOW_NODES[1:])
]


class WorkflowTracer:
    """Records the outcome of each node. Never masks errors — it re-raises after
    recording so the caller's existing error handling is unchanged."""

    def __init__(self) -> None:
        self._records: dict[str, dict] = {}

    def record(
        self, node_id: str, status: str, duration_ms: float = 0.0,
        retries: int = 0, error: str | None = None, detail: str | None = None,
    ) -> None:
        self._records[node_id] = {
            "status": status,
            "duration_ms": round(duration_ms, 1),
            "retries": retries,
            "error": error,
            "detail": detail,
        }

    def step(
        self, node_id: str, fn: Callable[[], object], *,
        detail_fn: Callable[[object], str] | None = None, retries: int = 0,
    ):
        """Run ``fn`` timed; record ok/error; re-raise on final failure."""
        attempt = 0
        while True:
            started = time.perf_counter()
            try:
                out = fn()
                dur = (time.perf_counter() - started) * 1000
                detail = None
                try:
                    detail = detail_fn(out) if detail_fn else None
                except Exception:  # noqa: BLE001
                    detail = None
                self.record(node_id, "ok", dur, attempt, None, detail)
                return out
            except Exception as exc:  # noqa: BLE001
                if attempt < retries:
                    attempt += 1
                    continue
                dur = (time.perf_counter() - started) * 1000
                self.record(node_id, "error", dur, attempt, str(exc), None)
                raise

    def as_list(self) -> list[dict]:
        """Merge recorded outcomes onto the static node list, in graph order."""
        out: list[dict] = []
        for node in WORKFLOW_NODES:
            rec = self._records.get(node["id"])
            if rec:
                out.append({**node, **rec})
            else:
                out.append({
                    **node,
                    "status": "deferred" if node.get("deferred") else "pending",
                    "duration_ms": 0.0, "retries": 0, "error": None, "detail": None,
                })
        return out

    def total_ms(self) -> float:
        return round(sum(r["duration_ms"] for r in self._records.values()), 1)


def build_graph() -> dict:
    """Static graph definition for the visualiser skeleton (no run needed)."""
    return {"nodes": WORKFLOW_NODES, "edges": WORKFLOW_EDGES}
