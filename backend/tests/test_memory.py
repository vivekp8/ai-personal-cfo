"""Phase 5 tests: Long-Term Memory extraction, persistence, and recall.

Offline: embedding into ChromaDB is stubbed so tests are fast and deterministic.
"""
from __future__ import annotations

import pytest

from agents import memory


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    from db import database

    monkeypatch.setattr(database, "_DB_PATH", str(tmp_path / "mem.db"))
    database.init_db()
    # Don't touch ChromaDB / the embedding model in unit tests.
    monkeypatch.setattr(memory, "_embed", lambda user_id, items: None)


@pytest.fixture()
def result() -> dict:
    return {
        "monthly_summary": {
            "monthly_income": {"2025-01": 100000, "2025-02": 100000, "2025-03": 100000},
            "category_totals": {"Food": -36000, "Rent": -75000},
        },
        "health_score": {"savings_rate": 0.12, "score": 70},
        "transactions": [
            {"date": "2025-01-05", "description": "NETFLIX SUBSCRIPTION", "amount": -499},
            {"date": "2025-02-05", "description": "NETFLIX SUBSCRIPTION", "amount": -499},
            {"date": "2025-03-05", "description": "NETFLIX SUBSCRIPTION", "amount": -499},
            {"date": "2025-01-01", "description": "RENT PAYMENT", "amount": -25000},
            {"date": "2025-02-01", "description": "RENT PAYMENT", "amount": -25000},
            {"date": "2025-01-09", "description": "ONE OFF GADGET", "amount": -8000},
        ],
    }


def test_extract_detects_all_kinds(result):
    items = memory.extract_memories(result)
    kinds = {i["kind"] for i in items}
    assert {"salary", "subscription", "recurring", "habit"} <= kinds
    # Netflix recognised as a subscription, rent as generic recurring.
    subs = [i for i in items if i["kind"] == "subscription"]
    assert any("NETFLIX" in i["content"].upper() for i in subs)


def test_one_off_not_recurring(result):
    items = memory.extract_memories(result)
    # The single gadget purchase appears once → must NOT be recurring.
    assert not any("GADGET" in i["content"].upper() for i in items)


def test_salary_history_per_month(result):
    items = memory.extract_memories(result)
    salary = [i for i in items if i["kind"] == "salary"]
    assert len(salary) == 3


def test_remember_and_recall(result):
    n = memory.remember_from_result("u1", result)
    assert n >= 6
    ctx = memory.recall_context("u1")
    assert "Netflix".lower() in ctx.lower() or "netflix" in ctx.lower()
    assert "savings rate" in ctx.lower()


def test_preferences_and_goals():
    memory.set_preference("u2", "risk_tolerance", "conservative")
    memory.add_goal("u2", "Buy a car", target_amount=1_500_000, note="in 2 years")
    grouped = memory.all_memories("u2")
    assert grouped["preference"]
    assert grouped["goal"]
    assert grouped["goal"][0]["data"]["target_amount"] == 1_500_000


def test_conversation_summary():
    history = [
        {"role": "user", "content": "How much did I spend on food?"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "What is my savings rate?"},
    ]
    summary = memory.summarize_conversation("u3", history)
    assert summary and "savings rate" in summary.lower()
    grouped = memory.all_memories("u3")
    assert grouped["conversation_summary"]


def test_all_memories_grouped_by_kind(result):
    memory.remember_from_result("u4", result)
    grouped = memory.all_memories("u4")
    assert set(grouped.keys()) >= set(memory.KINDS)
    assert grouped["salary"] and grouped["habit"]


def test_recall_empty_for_unknown_user():
    assert memory.recall_context("nobody") == ""
