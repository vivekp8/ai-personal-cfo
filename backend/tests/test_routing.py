"""Phase 8 tests: model-routing preferred-provider override + selection."""
from __future__ import annotations

import pytest

from llm.router import LLMRouter


@pytest.fixture()
def router(monkeypatch):
    r = LLMRouter()
    # Make all providers appear available deterministically (no network/keys).
    monkeypatch.setattr(r, "available_providers", lambda: list(r.all_providers()))
    return r


def test_default_preferred_is_auto(router, monkeypatch):
    monkeypatch.delenv("DEFAULT_PROVIDER", raising=False)
    assert router.preferred() == "auto"
    # auto → full priority chain unchanged
    assert router._selection() == router.all_providers()


def test_set_preferred_moves_provider_first(router):
    assert router.set_preferred("gemini") == "gemini"
    sel = router._selection()
    assert sel[0] == "gemini"
    assert set(sel) == set(router.all_providers())  # rest remain as fallback


def test_set_preferred_auto_restores_chain(router):
    router.set_preferred("groq")
    router.set_preferred("auto")
    assert router.preferred() == "auto"
    assert router._selection() == router.all_providers()


def test_set_preferred_none_is_auto(router):
    router.set_preferred("groq")
    assert router.set_preferred(None) == "auto"


def test_set_preferred_rejects_unknown(router):
    with pytest.raises(ValueError):
        router.set_preferred("claude")


def test_runtime_override_beats_env(router, monkeypatch):
    monkeypatch.setenv("DEFAULT_PROVIDER", "gemini")
    router.set_preferred("groq")
    assert router.preferred() == "groq"
    assert router._selection()[0] == "groq"


def test_unavailable_preferred_falls_back_to_chain(monkeypatch):
    r = LLMRouter()
    # Only groq available; prefer gemini (unavailable) → chain stays as available.
    monkeypatch.setattr(r, "available_providers", lambda: ["groq"])
    r.set_preferred("gemini")
    assert r._selection() == ["groq"]
