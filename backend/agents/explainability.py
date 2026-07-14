"""Phase 4 — Explainable AI.

For any dashboard figure, assemble a transparent, concise explanation card:
Why · Evidence · Confidence · Retrieved Documents · Transactions Used ·
Formula · Model · Reasoning Summary.

Everything is derived from the deterministic computed result — figures are never
invented. The reasoning summary is a short conclusion, NOT chain-of-thought.
"""
from __future__ import annotations

import logging

from llm.router import router as llm_router
from rag import retriever

logger = logging.getLogger("agents.explainability")

SUBJECTS = ["score", "savings", "forecast", "anomaly", "spending"]

_SUBJECT_TITLES = {
    "score": "Financial Health Score",
    "savings": "Savings Rate",
    "forecast": "Next-Month Expense Forecast",
    "anomaly": "Spending Anomalies",
    "spending": "Spending by Category",
}


def _inr(n) -> str:
    try:
        return f"Rs.{abs(float(n)):,.0f}"
    except (TypeError, ValueError):
        return "Rs.0"


def _narrator() -> str | None:
    try:
        avail = llm_router.available_providers()
        return avail[0] if avail else None
    except Exception:  # noqa: BLE001
        return None


def _model_used() -> str:
    narrator = _narrator()
    if narrator:
        return f"Deterministic engine (figures) + {narrator} (narration)"
    return "Deterministic engine (no LLM configured)"


def _reference_transactions(result: dict, subject: str, limit: int = 8) -> list[dict]:
    txns = result.get("transactions", []) or []
    hs = result.get("health_score", {}) or {}
    ref_month = hs.get("reference_month")

    if subject in ("score", "savings") and ref_month:
        rows = [t for t in txns if str(t.get("date", "")).startswith(ref_month)]
    elif subject == "anomaly":
        anoms = result.get("anomalies", []) or []
        keys = {(a.get("date"), round(abs(float(a.get("amount", 0))), 2)) for a in anoms}
        rows = [
            t for t in txns
            if (t.get("date"), round(abs(float(t.get("amount", 0))), 2)) in keys
        ]
        if not rows:  # fall back to the largest outflows
            rows = sorted(txns, key=lambda t: float(t.get("amount", 0)))[:limit]
    elif subject == "spending":
        rows = sorted(txns, key=lambda t: abs(float(t.get("amount", 0))), reverse=True)
    else:  # forecast
        rows = txns[-limit:]

    return rows[:limit]


def _score_breakdown(hs: dict) -> tuple[list[str], str]:
    """Reproduce the exact deductions from the health-score formula."""
    rate = float(hs.get("savings_rate", 0) or 0)
    anoms = int(hs.get("anomalies_count", 0) or 0)
    ef = float(hs.get("emergency_fund_months", 0) or 0)
    emis = int(hs.get("active_emis", 0) or 0)

    lines = ["Start at 100"]
    if rate < 0.10:
        lines.append(f"− 30  (savings rate {rate:.0%} < 10%)")
    elif rate < 0.20:
        lines.append(f"− 15  (savings rate {rate:.0%} < 20%)")
    else:
        lines.append(f"− 0   (savings rate {rate:.0%} ≥ 20%)")
    anom_pen = min(anoms * 10, 30)
    lines.append(f"− {anom_pen}  ({anoms} anomalies × 10, capped 30)")
    if ef < 3:
        lines.append(f"− 20  (emergency fund {ef:.1f} months < 3)")
    else:
        lines.append(f"− 0   (emergency fund {ef:.1f} months ≥ 3)")
    emi_pen = min(emis * 5, 15)
    lines.append(f"− {emi_pen}  ({emis} EMIs × 5, capped 15)")
    lines.append(f"= {hs.get('score', 0)}  → {hs.get('rating', 'unknown')}")
    formula = "100 − savings_penalty − min(anomalies×10, 30) − emergency_penalty − min(EMIs×5, 15)"
    return lines, formula


