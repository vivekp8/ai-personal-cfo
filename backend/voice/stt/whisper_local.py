"""Local Whisper STT provider (offline-capable). Confidence is derived from the
segment average log-probabilities that Whisper exposes.
"""
from __future__ import annotations

import logging
import math
import os
import tempfile
import time

from ..config import VoiceConfig
from .base import STTProvider, STTResult

logger = logging.getLogger("voice.stt.whisper_local")

_INITIAL_PROMPT = (
    "This is a question for a personal finance assistant about spending, budget, "
    "savings, savings rate, expenses, income, financial health score, forecast, "
    "anomalies, EMI, emergency fund, and categories like food, rent, shopping, "
    "travel, utilities, and entertainment."
)

_model = None
_load_failed = False


def _logprob_to_confidence(avg_logprob: float) -> float:
    """Map Whisper's average log-prob (~ -1.0..0) to a 0..1 confidence."""
    try:
        return max(0.0, min(1.0, math.exp(avg_logprob)))
    except OverflowError:
        return 0.0


class WhisperLocalProvider(STTProvider):
    name = "whisper_local"
    offline = True

    def __init__(self, config: VoiceConfig) -> None:
        self._config = config

    def _get_model(self):
        global _model, _load_failed
        if _model is not None or _load_failed:
            return _model
        try:
            import whisper

            _model = whisper.load_model(self._config.whisper_model)
            logger.info("whisper model loaded: %s", self._config.whisper_model)
        except Exception as exc:  # noqa: BLE001
            _load_failed = True
            logger.warning("whisper load failed: %s", exc)
        return _model

    def is_available(self) -> bool:
        try:
            import whisper  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return not _load_failed

    def preload(self) -> bool:
        return self._get_model() is not None

    def transcribe(self, audio_bytes: bytes, suffix: str = ".webm") -> STTResult:
        started = time.perf_counter()
        model = self._get_model()
        if model is None:
            return STTResult(
                text="", provider=self.name,
                error="Whisper not installed. Run: pip install openai-whisper",
            )
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            lang = self._config.whisper_lang or None
            result = model.transcribe(
                tmp_path,
                fp16=False,
                language=lang,
                task="transcribe",
                temperature=0.0,
                beam_size=5,
                best_of=5,
                condition_on_previous_text=False,
                initial_prompt=_INITIAL_PROMPT,
                no_speech_threshold=0.6,
                logprob_threshold=-1.0,
            )
            text = (result.get("text") or "").strip()
            segments = result.get("segments") or []
            if segments:
                avg = sum(s.get("avg_logprob", -1.0) for s in segments) / len(segments)
                confidence = _logprob_to_confidence(avg)
            else:
                confidence = 0.0 if not text else 0.5
            latency = (time.perf_counter() - started) * 1000
            logger.info(
                "whisper_local ok chars=%d conf=%.2f lang=%s %.0fms",
                len(text), confidence, result.get("language"), latency,
            )
            return STTResult(
                text=text,
                confidence=round(confidence, 3),
                language=result.get("language") or lang,
                provider=self.name,
                latency_ms=round(latency, 1),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("whisper_local error: %s", exc)
            return STTResult(text="", provider=self.name, error=str(exc))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
