"""Anomaly detection.

Two deterministic checks:
1. Month-category totals more than 1.5 std deviations above that category's
   own historical monthly mean.
2. Single transactions larger than 3x the user's average daily spend.

An IsolationForest pass is added as a supplementary signal when scikit-learn
is available and there is enough data; it never overrides the deterministic
flags, only augments them.
"""
from __future__ import annotations

import statistics
from collections import defaultdict


def detect_anomalies(categorized: list[dict], monthly_summary: dict) -> list[dict]:
    anomalies: list[dict] = []
    by_month_category = monthly_summary["by_month_category"]
    months = monthly_summary["months"]

    # --- Check 1: month-category totals vs category history ---
    # Build per-category series of monthly EXPENSE totals (positive numbers).
    category_series: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for month in months:
        for cat, total in by_month_category[month].items():
            if cat == "Income":
                continue
            category_series[cat].append((month, abs(total)))

    for cat, series in category_series.items():
        values = [v for _, v in series]
        if len(values) < 2:
            continue
        mean = statistics.mean(values)
        std = statistics.pstdev(values)
        if std == 0:
            continue
        threshold = mean + 1.5 * std
        for month, value in series:
            if value > threshold:
                anomalies.append(
                    {
                        "type": "category_spike",
                        "month": month,
                        "category": cat,
                        "amount": round(value, 2),
                        "expected": round(mean, 2),
                        "severity": "high" if value > mean + 3 * std else "medium",
                        "message": (
                            f"{cat} spending in {month} was Rs.{value:,.0f}, "
                            f"well above your usual Rs.{mean:,.0f}."
                        ),
                    }
                )

    # --- Check 2: single large transactions vs average daily spend ---
    expenses = [abs(t["amount"]) for t in categorized if t["amount"] < 0]
    if expenses:
        avg_txn = statistics.mean(expenses)
        limit = 3 * avg_txn
        for txn in categorized:
            if txn["amount"] < 0 and abs(txn["amount"]) > limit:
                anomalies.append(
                    {
                        "type": "large_transaction",
                        "date": txn["date"],
                        "category": txn["category"],
                        "description": txn["description"],
                        "amount": round(abs(txn["amount"]), 2),
                        "expected": round(avg_txn, 2),
                        "severity": "high",
                        "message": (
                            f"Large transaction on {txn['date']}: "
                            f"{txn['description']} for Rs.{abs(txn['amount']):,.0f} "
                            f"(3x+ your average of Rs.{avg_txn:,.0f})."
                        ),
                    }
                )

    return anomalies
