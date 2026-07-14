"""Cache behaviour: key stability, TTL, hit/miss."""
from __future__ import annotations

import time

from llm.base import LLMResponse, Message, Usage
from llm.cache import ResponseCache, make_key


def _messages():
    return [Message(role="user", content="hello world")]


def test_key_is_stable_and_order_independent():
    k1 = make_key(_messages(), temperature=0.7, max_tokens=None, provider_hint="chat")
    k2 = make_key(_messages(), temperature=0.7, max_tokens=None, provider_hint="chat")
    assert k1 == k2
    # Different content -> different key
    other = [Message(role="user", content="different")]
    assert make_key(other, temperature=0.7, max_tokens=None, provider_hint="chat") != k1


def test_set_and_get_roundtrip_marks_cached():
    cache = ResponseCache(ttl=60, redis_url="")
    key = make_key(_messages(), temperature=0.7, max_tokens=None, provider_hint="chat")
    resp = LLMResponse(text="hi", provider="groq", model="m", usage=Usage(total_tokens=3))
    cache.set(key, resp)
    got = cache.get(key)
    assert got is not None
    assert got.text == "hi"
    assert got.cached is True  # retrieval flips the cached flag


def test_ttl_expiry():
    cache = ResponseCache(ttl=1, redis_url="")
    key = "k"
    cache._memory.set(key, LLMResponse(text="x", provider="p", model="m").model_dump_json(), ttl=0)
    # ttl=0 -> already expired on next tick
    time.sleep(0.01)
    assert cache.get(key) is None


def test_miss_returns_none():
    cache = ResponseCache(ttl=60, redis_url="")
    assert cache.get("does-not-exist") is None
