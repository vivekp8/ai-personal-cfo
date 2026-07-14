"""Rule-based savings suggestions."""
from __future__ import annotations

from collections import Counter

# Subscription-like merchants (entertainment recurring)
_SUBSCRIPTION_KEYWORDS = ["netflix", "prime", "hotstar", "spotify", "youtube"]


def suggest_savings(categorized: list[dict], monthly_summary: dict) -> list[dict]:
    suggestions: list[dict] = []
    category_totals = monthly_summary["category_totals"]
    total_expenses = sum(category_totals.values()) or 1.0
    num_months = max(1, len(monthly_summary["months"]))

    # Rule: Food > 15% of expenses
    food = category_totals.get("Food", 0.0)
    food_pct = food / total_expenses
    if food_pct > 0.15:
        monthly_food = food / num_months
        potential = round(monthly_food * 0.30, 0)
        suggestions.append(
            {
                "category": "Food",
                "title": "Cut back on food delivery",
                "detail": (
                    f"Food is {food_pct:.0%} of your spending "
                    f"(Rs.{monthly_food:,.0f}/month). Reducing delivery orders by "
                    f"~30% could save about Rs.{potential:,.0f}/month."
                ),
                "monthly_savings": potential,
            }
        )

    # Rule: 2+ entertainment subscriptions
    sub_names = Counter()
    for txn in categorized:
        desc = txn["description"].lower()
        for kw in _SUBSCRIPTION_KEYWORDS:
            if kw in desc:
                sub_names[kw] += 1
    active_subs = list(sub_names.keys())
    if len(active_subs) >= 2:
        suggestions.append(
            {
                "category": "Entertainment",
                "title": "Consolidate subscriptions",
                "detail": (
                    f"You have {len(active_subs)} active subscriptions "
                    f"({', '.join(s.title() for s in active_subs)}). "
                    "Cancelling the least-used one could save a few hundred rupees "
                    "each month."
                ),
                "monthly_savings": 300,
            }
        )

    # Rule: Shopping > 20% of expenses
    shopping = category_totals.get("Shopping", 0.0)
    shopping_pct = shopping / total_expenses
    if shopping_pct > 0.20:
        monthly_shopping = shopping / num_months
        potential = round(monthly_shopping * 0.25, 0)
        suggestions.append(
            {
                "category": "Shopping",
                "title": "Trim discretionary shopping",
                "detail": (
                    f"Shopping is {shopping_pct:.0%} of your spending. Setting a "
                    f"monthly cap could save around Rs.{potential:,.0f}/month."
                ),
                "monthly_savings": potential,
            }
        )

    # Rule: Travel > 15%
    travel = category_totals.get("Travel", 0.0)
    if travel / total_expenses > 0.15:
        monthly_travel = travel / num_months
        potential = round(monthly_travel * 0.20, 0)
        suggestions.append(
            {
                "category": "Travel",
                "title": "Optimise travel spend",
                "detail": (
                    "Travel is a notable share of your spending. Pooling rides or "
                    f"using passes could save about Rs.{potential:,.0f}/month."
                ),
                "monthly_savings": potential,
            }
        )

    if not suggestions:
        suggestions.append(
            {
                "category": "General",
                "title": "You're on track",
                "detail": "No single category is dominating your spending. Keep it up.",
                "monthly_savings": 0,
            }
        )

    return suggestions
