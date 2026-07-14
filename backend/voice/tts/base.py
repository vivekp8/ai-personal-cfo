"""TTS provider interface."""
from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class TTSResult:
    audio: bytes | None = None
    mime: str = "audio/mpeg"
    provider: str = ""
    latency_ms: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.audio)


class TTSProvider(abc.ABC):
    name: str = "base"
    offline: bool = False

    @abc.abstractmethod
    def is_available(self) -> bool: ...

    @abc.abstractmethod
    def synthesize(self, text: str, *, lang: str = "en", voice: str | None = None) -> TTSResult:
        """Synthesize speech; must never raise — return TTSResult with error set."""
