"""Monthly aggregation: group transactions by month and category."""
from __future__ import annotations

from collections import defaultdict


def _month_key(date: str) -> str:
    # date is ISO "YYYY-MM-DD"
    return date[:7]  # "YYYY-MM"


def aggregate_monthly(categorized: list[dict]) -> dict:
    """Produce a monthly summary.

    Returns:
        {
          "months": ["2025-01", ...],
          "by_month_category": { "2025-01": { "Food": 1234.0, ... }, ... },
          "monthly_income": { "2025-01": 85000.0, ... },
          "monthly_expenses": { "2025-01": 40000.0, ... },
          "category_totals": { "Food": 5000.0, ... },   # expenses only
        }
    """
    by_month_category: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    monthly_income: dict[str, float] = defaultdict(float)
    monthly_expenses: dict[str, float] = defaultdict(float)
    category_totals: dict[str, float] = defaultdict(float)

    from datetime import datetime
    
    start_date = None
    end_date = None

    for txn in categorized:
        month = _month_key(txn["date"])
        cat = txn["category"]
        amt = txn["amount"]
        
        # Track earliest and latest dates
        if not start_date or txn["date"] < start_date:
            start_date = txn["date"]
        if not end_date or txn["date"] > end_date:
            end_date = txn["date"]
            
        by_month_category[month][cat] += amt
        if amt > 0 or cat == "Income":
            monthly_income[month] += amt
        else:
            spend = abs(amt)
            monthly_expenses[month] += spend
            category_totals[cat] += spend

    months = sorted(by_month_category.keys())
    
    duration_days = 0
    if start_date and end_date:
        d1 = datetime.strptime(start_date, "%Y-%m-%d")
        d2 = datetime.strptime(end_date, "%Y-%m-%d")
        duration_days = (d2 - d1).days + 1

    return {
        "timeline": {
            "start_date": start_date or "",
            "end_date": end_date or "",
            "duration_days": duration_days
        },
        "months": months,
        "by_month_category": {m: dict(by_month_category[m]) for m in months},
        "monthly_income": {m: round(monthly_income[m], 2) for m in months},
        "monthly_expenses": {m: round(monthly_expenses[m], 2) for m in months},
        "category_totals": {k: round(v, 2) for k, v in category_totals.items()},
    }
