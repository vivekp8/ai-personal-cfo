"""Phase 3 tests: Digital Financial Twin projection engine + persistence."""
from __future__ import annotations

import pytest

from agents import twin


@pytest.fixture()
def base_scenario() -> twin.ScenarioInput:
    return twin.ScenarioInput(
        monthly_income=100000,
        monthly_expenses=70000,
        current_savings=200000,
        current_age=30,
        retirement_age=60,
        years=30,
        salary_growth=0.06,
        expense_growth=0.05,
        inflation=0.05,
        investment_return=0.10,
    )


def test_projection_length_and_shape(base_scenario):
    r = twin.simulate(base_scenario)
    assert len(r.projection) == 30
    first = r.projection[0]
    assert first.year == 1
    assert first.age == 31
    assert first.annual_income == pytest.approx(100000 * 12)


def test_net_worth_grows_with_positive_savings(base_scenario):
    r = twin.simulate(base_scenario)
    nws = [p.net_worth for p in r.projection]
    assert nws == sorted(nws)  # monotonically non-decreasing with positive savings
    assert r.final_net_worth > base_scenario.current_savings


def test_real_net_worth_below_nominal(base_scenario):
    r = twin.simulate(base_scenario)
    assert r.final_real_net_worth < r.final_net_worth  # inflation erodes value


def test_negative_savings_floors_at_zero():
    # Expenses exceed income → portfolio must not go negative.
    s = twin.ScenarioInput(
        monthly_income=40000,
        monthly_expenses=60000,
        current_savings=10000,
        years=10,
        investment_return=0.08,
    )
    r = twin.simulate(s)
    assert all(p.net_worth >= 0 for p in r.projection)
    assert r.final_net_worth == 0.0


def test_retirement_estimate(base_scenario):
    r = twin.simulate(base_scenario)
    assert r.retirement.applicable is True
    assert r.retirement.years_to_retirement == 30
    assert r.retirement.projected_corpus and r.retirement.projected_corpus > 0
    # 4% rule
    assert r.retirement.sustainable_annual_income == pytest.approx(
        r.retirement.projected_corpus * twin.SAFE_WITHDRAWAL_RATE, rel=1e-6
    )


def test_retirement_not_applicable_without_ages():
    s = twin.ScenarioInput(monthly_income=50000, monthly_expenses=30000, years=5)
    r = twin.simulate(s)
    assert r.retirement.applicable is False


def test_goal_timeline(base_scenario):
    base_scenario.goals = [
        twin.Goal(name="Car", target_amount=1_500_000),
        twin.Goal(name="Impossible", target_amount=10_000_000_000),
    ]
    r = twin.simulate(base_scenario)
    car = next(g for g in r.goals if g.name == "Car")
    imp = next(g for g in r.goals if g.name == "Impossible")
    assert car.reached is True
    assert car.year_reached is not None
    assert imp.reached is False


def test_defaults_from_result():
    result = {"health_score": {"income": 90000, "expenses": 60000}}
    d = twin.defaults_from_result(result)
    assert d["monthly_income"] == 90000
    assert d["monthly_expenses"] == 60000


def test_scenario_validation_rejects_bad_input():
    with pytest.raises(Exception):
        twin.ScenarioInput(monthly_income=-5, monthly_expenses=10)


def test_simulation_persistence(tmp_path, monkeypatch):
    from db import database

    monkeypatch.setattr(database, "_DB_PATH", str(tmp_path / "sim.db"))
    database.init_db()

    uid = "sim_user"
    assert database.list_simulations(uid) == []
    sid = database.save_simulation(uid, "Aggressive", {"salary_growth": 0.1}, {"final": 1})
    assert isinstance(sid, int)
    rows = database.list_simulations(uid)
    assert len(rows) == 1
    assert rows[0]["name"] == "Aggressive"

    got = database.get_simulation(sid)
    assert got is not None and got["user_id"] == uid

    assert database.delete_simulation(sid, uid) is True
    assert database.list_simulations(uid) == []
