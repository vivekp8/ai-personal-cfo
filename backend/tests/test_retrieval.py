"""Phase 6 tests: retrieval trace + 3D projection helpers.

Tests updated for the Supabase RAG implementation.
"""
from __future__ import annotations

import pytest

from rag import retriever


def test_cosine_basics():
    assert retriever._cosine([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert retriever._cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert retriever._cosine([0, 0], [1, 1]) == 0.0  # zero vector guard


def test_project_3d_shapes_and_range():
    q = [1.0, 2.0, 3.0, 4.0]
    chunks = [[1.1, 2.0, 3.0, 4.0], [0.0, 0.0, 0.0, 0.0], [5.0, 5.0, 5.0, 5.0], [2, 1, 0, 3]]
    qp, pts = retriever._project_3d(q, chunks)
    assert len(qp) == 3
    assert len(pts) == len(chunks)
    for p in [qp] + pts:
        assert len(p) == 3
        assert all(-3.0001 <= v <= 3.0001 for v in p)


def test_retrieve_unavailable(monkeypatch):
    monkeypatch.setattr(retriever, "_init", lambda: False)
    t = retriever.retrieve("q", "u")
    assert t["available"] is False
    assert "sources" in t


def test_retrieve_dedupes_and_limits(monkeypatch):
    monkeypatch.setattr(retriever, "_init", lambda: True)
    monkeypatch.setattr(retriever, "_embed_query", lambda q: [1.0] + [0.0] * 7)
    
    # Mocking knowledge and memory to return duplicates and multiple items
    monkeypatch.setattr(retriever, "_query_knowledge", lambda e, k: [("doc A", 0.9), ("doc B", 0.7)])
    monkeypatch.setattr(retriever, "_query_memory", lambda e, u, k: [("doc A", 0.9), ("doc C", 0.8), ("doc D", 0.6)])
    
    # Force empty cache
    with retriever._cache_lock:
        retriever._query_cache.clear()
        
    res = retriever.retrieve("q", "demo_user", k=2)
    assert res["available"] is True
    
    sources = res["sources"]
    assert len(sources) == 2  # Truncated to k=2
    # Should be sorted by score descending, deduped: A (0.9), C (0.8), B (0.7), D (0.6) -> top 2 are A and C
    assert sources == ["doc A", "doc C"]


def test_visualize_retrieval_unavailable(monkeypatch):
    monkeypatch.setattr(retriever, "_init", lambda: False)
    assert retriever.visualize_retrieval("q", "u") is None
