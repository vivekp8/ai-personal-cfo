"""Backward-compatible facade over the modular voice layer.

Historically this module held Whisper + gTTS directly. It now delegates to the
clean multi-provider ``VoiceService`` (STT/TTS registries with failover,
confidence scoring, config, logging) while keeping the EXACT public functions
the rest of the app already imports:

    transcribe(audio_bytes, suffix) -> dict
    synthesize(text)               -> (bytes | None, error)
    preload()                      -> bool
    whisper_available()            -> bool
    gtts_available()               -> bool

No caller had to change; new fields (provider/confidence/language/latency) are
added to the transcribe dict without removing the original keys.
"""
from __future__ import annotations

from .service import service


def whisper_available() -> bool:
    return len(service.stt.available()) > 0


def gtts_available() -> bool:
    return len(service.tts.available()) > 0


def preload() -> bool:
    return service.preload()


def transcribe(audio_bytes: bytes, suffix: str = ".webm") -> dict:
    """Transcribe audio bytes. Returns the original shape plus extra metadata."""
    result = service.transcribe(audio_bytes, suffix)
    available = result.provider not in ("none", "")
    return {
        # ---- original keys (backward compatible) ----
        "text": result.text,
        "available": available,
        "error": result.error,
        "bytes": len(audio_bytes),
        # ---- new metadata ----
        "provider": result.provider,
        "confidence": result.confidence,
        "language": result.language,
        "latency_ms": result.latency_ms,
        "low_confidence": bool(
            result.ok and result.confidence < service.config.stt_min_confidence
        ),
    }


def synthesize(text: str) -> tuple[bytes | None, str | None]:
    """Return (audio_bytes, error). audio_bytes is None on failure."""
    result = service.synthesize(text)
    return result.audio, result.error


def capabilities() -> dict:
    return service.capabilities()


def metrics() -> dict:
    return service.metrics.snapshot()
