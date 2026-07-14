"""Speech-to-Text providers with a common interface and automatic failover."""
from __future__ import annotations

from .base import STTProvider, STTResult
from .registry import STTRegistry

__all__ = ["STTProvider", "STTResult", "STTRegistry"]
