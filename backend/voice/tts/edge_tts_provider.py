"""Edge TTS provider — high-quality neural voices, online, no key required.

Optional dependency: `pip install edge-tts`. If not installed the provider
reports unavailable and the registry falls back to another provider.
"""
from __future__ import annotations

import asyncio
import logging
import time

from .base import TTSProvider, TTSResult

logger = logging.getLogger("voice.tts.edge")


class EdgeTTSProvider(TTSProvider):
    name = "edge_tts"
    offline = False

    def __init__(self, voice: str = "en-US-AriaNeural") -> None:
        self._voice = voice

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return True

    async def _run(self, text: str, voice: str) -> bytes:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice)
        chunks = bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                chunks.extend(chunk["data"])
        return bytes(chunks)

    def synthesize(self, text: str, *, lang: str = "en", voice: str | None = None) -> TTSResult:
        if not text.strip():
            return TTSResult(provider=self.name, error="empty text")
        if not self.is_available():
            return TTSResult(provider=self.name, error="edge-tts not installed. pip install edge-tts")
        started = time.perf_counter()
        try:
            data = asyncio.run(self._run(text, voice or self._voice))
            if not data:
                return TTSResult(provider=self.name, error="edge-tts produced no audio")
            latency = (time.perf_counter() - started) * 1000
            logger.info("edge_tts ok bytes=%d %.0fms", len(data), latency)
            return TTSResult(audio=data, mime="audio/mpeg", provider=self.name, latency_ms=round(latency, 1))
        except RuntimeError as exc:
            # asyncio.run fails if a loop is already running in this thread.
            logger.warning("edge_tts loop error: %s", exc)
            return TTSResult(provider=self.name, error=f"event loop: {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("edge_tts error: %s", exc)
            return TTSResult(provider=self.name, error=str(exc))
