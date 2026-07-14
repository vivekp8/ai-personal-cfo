"""STT provider interface (SOLID: depend on this abstraction, not concretes)."""
from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class STTResult:
    """Normalised transcription result shared by every STT provider."""

    text: str
    confidence: float = 0.0          # 0..1
    language: str | None = None
    provider: str = ""
    latency_ms: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text.strip())


class STTProvider(abc.ABC):
    """A single speech-to-text backend."""

    #: stable short id used in config/logs (e.g. "groq_whisper").
    name: str = "base"
    #: True for providers that work without internet.
    offline: bool = False

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is usable (deps installed / key present)."""

    @abc.abstractmethod
    def transcribe(self, audio_bytes: bytes, suffix: str = ".webm") -> STTResult:
        """Transcribe audio; must never raise — return STTResult with error set."""
