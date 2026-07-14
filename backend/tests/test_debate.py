"""Phase 2 tests: Multi-Agent Debate System.

Runs entirely offline (LLM disabled) so specialists use their deterministic,
data-grounded heuristics. Also exercises the retry/timeout wrapper.
"""
from __future__ import annotations

import time

import pytest

from agents.debate import base, decider
from agents.debate.graph import _run_fallback, list_agents, run_debate
from agents.debate.specialists import PANEL


@pytest.fixture()
def data() -> dict:
    return {
        "health_score": {
            "score": 60,
            "savings_rate": 0.08,
            "income": 100000,
            "expenses": 88000,
            "emergency_fund_months": 1.5,
            "active_emis": 2,
            "anomalies_count": 3,
            "rating": "okay",
        },
        "monthly_summary": {
            "category_totals": {"Food": -12000, "Rent": -25000, "Shopping": -9000}
        },
        "savings_suggestions": [{"title": "Cut delivery", "monthly_savings": 2500}],
    }


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    # Force the deterministic path everywhere in the debate package.
    monkeypatch.setattr(base.llm_client, "is_configured", lambda: False)
    monkeypatch.setattr(decider.llm_client, "is_configured", lambda: False)


def test_panel_has_seven_specialists():
    assert len(PANEL) == 7
    # list_agents adds the Final Decision Agent → 8 total.
    assert len(list_agents()) == 8


def test_each_agent_produces_valid_opinion(data):
    for agent in PANEL:
        op = agent.analyze({"data": data, "question": "test"})
        assert op.agent == agent.name
        assert 0.0 <= op.confidence <= 1.0
        assert op.summary
        assert op.stance
        assert op.llm_used is False  # offline


def test_run_debate_full(data):
    out = run_debate(data, "Should I invest now?")
    assert len(out["opinions"]) == 7
    assert out["meta"]["agent_count"] == 7
    decision = out["decision"]
    assert 0.0 <= decision["consensus_confidence"] <= 1.0
    assert decision["summary"]
    assert len(decision["priorities"]) == 7
    # Priorities are ranked by confidence (descending).
    confs = [p["confidence"] for p in decision["priorities"]]
    assert confs == sorted(confs, reverse=True)


def test_fallback_path_matches_shape(data):
    out = _run_fallback(data, None)
    assert len(out["opinions"]) == 7
    assert "decision" in out


def test_confidence_is_clamped():
    op = base.AgentOpinion(
        agent="X", role="Y", stance="s", summary="t", confidence=5.0
    )
    assert op.confidence == 1.0
    op2 = base.AgentOpinion(agent="X", role="Y", stance="s", summary="t", confidence=-2)
    assert op2.confidence == 0.0


def test_safe_generate_times_out(monkeypatch):
    def slow(_prompt):
        time.sleep(5)
        return "late"

    monkeypatch.setattr(base.llm_client, "generate", slow)
    text, retries, err = base._safe_generate("p", timeout_s=0.2, attempts=2)
    assert text is None
    assert retries == 2
    assert "timeout" in (err or "")


def test_safe_generate_succeeds(monkeypatch):
    monkeypatch.setattr(base.llm_client, "generate", lambda p: "ok")
    text, retries, err = base._safe_generate("p", timeout_s=2, attempts=2)
    assert text == "ok"
    assert retries == 0
    assert err is None


def test_json_opinion_parsing():
    parsed = base._parse_json_opinion(
        'noise {"stance":"Boost savings","summary":"Do X.","key_points":["a","b"],"confidence":0.9} tail'
    )
    assert parsed is not None
    stance, summary, kp, conf = parsed
    assert stance == "Boost savings"
    assert kp == ["a", "b"]
    assert conf == 0.9
