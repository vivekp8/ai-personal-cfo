"""Voice subsystem configuration — the single source of truth, from .env.

Every voice feature toggle and provider preference is read here so the rest of
the package never touches os.environ directly (SOLID: single responsibility).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _flag(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class VoiceConfig:
    # Provider priority (first available wins; failover proceeds down the list).
    # Only implemented+available providers are actually used.
    stt_priority: list[str] = field(
        default_factory=lambda: _csv("STT_PROVIDER", ["groq_whisper", "whisper_local"])
    )
    tts_priority: list[str] = field(
        default_factory=lambda: _csv("TTS_PROVIDER", ["gtts", "edge_tts"])
    )

    # Feature flags.
    enable_streaming: bool = field(default_factory=lambda: _flag("ENABLE_STREAMING", True))
    enable_memory: bool = field(default_factory=lambda: _flag("ENABLE_MEMORY", True))
    enable_rag: bool = field(default_factory=lambda: _flag("ENABLE_RAG", True))
    enable_offline_mode: bool = field(default_factory=lambda: _flag("ENABLE_OFFLINE_MODE", True))
    enable_auto_retry: bool = field(default_factory=lambda: _flag("VOICE_AUTO_RETRY", True))

    # STT tuning.
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "small"))
    whisper_lang: str = field(default_factory=lambda: os.getenv("WHISPER_LANG", "en"))
    stt_min_confidence: float = field(default_factory=lambda: _float("VOICE_STT_MIN_CONFIDENCE", 0.75))
    groq_stt_model: str = field(
        default_factory=lambda: os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
    )

    # TTS tuning.
    tts_lang: str = field(default_factory=lambda: os.getenv("VOICE_TTS_LANG", "en"))
    edge_voice: str = field(default_factory=lambda: os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural"))

    def snapshot(self) -> dict:
        """Serialisable view for the /voice/config endpoint and the UI."""
        return {
            "stt_priority": self.stt_priority,
            "tts_priority": self.tts_priority,
            "enable_streaming": self.enable_streaming,
            "enable_memory": self.enable_memory,
            "enable_rag": self.enable_rag,
            "enable_offline_mode": self.enable_offline_mode,
            "enable_auto_retry": self.enable_auto_retry,
            "whisper_model": self.whisper_model,
            "whisper_lang": self.whisper_lang,
            "stt_min_confidence": self.stt_min_confidence,
            "tts_lang": self.tts_lang,
        }


def load_config() -> VoiceConfig:
    """Load a fresh config from the environment (call after dotenv is loaded)."""
    return VoiceConfig()
