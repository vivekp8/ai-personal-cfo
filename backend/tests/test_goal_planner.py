"""Phase 9 tests: Goal Planner engine + persistence."""
from __future__ import annotations

import pytest

from agents import goal_planner as g


def test_goal_types_include_presets():
    ids = {t["id"] for t in g.goal_types()}
    for expected in ("emergency_fund", "car", "house", "retirement", "custom"):
        assert expected in ids


def test_fixed_timeline_computes_required_monthly():
    p = g.plan_goal(
        goal_type="car", target_amount=800000, current_saved=100000,
        target_months=36, monthly_surplus=25000, emergency_fund_months=4,
    )
    assert p["timeline_months"] == 36
    assert p["required_monthly"] > 0
    # Surplus comfortably covers the requirement → high probability, low risk.
    assert p["completion_probability"] >= 0.9
    assert p["risk"] == "Low"
    assert p["trajectory"][0]["month"] == 0
    assert p["trajectory"][-1]["month"] == 36


def test_underfunded_goal_has_low_probability():
    p = g.plan_goal(
        goal_type="house", target_amount=5_000_000, current_saved=0,
        target_months=24, monthly_surplus=5000, emergency_fund_months=1,
    )
    # Required monthly hugely exceeds the surplus → low odds, high risk.
    assert p["completion_probability"] < 0.5
    assert p["risk"] == "High"


def test_auto_timeline_from_surplus():
    p = g.plan_goal(
        goal_type="vacation", target_amount=120000, current_saved=0,
        monthly_surplus=10000, emergency_fund_months=6,
    )
    assert p["timeline_months"] >= 1
    assert p["reachable"] is True


def test_unreachable_when_no_contribution_no_growth():
    p = g.plan_goal(
        goal_type="custom", target_amount=100000, current_saved=0,
        monthly_contribution=0, monthly_surplus=0, annual_return=0.0,
    )
    assert p["reachable"] is False
    assert p["completion_probability"] <= 0.1


def test_progress_pct():
    p = g.plan_goal(
        goal_type="emergency_fund", target_amount=100000, current_saved=25000,
        target_months=10, monthly_surplus=10000,
    )
    assert p["progress_pct"] == 25.0


def test_emergency_fund_fragility_penalty():
    strong = g.plan_goal(goal_type="car", target_amount=300000, current_saved=0,
                          target_months=12, monthly_surplus=30000, emergency_fund_months=6)
    weak = g.plan_goal(goal_type="car", target_amount=300000, current_saved=0,
                       target_months=12, monthly_surplus=30000, emergency_fund_months=1)
    assert weak["completion_probability"] < strong["completion_probability"]


def test_already_reached_goal():
    p = g.plan_goal(goal_type="custom", target_amount=1000, current_saved=1000,
                    target_months=12, monthly_surplus=5000)
    assert p["required_monthly"] == 0.0
    assert p["progress_pct"] == 100.0


def test_surplus_from_result():
    surplus, ef = g.surplus_from_result(
        {"health_score": {"income": 90000, "expenses": 60000, "emergency_fund_months": 2.5}}
    )
    assert surplus == 30000
    assert ef == 2.5


def test_goal_persistence(tmp_path, monkeypatch):
    from db import database

    monkeypatch.setattr(database, "_DB_PATH", str(tmp_path / "goals.db"))
    database.init_db()
    uid = "goal_user"
    assert database.list_goals(uid) == []
    gid = database.save_goal(uid, "New car", "car", 800000, 50000, 36, None)
    rows = database.list_goals(uid)
    assert len(rows) == 1 and rows[0]["name"] == "New car"
    assert database.delete_goal(gid, uid) is True
    assert database.list_goals(uid) == []
