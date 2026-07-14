"""Phase 4 tests: Explainable AI cards. Offline (RAG/LLM patched out)."""
from __future__ import annotations

import pytest

from agents import explainability
from agents.explainability import SUBJECTS, build_explanation


@pytest.fixture(autouse=True)
def _no_rag(monkeypatch):
    # Keep tests offline & fast: no vector search, no LLM provider probing.
    monkeypatch.setattr(explainability.retriever, "retrieve", lambda q, u: {"sources": []})
    monkeypatch.setattr(explainability, "_narrator", lambda: "groq")


@pytest.fixture()
def result() -> dict:
    return {
        "health_score": {
            "score": 70, "rating": "okay", "savings_rate": 0.12,
            "income": 100000, "expenses": 88000, "emergency_fund_months": 1.5,
            "active_emis": 2, "anomalies_count": 1, "reference_month": "2025-03",
        },
        "monthly_summary": {
            "category_totals": {"Food": -12000, "Rent": -25000, "Shopping": -9000},
            "months": ["2025-01", "2025-02", "2025-03"],
        },
        "forecast": {
            "next_month": "2025-04", "total_expense_forecast": 80000,
            "category_forecast": {"Food": 12000},
            "history": {"months": ["2025-01", "2025-02", "2025-03"]},
        },
        "anomalies": [{"date": "2025-03-10", "amount": -13170, "message": "High travel spend"}],
        "transactions": [
            {"date": "2025-03-01", "description": "SWIGGY", "amount": -450, "category": "Food"},
            {"date": "2025-03-10", "description": "MMT", "amount": -13170, "category": "Travel"},
            {"date": "2025-02-01", "description": "RENT", "amount": -25000, "category": "Rent"},
        ],
    }


_REQUIRED = {
    "subject", "title", "why", "evidence", "confidence",
    "retrieved_documents", "transactions_used", "formula", "model", "reasoning_summary",
}


def test_all_subjects_return_full_card(result):
    for s in SUBJECTS:
        card = build_explanation(s, result)
        assert _REQUIRED.issubset(card.keys())
        assert 0.0 <= card["confidence"] <= 1.0
        assert card["why"] and card["formula"] and card["reasoning_summary"]
        assert isinstance(card["evidence"], list) and card["evidence"]


def test_score_breakdown_matches_formula(result):
    card = build_explanation("score", result)
    joined = " ".join(card["evidence"])
    assert "Start at 100" in joined
    assert "− 15" in joined  # savings rate 12% < 20%
    assert "= 70" in joined
    assert card["confidence"] >= 0.95  # deterministic


def test_score_transactions_are_reference_month(result):
    card = build_explanation("score", result)
    assert card["transactions_used"]  # March txns only
    assert all(t["date"].startswith("2025-03") for t in card["transactions_used"])


def test_forecast_confidence_scales_with_history(result):
    few = {**result, "forecast": {**result["forecast"], "history": {"months": ["2025-03"]}}}
    many = {**result, "forecast": {**result["forecast"],
            "history": {"months": [f"2025-{m:02d}" for m in range(1, 8)]}}}
    assert build_explanation("forecast", many)["confidence"] > build_explanation("forecast", few)["confidence"]


def test_spending_top_category(result):
    card = build_explanation("spending", result)
    assert "Rent" in card["why"]  # largest at 25000


def test_unknown_subject_defaults_to_score(result):
    card = build_explanation("nonsense", result)
    assert card["subject"] == "score"


def test_no_chain_of_thought_leak(result):
    # Reasoning summary must be a conclusion, not step-by-step CoT.
    for s in SUBJECTS:
        card = build_explanation(s, result)
        low = card["reasoning_summary"].lower()
        assert "step 1" not in low and "let me think" not in low
