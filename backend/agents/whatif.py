"""What-If purchase simulator (Phase 5).

Deterministic math only. Compares paying in full vs EMI, running both
scenarios through the same health-score function for comparable scores.
"""
from __future__ import annotations

from agents.health_score import calculate_health_score

FLAT_INTEREST_RATE = 0.11  # ~11% flat interest for EMI realism


def simulate_purchase(
    purchase_amount: float,
    monthly_summary: dict,
    health_score: dict,
    tenure_months: int = 12,
    current_savings: float | None = None,
) -> dict:
    months = monthly_summary["months"]
    num_months = max(1, len(months))

    monthly_income = health_score.get("income", 0.0)
    monthly_expenses = health_score.get("expenses", 0.0) or 1.0

    # Estimate current savings from cumulative surplus if not provided.
    if current_savings is None:
        total_income = sum(monthly_summary["monthly_income"].values())
        total_expenses = sum(monthly_summary["monthly_expenses"].values())
        current_savings = max(0.0, total_income - total_expenses)

    anomalies_count = health_score.get("anomalies_count", 0)
    active_emis = health_score.get("active_emis", 0)

    # --- Scenario A: Pay in full ---
    new_savings_full = current_savings - purchase_amount
    ef_months_full = new_savings_full / monthly_expenses
    score_full, sr_full = calculate_health_score(
        monthly_income,
        monthly_expenses,
        anomalies_count,
        ef_months_full,
        active_emis,
    )

    # --- Scenario B: EMI ---
    total_with_interest = purchase_amount * (1 + FLAT_INTEREST_RATE * (tenure_months / 12))
    emi_monthly = total_with_interest / tenure_months
    expenses_with_emi = monthly_expenses + emi_monthly
    # Savings untouched at purchase time, but emergency fund measured against
    # the higher ongoing monthly outflow.
    ef_months_emi = current_savings / expenses_with_emi
    score_emi, sr_emi = calculate_health_score(
        monthly_income,
        expenses_with_emi,
        anomalies_count,
        ef_months_emi,
        active_emis + 1,
    )

    return {
        "purchase_amount": round(purchase_amount, 2),
        "tenure_months": tenure_months,
        "current_savings": round(current_savings, 2),
        "monthly_expenses": round(monthly_expenses, 2),
        "pay_full": {
            "label": "Pay in Full",
            "new_savings": round(new_savings_full, 2),
            "emergency_fund_months": round(ef_months_full, 2),
            "monthly_outflow": round(monthly_expenses, 2),
            "savings_rate": round(sr_full, 4),
            "health_score": score_full,
            "affordable": new_savings_full >= 0,
        },
        "emi": {
            "label": "EMI",
            "emi_monthly": round(emi_monthly, 2),
            "total_paid": round(total_with_interest, 2),
            "interest_paid": round(total_with_interest - purchase_amount, 2),
            "emergency_fund_months": round(ef_months_emi, 2),
            "monthly_outflow": round(expenses_with_emi, 2),
            "savings_rate": round(sr_emi, 4),
            "health_score": score_emi,
        },
        "recommendation": "pay_full" if score_full >= score_emi else "emi",
    }
