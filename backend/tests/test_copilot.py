"""Phase 1 tests: AI Financial Copilot + conversation memory.

These tests avoid any real network/LLM calls by monkeypatching the LLM client,
and use an isolated temporary SQLite database for persistence.
"""
from __future__ import annotations

import importlib

import pytest

from agents import copilot


@pytest.fixture()
def sample_result() -> dict:
    return {
        "health_score": {
            "score": 72,
            "rating": "Good",
            "savings_rate": 0.22,
            "income": 100000,
            "expenses": 78000,
        },
        "monthly_summary": {
            "months": ["2024-01"],
            "by_month_category": {"2024-01": {"Food": 12000, "Rent": 25000}},
        },
        "forecast": {"next_month": "2024-02", "total_expense_forecast": 80000},
        "anomalies": [],
        "savings_suggestions": [],
    }


@pytest.fixture()
def empty_rag() -> dict:
    return {"context": "", "sources": [], "available": False}


def test_converse_uses_llm_when_configured(monkeypatch, sample_result, empty_rag):
    captured = {}

    def fake_generate(prompt: str):
        captured["prompt"] = prompt
        return "Your savings rate is 22%, which is healthy."

    monkeypatch.setattr(copilot.llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(copilot.llm_client, "generate", fake_generate)

    history = [
        {"role": "user", "content": "How is my health score?"},
        {"role": "assistant", "content": "It's 72, rated Good."},
    ]
    out = copilot.converse("Is that a good score?", sample_result, empty_rag, history)

    assert out["llm_used"] is True
    assert out["intent"] == "score"
    assert "22%" in out["response"]
    # Follow-up context must be threaded into the prompt.
    assert "It's 72, rated Good." in captured["prompt"]
    assert "Is that a good score?" in captured["prompt"]


def test_converse_falls_back_without_llm(monkeypatch, sample_result, empty_rag):
    monkeypatch.setattr(copilot.llm_client, "is_configured", lambda: False)
    out = copilot.converse("How is my score?", sample_result, empty_rag, [])

    assert out["llm_used"] is False
    assert "72" in out["response"]  # deterministic, grounded in computed data
    assert out["intent"] == "score"


def test_converse_handles_llm_error(monkeypatch, sample_result, empty_rag):
    monkeypatch.setattr(copilot.llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(
        copilot.llm_client, "generate", lambda prompt: "[LLM error: boom]"
    )
    out = copilot.converse("How is my score?", sample_result, empty_rag, [])

    assert out["llm_used"] is False
    assert out["llm_error"] == "[LLM error: boom]"
    assert "72" in out["response"]


def test_conversation_persistence(tmp_path, monkeypatch):
    # Point the DB module at an isolated temporary database.
    from db import database

    monkeypatch.setattr(database, "_DB_PATH", str(tmp_path / "test.db"))
    database.init_db()

    uid = "unit_user"
    assert database.get_conversation(uid) == []

    database.save_message(uid, "user", "hi", intent=None, llm_used=None)
    database.save_message(uid, "assistant", "hello", intent="spending", llm_used=True)

    convo = database.get_conversation(uid)
    assert [m["role"] for m in convo] == ["user", "assistant"]
    assert convo[1]["content"] == "hello"
    assert convo[1]["llm_used"] is True
    assert convo[1]["intent"] == "spending"

    removed = database.clear_conversation(uid)
    assert removed == 2
    assert database.get_conversation(uid) == []


def test_history_ordering_and_limit(tmp_path, monkeypatch):
    from db import database

    monkeypatch.setattr(database, "_DB_PATH", str(tmp_path / "test2.db"))
    database.init_db()
    uid = "order_user"
    for i in range(10):
        database.save_message(uid, "user", f"msg-{i}")

    recent = database.get_conversation(uid, limit=3)
    assert [m["content"] for m in recent] == ["msg-7", "msg-8", "msg-9"]


def test_module_imports_cleanly():
    # Guards against import-time regressions in the copilot wiring.
    importlib.reload(copilot)
    assert hasattr(copilot, "converse")