def build_explanation(subject: str, result: dict) -> dict:
    """Return a structured explanation card for one dashboard subject."""
    subject = (subject or "").lower().strip()
    if subject not in SUBJECTS:
        subject = "score"

    hs = result.get("health_score", {}) or {}
    summary = result.get("monthly_summary", {}) or {}
    forecast = result.get("forecast", {}) or {}
    anomalies = result.get("anomalies", []) or []

    evidence: list[str] = []
    formula = ""
    why = ""
    reasoning = ""
    confidence = 0.9

    if subject == "score":
        breakdown, formula = _score_breakdown(hs)
        evidence = breakdown
        why = (
            f"Your score is {hs.get('score', 0)} ({hs.get('rating', 'unknown')}) because of "
            f"the deductions above applied to a base of 100."
        )
        reasoning = (
            f"Savings rate {float(hs.get('savings_rate',0)):.0%}, "
            f"{hs.get('anomalies_count',0)} anomalies, "
            f"{float(hs.get('emergency_fund_months',0)):.1f}-month emergency fund and "
            f"{hs.get('active_emis',0)} EMIs together set the score."
        )
        confidence = 0.97  # exact deterministic formula

    elif subject == "savings":
        income = float(hs.get("income", 0) or 0)
        expenses = float(hs.get("expenses", 0) or 0)
        rate = float(hs.get("savings_rate", 0) or 0)
        formula = "savings_rate = (income − expenses) / income"
        evidence = [
            f"Income = {_inr(income)}",
            f"Expenses = {_inr(expenses)}",
            f"Surplus = {_inr(income - expenses)}",
            f"Savings rate = {rate:.1%}",
        ]
        why = (
            f"You save {rate:.0%} of income "
            f"({'above' if rate >= 0.20 else 'below'} the 20% benchmark)."
        )
        reasoning = (
            "A higher savings rate improves resilience; the 20% benchmark is the "
            "healthy target used across the app."
        )
        confidence = 0.95

    elif subject == "forecast":
        months = (forecast.get("history", {}) or {}).get("months", []) or []
        n = len(months)
        formula = "LinearRegression over monthly expense totals (fallback: latest value if < 2 months)"
        evidence = [
            f"Data points = {n} month(s)",
            f"Next month = {forecast.get('next_month', 'n/a')}",
            f"Forecast total = {_inr(forecast.get('total_expense_forecast', 0))}",
        ]
        for cat, val in list((forecast.get("category_forecast", {}) or {}).items())[:4]:
            evidence.append(f"{cat} ≈ {_inr(val)}")
        why = (
            f"Next month's expenses are projected at "
            f"{_inr(forecast.get('total_expense_forecast', 0))} by fitting a trend line "
            f"to {n} month(s) of totals."
        )
        reasoning = (
            "The trend line extrapolates recent monthly spend; more months of history "
            "increase reliability."
        )
        # More history → higher confidence (naive average when < 2 months).
        confidence = round(min(0.9, 0.45 + 0.09 * n), 2) if n else 0.3

    elif subject == "anomaly":
        formula = "flag if category month spend > mean + 2·std, or a single txn > 3× category median"
        evidence = [f"{len(anomalies)} anomaly(ies) detected"]
        for a in anomalies[:5]:
            evidence.append(f"{a.get('message', '')}")
        why = (
            f"{len(anomalies)} transaction(s)/categories deviated enough from your "
            f"normal pattern to be flagged."
            if anomalies else "No spending deviated enough from your pattern to be flagged."
        )
        reasoning = (
            "Anomalies mark unusual spikes so you can confirm they were intentional."
        )
        confidence = 0.85

    else:  # spending
        totals = summary.get("category_totals", {}) or {}
        spend = sorted(
            ((k, abs(v)) for k, v in totals.items() if v), key=lambda x: x[1], reverse=True
        )
        formula = "category_total = Σ(transaction amounts within each category)"
        evidence = [f"{k} = {_inr(v)}" for k, v in spend[:6]] or ["No categorised spend yet."]
        top = spend[0] if spend else None
        why = (
            f"Your largest category is {top[0]} at {_inr(top[1])}." if top
            else "No spending has been categorised yet."
        )
        reasoning = "Category totals aggregate every transaction tagged to that category."
        confidence = 0.95

    # RAG-retrieved supporting documents (best-effort; empty if RAG unavailable).
    retrieved_docs: list[str] = []
    try:
        rag = retriever.retrieve(_SUBJECT_TITLES.get(subject, subject), "demo_user")
        retrieved_docs = rag.get("sources", [])[:4]
    except Exception:  # noqa: BLE001
        retrieved_docs = []

    txns_used = _reference_transactions(result, subject)

    card = {
        "subject": subject,
        "title": _SUBJECT_TITLES.get(subject, subject.title()),
        "why": why,
        "evidence": evidence,
        "confidence": confidence,
        "retrieved_documents": retrieved_docs,
        "transactions_used": txns_used,
        "formula": formula,
        "model": _model_used(),
        "reasoning_summary": reasoning,
    }
    logger.info("explanation built subject=%s conf=%.2f txns=%d", subject, confidence, len(txns_used))
    return card
