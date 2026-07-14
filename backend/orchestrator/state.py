"""Shared CFO state used by the LangGraph pipeline (Phase 2)."""
from __future__ import annotations

from typing import TypedDict


class CFOState(TypedDict, total=False):
    raw_csv_path: str
    raw_csv_content: str
    raw_bytes: bytes
    filename: str
    user_id: str
    transactions: list[dict]
    categorized: list[dict]
    monthly_summary: dict
    anomalies: list[dict]
    forecast: dict
    health_score: dict
    savings_suggestions: list[dict]
    whatif_result: dict | None
    user_query: str
    intent: str
    final_response: str
