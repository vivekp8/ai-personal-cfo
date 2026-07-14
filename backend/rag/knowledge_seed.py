"""Static financial-knowledge documents for the RAG knowledge base.

Loaded from backend/rag/knowledge_docs/*.md if present; otherwise the
embedded defaults below are used (and written to disk on first run so they
are inspectable).
"""
from __future__ import annotations

import os

_DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_docs")

_DEFAULT_DOCS: list[str] = [
    "The 50/30/20 budgeting rule splits after-tax income into 50% needs, 30% wants, and 20% savings or debt repayment.",
    "Needs in the 50/30/20 rule include rent, utilities, groceries, insurance, and minimum loan payments.",
    "Wants in the 50/30/20 rule include dining out, subscriptions, travel, and shopping beyond essentials.",
    "A healthy personal savings rate is at least 20% of income; below 10% is a warning sign of overspending.",
    "An emergency fund should cover 3 to 6 months of essential expenses, kept in a liquid, easily accessible account.",
    "If your emergency fund covers less than 3 months of expenses, prioritise building it before discretionary spending.",
    "Emergency funds protect against job loss, medical bills, and urgent repairs without forcing you into high-interest debt.",
    "EMI stands for Equated Monthly Instalment: a fixed payment combining principal and interest over a loan tenure.",
    "Flat-rate interest charges interest on the full original principal for the whole tenure, so the effective rate is higher than it appears.",
    "Reducing-balance interest charges interest only on the outstanding principal, making it cheaper than flat-rate for the same nominal rate.",
    "Longer EMI tenures lower the monthly payment but increase the total interest you pay over the life of the loan.",
    "Before taking an EMI, check that the monthly instalment stays within your budget without cutting into your emergency fund.",
    "A debt-to-income ratio above 40% is considered risky; lenders and advisors prefer keeping total EMIs below 30-40% of income.",
    "Paying for a purchase in full avoids interest entirely, but only if it does not drain your emergency fund below 3 months.",
    "Subscription overload happens when small recurring charges accumulate; audit subscriptions quarterly and cancel unused ones.",
    "Two or more overlapping streaming subscriptions is a common source of waste; rotate services instead of paying for all at once.",
    "Food delivery is a frequent budget leak; cooking at home even a few extra days per week can cut food spending by 20-30%.",
    "The rule of thumb for discretionary categories: no single want should dominate your budget the way a need would.",
    "Lifestyle inflation is when spending rises with income; keeping expenses flat as income grows accelerates savings.",
    "Pay yourself first: automate a transfer to savings on payday before you have a chance to spend it.",
    "High-interest debt (credit cards, personal loans) should be repaid before investing, as the guaranteed 'return' from avoiding interest is large.",
    "A financial health score reflects savings rate, spending anomalies, emergency fund depth, and active debt obligations together.",
    "A savings rate below 10% typically lowers a financial health score significantly and signals a tight or overspent budget.",
    "Frequent spending anomalies (unusual spikes) reduce financial health because they suggest unplanned or impulsive spending.",
    "Sinking funds set aside money monthly for known irregular expenses like insurance premiums, travel, or festivals.",
    "The 24-hour rule: wait a day before any large discretionary purchase to reduce impulse buying.",
    "Track spending by category monthly; awareness alone often reduces discretionary spending.",
    "Utilities and rent are fixed needs; the main lever for improving savings is usually the discretionary wants category.",
    "Windfalls like bonuses or refunds are best split: part to emergency fund, part to debt, and a small part to enjoy.",
    "Interest on flat-rate EMIs is often quoted low but the effective annual rate can be nearly double the flat rate.",
    "A good financial goal is SMART: Specific, Measurable, Achievable, Relevant, and Time-bound.",
    "Insurance (health and term life) is part of a sound financial base and counts as a need, not a want.",
    "Round-up savings apps move spare change from transactions into savings automatically, building funds painlessly.",
    "If expenses exceed income in a month, review the largest discretionary categories first for quick cuts.",
    "A rising monthly expense trend over several months is an early warning to review the budget before savings erode.",
]


def _load_docs() -> list[str]:
    docs: list[str] = []
    if os.path.isdir(_DOCS_DIR):
        files = sorted(
            f for f in os.listdir(_DOCS_DIR) if f.endswith((".md", ".txt"))
        )
        for fname in files:
            path = os.path.join(_DOCS_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read().strip()
                if text:
                    docs.append(text)
            except Exception:  # noqa: BLE001
                continue
    if docs:
        return docs

    # Write defaults to disk for inspectability, then return them.
    try:
        os.makedirs(_DOCS_DIR, exist_ok=True)
        for i, doc in enumerate(_DEFAULT_DOCS):
            with open(os.path.join(_DOCS_DIR, f"kb_{i:02d}.md"), "w", encoding="utf-8") as fh:
                fh.write(doc + "\n")
    except Exception:  # noqa: BLE001
        pass
    return _DEFAULT_DOCS


KNOWLEDGE_DOCS: list[str] = _load_docs()
