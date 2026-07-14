"""Deterministic financial health score.

This is the single source of truth for the score. The LLM must NEVER compute
this number, only narrate it.
"""
from __future__ import annotations


def calculate_health_score(
    income: float,
    expenses: float,
    anomalies_count: int,
    emergency_fund_months: float,
    active_emis: int,
) -> tuple[int, float]:
    """Return (score, savings_rate). Exact formula from the spec."""
    score = 100
    savings_rate = (income - expenses) / income if income > 0 else 0.0
    if savings_rate < 0.10:
        score -= 30
    elif savings_rate < 0.20:
        score -= 15
    score -= min(anomalies_count * 10, 30)
    if emergency_fund_months < 3:
        score -= 20
    score -= min(active_emis * 5, 15)
    return max(0, min(100, score)), savings_rate


def build_health_score(
    monthly_summary: dict,
    anomalies: list[dict],
    emergency_fund_months: float = 0.0,
    active_emis: int = 0,
) -> dict:
    """Compute the score using the latest full month as the reference period."""
    months = monthly_summary["months"]
    if not months:
        return {
            "score": 0,
            "savings_rate": 0.0,
            "income": 0.0,
            "expenses": 0.0,
            "anomalies_count": 0,
            "emergency_fund_months": emergency_fund_months,
            "active_emis": active_emis,
            "rating": "unknown",
        }

    latest = months[-1]
    income = monthly_summary["monthly_income"].get(latest, 0.0)
    expenses = monthly_summary["monthly_expenses"].get(latest, 0.0)

    # Estimate emergency fund from average monthly surplus if not supplied.
    if emergency_fund_months == 0.0:
        surpluses = [
            monthly_summary["monthly_income"].get(m, 0.0)
            - monthly_summary["monthly_expenses"].get(m, 0.0)
            for m in months
        ]
        total_surplus = sum(s for s in surpluses if s > 0)
        avg_expense = (
            sum(monthly_summary["monthly_expenses"].values()) / len(months)
        ) or 1.0
        emergency_fund_months = round(total_surplus / avg_expense, 2)

    anomalies_count = len(anomalies)
    score, savings_rate = calculate_health_score(
        income, expenses, anomalies_count, emergency_fund_months, active_emis
    )

    if score >= 75:
        rating = "healthy"
    elif score >= 50:
        rating = "okay"
    else:
        rating = "at risk"

    return {
        "score": score,
        "savings_rate": round(savings_rate, 4),
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "anomalies_count": anomalies_count,
        "emergency_fund_months": emergency_fund_months,
        "active_emis": active_emis,
        "reference_month": latest,
        "rating": rating,
    }
