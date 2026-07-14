"""Phase 7 tests: workflow tracing over the analysis pipeline (any format)."""
from __future__ import annotations

import pytest

from orchestrator.trace import WORKFLOW_NODES, WorkflowTracer, build_graph


def test_build_graph_shape():
    g = build_graph()
    ids = [n["id"] for n in g["nodes"]]
    for required in ("upload", "parser", "categorizer", "forecast", "health_score",
                     "memory", "persist", "retriever", "llm", "response"):
        assert required in ids
    # edges chain consecutive nodes
    assert len(g["edges"]) == len(g["nodes"]) - 1


def test_tracer_records_ok_with_timing_and_detail():
    t = WorkflowTracer()
    out = t.step("parser", lambda: [1, 2, 3], detail_fn=lambda o: f"{len(o)} rows")
    assert out == [1, 2, 3]
    lst = {n["id"]: n for n in t.as_list()}
    assert lst["parser"]["status"] == "ok"
    assert lst["parser"]["detail"] == "3 rows"
    assert lst["parser"]["duration_ms"] >= 0


def test_tracer_retries_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("boom")
        return "ok"

    t = WorkflowTracer()
    out = t.step("categorizer", flaky, retries=2)
    assert out == "ok"
    rec = {n["id"]: n for n in t.as_list()}["categorizer"]
    assert rec["status"] == "ok"
    assert rec["retries"] == 1


def test_tracer_records_error_and_reraises():
    t = WorkflowTracer()
    with pytest.raises(ValueError):
        t.step("anomaly", lambda: (_ for _ in ()).throw(ValueError("bad")))
    rec = {n["id"]: n for n in t.as_list()}["anomaly"]
    assert rec["status"] == "error"
    assert "bad" in rec["error"]


def test_deferred_nodes_marked():
    t = WorkflowTracer()
    lst = {n["id"]: n for n in t.as_list()}
    # chat-stage nodes are deferred until a question is asked
    assert lst["llm"]["status"] == "deferred"
    # un-run analysis nodes are pending
    assert lst["parser"]["status"] == "pending"


def test_total_ms_accumulates():
    t = WorkflowTracer()
    t.step("a", lambda: 1)
    t.step("b", lambda: 2)
    assert t.total_ms() >= 0


def test_run_pipeline_traced_over_csv(monkeypatch):
    # A tiny CSV must flow through every analysis node and be traced.
    # Keep it hermetic: force deterministic (rule-based) categorization, no network.
    from agents import llm_client
    monkeypatch.setattr(llm_client, "is_configured", lambda: False)
    monkeypatch.setattr(llm_client, "categorize_with_llm", lambda *a, **k: None)

    from orchestrator.pipeline import run_pipeline_traced

    csv = "date,description,amount\n2025-01-05,Salary,50000\n2025-01-06,Rent,-15000\n"
    t = WorkflowTracer()
    state = run_pipeline_traced(csv, "test_user", "statement.csv", t)
    assert state.get("categorized")
    recorded = {n["id"]: n for n in t.as_list()}
    for node in ("parser", "categorizer", "aggregator", "forecast", "health_score"):
        assert recorded[node]["status"] == "ok"
