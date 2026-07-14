"""The specialist panel. Each heuristic is grounded in computed numbers so an
opinion is always available even without an LLM. The LLM (when configured)
enriches the phrasing; it never invents figures.
"""
from __future__ import annotations

from .base import SpecialistAgent

_DISCRETIONARY = {"Food", "Shopping", "Entertainment", "Travel", "Dining", "Subscriptions"}


def _hs(data: dict) -> dict:
    return data.get("health_score", {}) or {}


def _inr(n: float) -> str:
    return f"Rs.{abs(float(n or 0)):,.0f}"


def _surplus(data: dict) -> float:
    hs = _hs(data)
    return float(hs.get("income", 0) or 0) - float(hs.get("expenses", 0) or 0)


def _top_categories(data: dict, n: int = 3) -> list[tuple[str, float]]:
    totals = (data.get("monthly_summary", {}) or {}).get("category_totals", {}) or {}
    spend = {k: abs(v) for k, v in totals.items() if v and v < 0} or {
        k: abs(v) for k, v in totals.items() if v
    }
    return sorted(spend.items(), key=lambda x: x[1], reverse=True)[:n]


# --------------------------------------------------------------------------- #
# Heuristics (stance, summary, key_points, confidence)
# --------------------------------------------------------------------------- #
def _risk(data: dict):
    hs = _hs(data)
    ef = float(hs.get("emergency_fund_months", 0) or 0)
    emis = int(hs.get("active_emis", 0) or 0)
    anoms = int(hs.get("anomalies_count", 0) or 0)
    rate = float(hs.get("savings_rate", 0) or 0)
    flags = 0
    points = []
    if ef < 3:
        flags += 2
        points.append(f"Emergency fund only {ef:.1f} months (target 3-6).")
    else:
        points.append(f"Emergency fund {ef:.1f} months — adequate.")
    if emis > 0:
        flags += emis
        points.append(f"{emis} active EMI(s) add fixed obligations.")
    if anoms >= 2:
        flags += 1
        points.append(f"{anoms} spending anomalies detected.")
    if rate < 0.1:
        flags += 1
        points.append(f"Low savings rate ({rate:.0%}) reduces buffer.")
    stance = "High risk exposure" if flags >= 3 else "Moderate risk" if flags >= 1 else "Low risk"
    summary = (
        f"Overall financial risk looks {stance.lower()} with {ef:.1f} months of "
        f"emergency cover and {emis} active EMI(s)."
    )
    conf = 0.85 if hs else 0.4
    return stance, summary, points, conf


def _savings(data: dict):
    hs = _hs(data)
    rate = float(hs.get("savings_rate", 0) or 0)
    target = 0.20
    gap = max(0.0, target - rate)
    points = [f"Current savings rate {rate:.0%} vs 20% target."]
    sugg = data.get("savings_suggestions", []) or []
    if sugg:
        top = sugg[0]
        points.append(f"Quick win: {top.get('title')} (~{_inr(top.get('monthly_savings',0))}/mo).")
    if rate >= target:
        stance = "Savings on track"
        summary = f"Savings rate of {rate:.0%} meets the 20% benchmark; keep automating transfers."
    else:
        stance = "Boost savings rate"
        summary = (
            f"Savings rate {rate:.0%} is {gap:.0%} below the 20% target; "
            f"redirect discretionary spend to close the gap."
        )
    return stance, summary, points, 0.8 if hs else 0.4


def _investment(data: dict):
    hs = _hs(data)
    ef = float(hs.get("emergency_fund_months", 0) or 0)
    rate = float(hs.get("savings_rate", 0) or 0)
    surplus = _surplus(data)
    points = [f"Monthly surplus ~{_inr(surplus)}.", f"Emergency fund {ef:.1f} months."]
    if ef >= 3 and rate >= 0.15 and surplus > 0:
        stance = "Ready to invest surplus"
        summary = (
            f"With {ef:.1f} months of reserves and a {rate:.0%} savings rate, the "
            f"~{_inr(surplus)} monthly surplus can be systematically invested."
        )
        conf = 0.75
    else:
        stance = "Build safety net first"
        summary = (
            "Prioritise the emergency fund and a stable savings rate before "
            "committing surplus to market investments."
        )
        conf = 0.7
    return stance, summary, points, conf if hs else 0.4


