"""Voice layer tests: config, STT/TTS registries, failover, confidence retry,
and backward-compatible facade. All offline — providers are faked.
"""
from __future__ import annotations

import pytest

from voice.config import VoiceConfig
from voice.stt.base import STTProvider, STTResult
from voice.stt.registry import STTRegistry
from voice.tts.base import TTSProvider, TTSResult
from voice.tts.registry import TTSRegistry


# ---- fakes ---------------------------------------------------------------- #
class FakeSTT(STTProvider):
    def __init__(self, name, *, available=True, text="hello", conf=0.9, error=None, offline=False):
        self.name = name
        self._available = available
        self._text = text
        self._conf = conf
        self._error = error
        self.offline = offline
        self.calls = 0

    def is_available(self):
        return self._available

    def transcribe(self, audio_bytes, suffix=".webm"):
        self.calls += 1
        return STTResult(
            text="" if self._error else self._text,
            confidence=self._conf, provider=self.name, error=self._error,
        )


class FakeTTS(TTSProvider):
    def __init__(self, name, *, available=True, audio=b"AUDIO", error=None):
        self.name = name
        self._available = available
        self._audio = audio
        self._error = error

    def is_available(self):
        return self._available

    def synthesize(self, text, *, lang="en", voice=None):
        if self._error:
            return TTSResult(provider=self.name, error=self._error)
        return TTSResult(audio=self._audio, provider=self.name)


def _cfg(**kw) -> VoiceConfig:
    base = dict(
        stt_priority=["a", "b", "c"],
        tts_priority=["x", "y"],
        stt_min_confidence=0.75,
        enable_auto_retry=True,
    )
    base.update(kw)
    return VoiceConfig(**base)


# ---- config --------------------------------------------------------------- #
def test_config_from_env(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "groq_whisper, whisper_local")
    monkeypatch.setenv("VOICE_STT_MIN_CONFIDENCE", "0.6")
    monkeypatch.setenv("ENABLE_OFFLINE_MODE", "false")
    from voice.config import load_config

    c = load_config()
    assert c.stt_priority == ["groq_whisper", "whisper_local"]
    assert c.stt_min_confidence == 0.6
    assert c.enable_offline_mode is False


# ---- STT registry --------------------------------------------------------- #
def test_stt_uses_first_confident_provider():
    reg = STTRegistry(_cfg())
    reg._providers = {
        "a": FakeSTT("a", conf=0.9),
        "b": FakeSTT("b", conf=0.5),
    }
    reg._config = _cfg(stt_priority=["a", "b"])
    r = reg.transcribe(b"x")
    assert r.provider == "a"
    assert r.confidence == 0.9


def test_stt_fails_over_on_error():
    reg = STTRegistry(_cfg(stt_priority=["a", "b"]))
    a = FakeSTT("a", error="boom")
    b = FakeSTT("b", conf=0.9)
    reg._providers = {"a": a, "b": b}
    r = reg.transcribe(b"x")
    assert r.provider == "b"
    assert a.calls == 1 and b.calls == 1


def test_stt_confidence_retry_then_best():
    # Both below threshold → returns the higher-confidence one, flagged.
    reg = STTRegistry(_cfg(stt_priority=["a", "b"]))
    reg._providers = {
        "a": FakeSTT("a", conf=0.4),
        "b": FakeSTT("b", conf=0.6),
    }
    r = reg.transcribe(b"x")
    assert r.provider == "b"
    assert r.error == "low_confidence"


def test_stt_no_retry_when_disabled():
    reg = STTRegistry(_cfg(stt_priority=["a", "b"], enable_auto_retry=False))
    reg._providers = {"a": FakeSTT("a", conf=0.4), "b": FakeSTT("b", conf=0.99)}
    r = reg.transcribe(b"x")
    assert r.provider == "a"  # returned immediately despite low confidence


def test_stt_offline_only_filters_online_providers():
    reg = STTRegistry(_cfg(stt_priority=["a", "b"]))
    reg._providers = {
        "a": FakeSTT("a", conf=0.9, offline=False),
        "b": FakeSTT("b", conf=0.9, offline=True),
    }
    r = reg.transcribe(b"x", offline=True)
    assert r.provider == "b"


def test_stt_no_providers_available():
    reg = STTRegistry(_cfg(stt_priority=["a"]))
    reg._providers = {"a": FakeSTT("a", available=False)}
    r = reg.transcribe(b"x")
    assert r.error and "No STT provider" in r.error


# ---- TTS registry --------------------------------------------------------- #
def test_tts_fails_over():
    reg = TTSRegistry(_cfg(tts_priority=["x", "y"]))
    reg._providers = {"x": FakeTTS("x", error="down"), "y": FakeTTS("y")}
    r = reg.synthesize("hello")
    assert r.provider == "y" and r.ok


def test_tts_all_fail():
    reg = TTSRegistry(_cfg(tts_priority=["x"]))
    reg._providers = {"x": FakeTTS("x", available=False)}
    r = reg.synthesize("hello")
    assert not r.ok


# ---- backward-compatible facade ------------------------------------------- #
def test_facade_transcribe_shape(monkeypatch):
    from voice import service as svc_mod
    from voice import voice_service

    class _S:
        class config:
            stt_min_confidence = 0.75

        def transcribe(self, audio, suffix=".webm"):
            return STTResult(text="hi", confidence=0.9, provider="fake", language="en", latency_ms=10)

    monkeypatch.setattr(voice_service, "service", _S())
    out = voice_service.transcribe(b"12345", ".webm")
    # original keys preserved
    assert out["text"] == "hi"
    assert out["available"] is True
    assert out["bytes"] == 5
    # new metadata present
    assert out["provider"] == "fake"
    assert out["confidence"] == 0.9
    assert out["low_confidence"] is False
