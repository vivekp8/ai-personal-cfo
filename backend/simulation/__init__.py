"""Phase 3 — Digital Financial Twin.

A deterministic, year-by-year projection engine plus scenario persistence.
"""
from __future__ import annotations

from .engine import DEFAULT_ASSUMPTIONS, derive_current_state, simulate

__all__ = ["simulate", "derive_current_state", "DEFAULT_ASSUMPTIONS"]