def _lifestyle(data: dict):
    tops = _top_categories(data, 3)
    disc = [(c, v) for c, v in tops if c in _DISCRETIONARY]
    points = [f"{c}: {_inr(v)}" for c, v in tops]
    if disc:
        c, v = disc[0]
        stance = "Trim discretionary spend"
        summary = f"Discretionary category '{c}' is a top outflow at {_inr(v)}; small cuts here compound."
        conf = 0.7
    else:
        stance = "Lifestyle balanced"
        summary = "Top categories are largely essential; discretionary spend looks controlled."
        conf = 0.6
    return stance, summary, points, conf


def _budget(data: dict):
    hs = _hs(data)
    income = float(hs.get("income", 0) or 0)
    expenses = float(hs.get("expenses", 0) or 0)
    ratio = (expenses / income) if income else 1.0
    points = [f"Expenses are {ratio:.0%} of income."]
    if ratio <= 0.8:
        stance = "Budget healthy"
        summary = f"Spending at {ratio:.0%} of income leaves room for the 20% savings goal."
        conf = 0.8
    else:
        stance = "Rebalance budget"
        summary = f"Spending consumes {ratio:.0%} of income — tighten needs/wants to protect savings."
        conf = 0.78
    return stance, summary, points, conf if income else 0.4


def _tax(data: dict):
    hs = _hs(data)
    income = float(hs.get("income", 0) or 0)
    annual = income * 12
    points = [f"Estimated annual income ~{_inr(annual)}."]
    if annual >= 500000:
        stance = "Explore tax-saving options"
        summary = (
            f"With ~{_inr(annual)} annual income, structured deductions (e.g. retirement "
            f"contributions, insurance) may reduce taxable income. General guidance, not tax advice."
        )
        conf = 0.55
    else:
        stance = "Limited tax action"
        summary = "At current income, aggressive tax planning has limited benefit; revisit as income grows."
        conf = 0.5
    points.append("Consult a qualified tax professional before acting.")
    return stance, summary, points, conf


def _planner(data: dict):
    hs = _hs(data)
    ef = float(hs.get("emergency_fund_months", 0) or 0)
    rate = float(hs.get("savings_rate", 0) or 0)
    emis = int(hs.get("active_emis", 0) or 0)
    if ef < 3:
        stance = "Prioritise emergency fund"
        summary = f"The near-term plan should build the emergency fund from {ef:.1f} to 3+ months before other goals."
    elif emis > 0 and rate < 0.15:
        stance = "Focus on debt reduction"
        summary = "With active EMIs and a modest savings rate, accelerating debt payoff improves resilience."
    else:
        stance = "Grow long-term investments"
        summary = "Foundations look stable; shift focus to consistent long-term investing toward goals."
    points = [
        f"Emergency fund {ef:.1f} months",
        f"Savings rate {rate:.0%}",
        f"{emis} active EMI(s)",
    ]
    return stance, summary, points, 0.8 if hs else 0.4


PANEL: list[SpecialistAgent] = [
    SpecialistAgent("Risk Agent", "Risk Analyst", "🛡️",
                    "financial risk: emergency fund depth, debt load, income stability, spending anomalies", _risk),
    SpecialistAgent("Savings Agent", "Savings Strategist", "💰",
                    "the savings rate and how to increase it toward the 20% benchmark", _savings),
    SpecialistAgent("Investment Agent", "Investment Advisor", "📈",
                    "whether and how surplus should be invested, given reserves and risk capacity", _investment),
    SpecialistAgent("Lifestyle Agent", "Lifestyle Coach", "🎯",
                    "discretionary spending and lifestyle habits", _lifestyle),
    SpecialistAgent("Budget Agent", "Budget Planner", "📊",
                    "budget balance and the 50/30/20 needs/wants/savings split", _budget),
    SpecialistAgent("Tax Agent", "Tax Specialist", "🧾",
                    "tax efficiency and deduction opportunities (general guidance only)", _tax),
    SpecialistAgent("Financial Planner", "Certified Planner", "🧭",
                    "the holistic near-to-mid-term plan and goal sequencing", _planner),
]
