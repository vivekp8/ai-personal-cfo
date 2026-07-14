"""Phase 3 — Digital Financial Twin.

A deterministic simulation engine that projects a user's current financial
state into the future. Every number is computed explicitly (no LLM, no random
noise) so results are reproducible and explainable:

  current state → salary growth → expense growth → inflation →
  investment growth → emergency fund → retirement estimate → goal timelines

Supports multiple named scenarios; the API layer handles save/compare.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# Safe withdrawal rate used for the retirement sustainability estimate.
SAFE_WITHDRAWAL_RATE = 0.04


class Goal(BaseModel):
    name: str
    target_amount: float = Field(gt=0)


class ScenarioInput(BaseModel):
    """All assumptions for one projection. Rates are annual decimals (0.08 = 8%)."""

    name: str = "Base scenario"
    years: int = Field(default=20, ge=1, le=60)

    monthly_income: float = Field(ge=0)
    monthly_expenses: float = Field(ge=0)
    current_savings: float = Field(default=0.0, ge=0)

    salary_growth: float = Field(default=0.08, ge=-0.5, le=1.0)
    expense_growth: float = Field(default=0.06, ge=-0.5, le=1.0)
    inflation: float = Field(default=0.05, ge=0.0, le=0.5)
    investment_return: float = Field(default=0.10, ge=-0.5, le=1.0)

    current_age: Optional[int] = Field(default=None, ge=0, le=100)
    retirement_age: Optional[int] = Field(default=None, ge=1, le=100)

    goals: list[Goal] = Field(default_factory=list)


class YearProjection(BaseModel):
    year: int
    age: Optional[int] = None
    annual_income: float
    annual_expenses: float
    annual_savings: float
    invested: float           # cumulative portfolio value (nominal)
    net_worth: float          # nominal
    real_net_worth: float     # inflation-adjusted to today's money
    emergency_fund_months: float


class GoalTimeline(BaseModel):
    name: str
    target_amount: float
    reached: bool
    year_reached: Optional[int] = None
    years_to_reach: Optional[int] = None


class RetirementEstimate(BaseModel):
    applicable: bool
    retirement_age: Optional[int] = None
    years_to_retirement: Optional[int] = None
    projected_corpus: Optional[float] = None
    sustainable_annual_income: Optional[float] = None
    sustainable_monthly_income: Optional[float] = None
    real_sustainable_monthly_income: Optional[float] = None


class TwinResult(BaseModel):
    scenario: ScenarioInput
    projection: list[YearProjection]
    final_net_worth: float
    final_real_net_worth: float
    total_contributed: float
    total_growth: float
    retirement: RetirementEstimate
    goals: list[GoalTimeline]


def _compound_year(corpus: float, annual_contribution: float, annual_return: float) -> float:
    """Grow a portfolio one year with monthly contributions (end-of-month).

    The corpus is floored at zero each month: an investment portfolio cannot go
    negative. If contributions are negative (expenses exceed income) the balance
    draws down to zero and stays there rather than compounding into fantasy debt.
    """
    monthly_rate = (1 + annual_return) ** (1 / 12) - 1
    monthly_contribution = annual_contribution / 12.0
    value = corpus
    for _ in range(12):
        value = max(0.0, value * (1 + monthly_rate) + monthly_contribution)
    return value


def simulate(params: ScenarioInput) -> TwinResult:
    """Run the full projection and return a structured, explainable result."""
    monthly_income = float(params.monthly_income)
    monthly_expenses = float(params.monthly_expenses)
    corpus = float(params.current_savings)

    projection: list[YearProjection] = []
    total_contributed = 0.0

    for y in range(1, params.years + 1):
        # Growth applies at the start of each year after year 1.
        if y > 1:
            monthly_income *= 1 + params.salary_growth
            monthly_expenses *= 1 + params.expense_growth

        annual_income = monthly_income * 12
        annual_expenses = monthly_expenses * 12
        annual_savings = annual_income - annual_expenses
        total_contributed += annual_savings

        corpus = _compound_year(corpus, annual_savings, params.investment_return)
        real_factor = (1 + params.inflation) ** y
        emergency_months = (corpus / monthly_expenses) if monthly_expenses > 0 else 0.0

        projection.append(
            YearProjection(
                year=y,
                age=(params.current_age + y) if params.current_age is not None else None,
                annual_income=round(annual_income, 2),
                annual_expenses=round(annual_expenses, 2),
                annual_savings=round(annual_savings, 2),
                invested=round(corpus, 2),
                net_worth=round(corpus, 2),
                real_net_worth=round(corpus / real_factor, 2),
                emergency_fund_months=round(emergency_months, 1),
            )
        )

    final_net_worth = projection[-1].net_worth if projection else corpus
    final_real = projection[-1].real_net_worth if projection else corpus

    retirement = _retirement(params, projection)
    goals = _goals(params, projection)

    return TwinResult(
        scenario=params,
        projection=projection,
        final_net_worth=round(final_net_worth, 2),
        final_real_net_worth=round(final_real, 2),
        total_contributed=round(total_contributed, 2),
        total_growth=round(final_net_worth - float(params.current_savings) - total_contributed, 2),
        retirement=retirement,
        goals=goals,
    )


def _retirement(params: ScenarioInput, projection: list[YearProjection]) -> RetirementEstimate:
    if params.current_age is None or params.retirement_age is None:
        return RetirementEstimate(applicable=False)
    years_to = params.retirement_age - params.current_age
    if years_to <= 0 or not projection:
        return RetirementEstimate(applicable=False)

    # Use the projected corpus at (or nearest to) the retirement year.
    idx = min(years_to, len(projection)) - 1
    corpus = projection[idx].net_worth
    sustainable_annual = corpus * SAFE_WITHDRAWAL_RATE
    real_factor = (1 + params.inflation) ** (idx + 1)
    return RetirementEstimate(
        applicable=True,
        retirement_age=params.retirement_age,
        years_to_retirement=years_to,
        projected_corpus=round(corpus, 2),
        sustainable_annual_income=round(sustainable_annual, 2),
        sustainable_monthly_income=round(sustainable_annual / 12, 2),
        real_sustainable_monthly_income=round(sustainable_annual / 12 / real_factor, 2),
    )


def _goals(params: ScenarioInput, projection: list[YearProjection]) -> list[GoalTimeline]:
    out: list[GoalTimeline] = []
    for g in params.goals:
        reached_year = None
        for p in projection:
            if p.net_worth >= g.target_amount:
                reached_year = p.year
                break
        out.append(
            GoalTimeline(
                name=g.name,
                target_amount=g.target_amount,
                reached=reached_year is not None,
                year_reached=reached_year,
                years_to_reach=reached_year,
            )
        )
    return out


def defaults_from_result(result: dict) -> dict:
    """Sensible scenario defaults derived from the user's computed data."""
    hs = result.get("health_score", {}) or {}
    return {
        "monthly_income": float(hs.get("income", 0) or 0),
        "monthly_expenses": float(hs.get("expenses", 0) or 0),
        "current_savings": 0.0,
    }
