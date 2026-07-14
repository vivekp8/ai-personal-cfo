"""Voice service orchestrator.

The single entry point the API depends on. Wires the STT and TTS registries,
applies config, records observability metrics, and never raises — every failure
is returned as structured data so the app degrades gracefully.
"""
from __future__ import annotations

import logging
import threading

from .config import VoiceConfig, load_config
from .stt import STTRegistry, STTResult
from .tts import TTSRegistry, TTSResult

logger = logging.getLogger("voice.service")


class _Metrics:
    """Lightweight in-process observability counters (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.stt_calls = 0
        self.tts_calls = 0
        self.stt_fallbacks = 0
        self.tts_fallbacks = 0
        self.stt_latency_ms = 0.0
        self.tts_latency_ms = 0.0
        self.low_confidence = 0
        self.errors = 0
        self.provider_usage: dict[str, int] = {}

    def record_stt(self, result: STTResult, min_conf: float) -> None:
        with self._lock:
            self.stt_calls += 1
            self.stt_latency_ms += result.latency_ms
            self.provider_usage[result.provider] = self.provider_usage.get(result.provider, 0) + 1
            if result.error:
                self.errors += 1
            if result.confidence < min_conf:
                self.low_confidence += 1

    def record_tts(self, result: TTSResult) -> None:
        with self._lock:
            self.tts_calls += 1
            self.tts_latency_ms += result.latency_ms
            self.provider_usage[result.provider] = self.provider_usage.get(result.provider, 0) + 1
            if result.error:
                self.errors += 1

    def snapshot(self) -> dict:
        with self._lock:
            avg_stt = self.stt_latency_ms / self.stt_calls if self.stt_calls else 0.0
            avg_tts = self.tts_latency_ms / self.tts_calls if self.tts_calls else 0.0
            return {
                "stt_calls": self.stt_calls,
                "tts_calls": self.tts_calls,
                "avg_stt_latency_ms": round(avg_stt, 1),
                "avg_tts_latency_ms": round(avg_tts, 1),
                "low_confidence_count": self.low_confidence,
                "errors": self.errors,
                "provider_usage": dict(self.provider_usage),
            }


class VoiceService:
    def __init__(self, config: VoiceConfig | None = None) -> None:
        self.config = config or load_config()
        self.stt = STTRegistry(self.config)
        self.tts = TTSRegistry(self.config)
        self.metrics = _Metrics()

    # ---- capabilities ---------------------------------------------------- #
    def capabilities(self) -> dict:
        return {
            "stt_providers": self.stt.available(),
            "tts_providers": self.tts.available(),
            "config": self.config.snapshot(),
        }

    def preload(self) -> bool:
        return self.stt.preload()

    # ---- STT ------------------------------------------------------------- #
    def transcribe(self, audio_bytes: bytes, suffix: str = ".webm", *, offline: bool = False) -> STTResult:
        result = self.stt.transcribe(audio_bytes, suffix, offline=offline)
        self.metrics.record_stt(result, self.config.stt_min_confidence)
        low = result.ok and result.confidence < self.config.stt_min_confidence
        logger.info(
            "voice.transcribe provider=%s ok=%s conf=%.2f low=%s err=%s",
            result.provider, result.ok, result.confidence, low, result.error,
        )
        return result

    # ---- TTS ------------------------------------------------------------- #
    def synthesize(self, text: str) -> TTSResult:
        result = self.tts.synthesize(text)
        self.metrics.record_tts(result)
        logger.info(
            "voice.synthesize provider=%s ok=%s bytes=%s err=%s",
            result.provider, result.ok, len(result.audio) if result.audio else 0, result.error,
        )
        return result


# App-wide singleton.
service = VoiceService()
