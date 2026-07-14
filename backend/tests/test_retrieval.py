"""Phase 6 tests: retrieval trace + 3D projection helpers.

The Chroma layer is faked so tests run fast and offline.
"""
from __future__ import annotations

import math

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


def _fake_chroma_result(docs, dists, dim=8):
    # Mimic chromadb's {"key": [[...per-query...]]} shape with numpy-free lists.
    embs = []
    for i in range(len(docs)):
        v = [0.0] * dim
        v[i % dim] = 1.0
        embs.append(v)
    return {
        "documents": [docs],
        "distances": [dists],
        "embeddings": [embs],
        "metadatas": [[{} for _ in docs]],
    }


def test_retrieve_trace_structure(monkeypatch):
    monkeypatch.setattr(retriever, "_init", lambda: True)
    monkeypatch.setattr(retriever, "_embed_query", lambda q: [[1.0] + [0.0] * 7])

    def fake_query(collection, q_emb, k, where):
        if collection == "financial_knowledge":
            return _fake_chroma_result(
                ["Emergency fund covers 3-6 months", "Save 20% of income"],
                [0.2, 0.6],
            )
        return _fake_chroma_result(["[demo_user] savings rate 22%"], [0.4])

    monkeypatch.setattr(retriever, "_query_with_embeddings", fake_query)

    t = retriever.retrieve_trace("emergency fund", "demo_user", k=3)
    assert t["available"] is True
    assert t["query"] == "emergency fund"
    assert t["embedding"]["dimension"] == 8
    assert len(t["embedding"]["query_point"]) == 3

    chunks = t["chunks"]
    assert len(chunks) == 3
    # ranked by similarity descending
    sims = [c["similarity"] for c in chunks]
    assert sims == sorted(sims, reverse=True)
    # ranks are 1..n and each has a 3D point
    assert [c["rank"] for c in chunks] == [1, 2, 3]
    assert all(len(c["point"]) == 3 for c in chunks)
    # raw embedding vectors are stripped from the payload
    assert all("embedding" not in c for c in chunks)
    # stages + final context present
    assert t["stages"][0] == "Question" and t["stages"][-1] == "LLM Response"
    assert t["final_context"]


def test_retrieve_trace_unavailable(monkeypatch):
    monkeypatch.setattr(retriever, "_init", lambda: False)
    t = retriever.retrieve_trace("q", "u")
    assert t["available"] is False
    assert "reason" in t


def test_retrieve_trace_dedupes(monkeypatch):
    monkeypatch.setattr(retriever, "_init", lambda: True)
    monkeypatch.setattr(retriever, "_embed_query", lambda q: [[1.0] + [0.0] * 7])
    dup = _fake_chroma_result(["same doc", "same doc"], [0.2, 0.5])
    monkeypatch.setattr(retriever, "_query_with_embeddings", lambda c, e, k, w: dup)
    t = retriever.retrieve_trace("q", "demo_user", k=5)
    texts = [c["text"] for c in t["chunks"]]
    assert len(texts) == len(set(texts))  # de-duplicated
