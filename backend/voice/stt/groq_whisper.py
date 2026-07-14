"""Groq Whisper STT provider (online). Uses the OpenAI-compatible Groq audio
endpoint with verbose_json to obtain per-segment log-probs (confidence) and the
auto-detected language. Reuses the existing GROQ_API_KEY — no new secret.
"""
from __future__ import annotations

import logging
import math
import os
import time

import httpx

from ..config import VoiceConfig
from .base import STTProvider, STTResult

logger = logging.getLogger("voice.stt.groq_whisper")

_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
_TIMEOUT = 30.0


def _mime_for(suffix: str) -> str:
    s = suffix.lower()
    if "mp4" in s or "m4a" in s:
        return "audio/mp4"
    if "ogg" in s:
        return "audio/ogg"
    if "wav" in s:
        return "audio/wav"
    if "mp3" in s:
        return "audio/mpeg"
    return "audio/webm"


class GroqWhisperProvider(STTProvider):
    name = "groq_whisper"
    offline = False

    def __init__(self, config: VoiceConfig) -> None:
        self._config = config

    def _api_key(self) -> str | None:
        return os.getenv("GROQ_API_KEY")

    def is_available(self) -> bool:
        return bool(self._api_key())

    def transcribe(self, audio_bytes: bytes, suffix: str = ".webm") -> STTResult:
        key = self._api_key()
        if not key:
            return STTResult(text="", provider=self.name, error="GROQ_API_KEY not set")
        started = time.perf_counter()
        files = {"file": (f"audio{suffix}", audio_bytes, _mime_for(suffix))}
        data = {
            "model": self._config.groq_stt_model,
            "response_format": "verbose_json",
            "temperature": "0",
        }
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(
                    _ENDPOINT,
                    headers={"Authorization": f"Bearer {key}"},
                    files=files,
                    data=data,
                )
            if resp.status_code != 200:
                return STTResult(
                    text="", provider=self.name,
                    error=f"groq stt http {resp.status_code}: {resp.text[:180]}",
                )
            body = resp.json()
            text = (body.get("text") or "").strip()
            segments = body.get("segments") or []
            if segments:
                avg = sum(s.get("avg_logprob", -1.0) for s in segments) / len(segments)
                confidence = max(0.0, min(1.0, math.exp(avg)))
            else:
                confidence = 0.85 if text else 0.0
            latency = (time.perf_counter() - started) * 1000
            logger.info(
                "groq_whisper ok chars=%d conf=%.2f lang=%s %.0fms",
                len(text), confidence, body.get("language"), latency,
            )
            return STTResult(
                text=text,
                confidence=round(confidence, 3),
                language=body.get("language"),
                provider=self.name,
                latency_ms=round(latency, 1),
            )
        except httpx.HTTPError as exc:
            logger.warning("groq_whisper network error: %s", exc)
            return STTResult(text="", provider=self.name, error=f"network: {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("groq_whisper error: %s", exc)
            return STTResult(text="", provider=self.name, error=str(exc))
