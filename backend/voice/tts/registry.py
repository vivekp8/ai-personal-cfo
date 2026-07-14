"""TTS registry: builds the provider chain from config and synthesizes with
automatic failover.
"""
from __future__ import annotations

import logging

from ..config import VoiceConfig
from .base import TTSProvider, TTSResult
from .edge_tts_provider import EdgeTTSProvider
from .gtts_tts import GTTSProvider

logger = logging.getLogger("voice.tts.registry")


class TTSRegistry:
    def __init__(self, config: VoiceConfig) -> None:
        self._config = config
        self._providers: dict[str, TTSProvider] = {
            "gtts": GTTSProvider(),
            "edge_tts": EdgeTTSProvider(config.edge_voice),
        }

    def _ordered(self) -> list[TTSProvider]:
        order: list[str] = []
        for name in self._config.tts_priority:
            if name in self._providers and name not in order:
                order.append(name)
        for name in self._providers:
            if name not in order:
                order.append(name)
        return [self._providers[n] for n in order if self._providers[n].is_available()]

    def available(self) -> list[str]:
        return [p.name for p in self._ordered()]

    def synthesize(self, text: str) -> TTSResult:
        chain = self._ordered()
        if not chain:
            return TTSResult(provider="none", error="No TTS provider available. pip install gtts")
        last: TTSResult | None = None
        fallbacks = 0
        for provider in chain:
            result = provider.synthesize(text, lang=self._config.tts_lang)
            if result.ok:
                if fallbacks:
                    logger.info("TTS succeeded on %s after %d fallback(s)", provider.name, fallbacks)
                return result
            logger.info("TTS %s failed (%s), failing over", provider.name, result.error)
            last = result
            fallbacks += 1
        return last or TTSResult(provider="none", error="All TTS providers failed.")
