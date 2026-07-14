"""Phase 9 — Goal Planner.

Deterministic planning for savings goals (emergency fund, vacation, car, house,
wedding, education, retirement, custom). Given a target and the user's monthly
surplus (or an explicit contribution), it computes the required monthly saving,
the timeline, a transparent completion probability, and a risk level.

No LLM, no randomness — every output is reproducible from the inputs. The
emergency-fund depth applies a fragility penalty: the same funding coverage is
less certain when the safety net is thin.
"""
from __future__ import annotations

import math

GOAL_TYPES: dict[str, dict] = {
    "emergency_fund": {"label": "Emergency Fund", "icon": "🛟"},
    "vacation": {"label": "Vacation", "icon": "🏖️"},
    "car": {"label": "Car", "icon": "🚗"},
    "house": {"label": "House", "icon": "🏠"},
    "wedding": {"label": "Wedding", "icon": "💍"},
    "education": {"label": "Education", "icon": "🎓"},
    "retirement": {"label": "Retirement", "icon": "🌴"},
    "custom": {"label": "Custom Goal", "icon": "🎯"},
}

# Trajectory points are capped so charts stay readable for very long goals.
_MAX_TRAJECTORY = 120


def goal_types() -> list[dict]:
    """Preset goal types for the UI."""
    return [{"id": k, **v} for k, v in GOAL_TYPES.items()]


def surplus_from_result(result: dict | None) -> tuple[float, float]:
    """Return (monthly_surplus, emergency_fund_months) from a computed result."""
    hs = (result or {}).get("health_score", {}) or {}
    surplus = max(0.0, float(hs.get("income", 0) or 0) - float(hs.get("expenses", 0) or 0))
    ef_months = float(hs.get("emergency_fund_months", 0) or 0)
    return surplus, ef_months


def _monthly_rate(annual_return: float) -> float:
    return (1 + annual_return) ** (1 / 12) - 1 if annual_return > 0 else 0.0


def _balance_after(current: float, monthly: float, months: int, annual_return: float) -> float:
    r = _monthly_rate(annual_return)
    if r == 0:
        return current + monthly * months
    return current * (1 + r) ** months + monthly * (((1 + r) ** months - 1) / r)


def _months_to_target(current: float, monthly: float, target: float, annual_return: float) -> int | None:
    """Smallest month count where the balance reaches the target."""
    if current >= target:
        return 0
    if monthly <= 0 and annual_return <= 0:
        return None
    r = _monthly_rate(annual_return)
    bal = current
    for m in range(1, _MAX_TRAJECTORY * 12 + 1):
        bal = bal * (1 + r) + monthly
        if bal >= target:
            return m
    return None  # not reachable within the horizon


def _trajectory(current: float, monthly: float, target: float, horizon: int, annual_return: float) -> list[dict]:
    horizon = max(1, min(horizon, _MAX_TRAJECTORY))
    return [
        {
            "month": i,
            "saved": round(_balance_after(current, monthly, i, annual_return), 2),
            "target": round(target, 2),
        }
        for i in range(0, horizon + 1)
    ]


def _ef_factor(emergency_fund_months: float) -> float:
    """Fragility penalty: a thin emergency fund lowers confidence."""
    if emergency_fund_months >= 3:
        return 1.0
    return round(0.55 + 0.15 * max(0.0, emergency_fund_months), 2)  # ef 0→0.55, 1→0.70, 2→0.85


def plan_goal(
    *,
    goal_type: str,
    target_amount: float,
    monthly_surplus: float = 0.0,
    current_saved: float = 0.0,
    target_months: int | None = None,
    monthly_contribution: float | None = None,
    emergency_fund_months: float = 3.0,
    annual_return: float = 0.0,
) -> dict:
    """Compute a full, deterministic plan for one goal. Returns a plain dict."""
    goal_type = goal_type if goal_type in GOAL_TYPES else "custom"
    icon = GOAL_TYPES[goal_type]["icon"]
    target = max(0.0, float(target_amount))
    current = max(0.0, float(current_saved))
    # Use the explicit contribution when provided; otherwise the whole surplus.
    contribution = monthly_contribution if monthly_contribution is not None else monthly_surplus
    contribution = max(0.0, float(contribution))
    ef_factor = _ef_factor(emergency_fund_months)

    remaining = max(0.0, target - current)
    progress_pct = round(min(100.0, (current / target * 100.0) if target > 0 else 0.0), 1)

    # Already achieved.
    if remaining <= 0:
        return {
            "goal_type": goal_type, "icon": icon, "target_amount": round(target, 2),
            "current_saved": round(current, 2), "monthly_surplus": round(monthly_surplus, 2),
            "monthly_contribution": round(contribution, 2),
            "required_monthly": 0.0, "timeline_months": target_months or 0,
            "reachable": True, "on_track": True, "risk": "Low",
            "completion_probability": 1.0, "progress_pct": 100.0, "shortfall_monthly": 0.0,
            "projected_label": "Already achieved 🎉",
            "trajectory": _trajectory(current, contribution, target, target_months or 12, annual_return),
        }

    if target_months and target_months > 0:
        # Deadline-driven.
        required_monthly = round(remaining / target_months, 2)
        coverage = (contribution / required_monthly) if required_monthly > 0 else (10.0 if contribution > 0 else 0.0)
        projected = _balance_after(current, contribution, target_months, annual_return)
        reachable = projected >= target
        base = min(1.0, coverage)
        timeline_months = target_months
        shortfall = round(max(0.0, required_monthly - contribution), 2)
        if not reachable and coverage < 1.0:
            risk = "High"
        elif coverage >= 1.25:
            risk = "Low"
        elif coverage >= 1.0:
            risk = "Medium"
        else:
            risk = "High"
        months_to_reach = _months_to_target(current, contribution, target, annual_return)
    else:
        # Open-ended: save the contribution until the target is met.
        required_monthly = round(contribution, 2)
        months_to_reach = _months_to_target(current, contribution, target, annual_return)
        reachable = months_to_reach is not None
        timeline_months = months_to_reach
        shortfall = 0.0
        if not reachable:
            base, risk = 0.0, "High"
        else:
            base = 0.9
            risk = "Low" if months_to_reach <= 36 else "Medium" if months_to_reach <= 120 else "High"

    completion_probability = 0.0 if not reachable and base == 0.0 else round(base * ef_factor, 2)
    horizon = timeline_months or target_months or 24

    return {
        "goal_type": goal_type, "icon": icon, "target_amount": round(target, 2),
        "current_saved": round(current, 2), "monthly_surplus": round(monthly_surplus, 2),
        "monthly_contribution": round(contribution, 2),
        "required_monthly": required_monthly,
        "timeline_months": timeline_months,
        "months_to_reach": months_to_reach,
        "reachable": reachable, "on_track": contribution >= required_monthly,
        "risk": risk, "completion_probability": completion_probability,
        "progress_pct": progress_pct, "shortfall_monthly": shortfall,
        "projected_label": (
            "Not reachable at the current surplus" if not reachable
            else f"~{timeline_months} months to reach" if timeline_months
            else "On track"
        ),
        "trajectory": _trajectory(current, contribution, target, horizon, annual_return),
    }
