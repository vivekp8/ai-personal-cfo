"""Text-to-Speech providers with a common interface and automatic failover."""
from __future__ import annotations

from .base import TTSProvider, TTSResult
from .registry import TTSRegistry

__all__ = ["TTSProvider", "TTSResult", "TTSRegistry"]
