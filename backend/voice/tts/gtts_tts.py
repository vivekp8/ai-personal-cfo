"""Google TTS (gTTS) provider — online, no key required."""
from __future__ import annotations

import logging
import os
import tempfile
import time

from .base import TTSProvider, TTSResult

logger = logging.getLogger("voice.tts.gtts")


class GTTSProvider(TTSProvider):
    name = "gtts"
    offline = False

    def is_available(self) -> bool:
        try:
            import gtts  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return True

    def synthesize(self, text: str, *, lang: str = "en", voice: str | None = None) -> TTSResult:
        if not text.strip():
            return TTSResult(provider=self.name, error="empty text")
        try:
            from gtts import gTTS
        except Exception:  # noqa: BLE001
            return TTSResult(provider=self.name, error="gTTS not installed. pip install gtts")
        started = time.perf_counter()
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp_path = tmp.name
            gTTS(text=text, lang=lang or "en").save(tmp_path)
            with open(tmp_path, "rb") as fh:
                data = fh.read()
            latency = (time.perf_counter() - started) * 1000
            logger.info("gtts ok bytes=%d %.0fms", len(data), latency)
            return TTSResult(audio=data, mime="audio/mpeg", provider=self.name, latency_ms=round(latency, 1))
        except Exception as exc:  # noqa: BLE001
            logger.warning("gtts error: %s", exc)
            return TTSResult(provider=self.name, error=str(exc))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
