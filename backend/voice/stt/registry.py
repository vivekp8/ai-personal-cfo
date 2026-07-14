"""STT registry: builds the provider chain from config, then transcribes with
automatic failover and confidence-based retry.
"""
from __future__ import annotations

import logging

from ..config import VoiceConfig
from .base import STTProvider, STTResult
from .groq_whisper import GroqWhisperProvider
from .whisper_local import WhisperLocalProvider

logger = logging.getLogger("voice.stt.registry")

# All known providers keyed by their config id. Add new backends here only.
_FACTORIES = {
    "groq_whisper": GroqWhisperProvider,
    "whisper_local": WhisperLocalProvider,
}


class STTRegistry:
    def __init__(self, config: VoiceConfig) -> None:
        self._config = config
        self._providers: dict[str, STTProvider] = {}
        for name, factory in _FACTORIES.items():
            try:
                self._providers[name] = factory(config)
            except Exception as exc:  # noqa: BLE001
                logger.warning("STT provider %s init failed: %s", name, exc)

    def _ordered(self, offline_only: bool = False) -> list[STTProvider]:
        order: list[str] = []
        for name in self._config.stt_priority:
            if name in self._providers and name not in order:
                order.append(name)
        for name in self._providers:  # append any not listed, as last resort
            if name not in order:
                order.append(name)
        chain = [self._providers[n] for n in order]
        if offline_only:
            chain = [p for p in chain if p.offline]
        return [p for p in chain if p.is_available()]

    def available(self) -> list[str]:
        return [p.name for p in self._ordered()]

    def transcribe(self, audio_bytes: bytes, suffix: str = ".webm", *, offline: bool = False) -> STTResult:
        """Try providers in priority order. Accept the first confident result;
        otherwise keep the best-scoring one and report low confidence."""
        chain = self._ordered(offline_only=offline)
        if not chain:
            return STTResult(
                text="", provider="none",
                error="No STT provider available. Install openai-whisper or set GROQ_API_KEY.",
            )

        min_conf = self._config.stt_min_confidence
        fallbacks = 0
        best: STTResult | None = None

        for provider in chain:
            result = provider.transcribe(audio_bytes, suffix)
            if result.ok:
                if best is None or result.confidence > best.confidence:
                    best = result
                if result.confidence >= min_conf:
                    if fallbacks:
                        logger.info("STT succeeded on %s after %d fallback(s)", provider.name, fallbacks)
                    return result
                logger.info(
                    "STT %s low confidence %.2f < %.2f%s",
                    provider.name, result.confidence, min_conf,
                    " — trying next" if self._config.enable_auto_retry else "",
                )
                if not self._config.enable_auto_retry:
                    return result
            else:
                logger.info("STT %s failed (%s), failing over", provider.name, result.error)
            fallbacks += 1

        if best is not None:
            best.error = best.error or "low_confidence"
            return best
        return STTResult(text="", provider="none", error="All STT providers failed.")

    def preload(self) -> bool:
        """Warm any offline provider that supports preloading (Whisper)."""
        local = self._providers.get("whisper_local")
        if isinstance(local, WhisperLocalProvider):
            return local.preload()
        return False
