"""RAG layer (Phase 3): ChromaDB + sentence-transformers.

Two persistent collections:
  - financial_knowledge: static budgeting/finance guidance
  - user_memory: per-user month summaries, anomalies, what-if results

Performance-oriented design:
  - The query is embedded ONCE per retrieve() and reused across collections.
  - Collection handles are cached (no repeated get_or_create round-trips).
  - Per-user memory is isolated with a Chroma metadata filter (server-side),
    not a slow Python-side scan of everyone's docs.
  - A small versioned in-process cache short-circuits repeated queries.
  - The embedding model can be warmed up at startup via preload().

Degrades gracefully: if chromadb / sentence-transformers are not installed,
retrieval returns an empty context and the app keeps working.
"""
from __future__ import annotations

import os
import threading
from collections import OrderedDict
from typing import Any

from rag.knowledge_seed import KNOWLEDGE_DOCS

_PERSIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_store")

_client: Any = None
_embed_fn: Any = None
_available = False
_init_lock = threading.Lock()

# Cached collection handles: name -> collection.
_collections: dict[str, Any] = {}

# Versioned retrieval cache. Bumping a user's version invalidates their entries.
_CACHE_MAX = 256
_query_cache: "OrderedDict[tuple, dict]" = OrderedDict()
_user_version: dict[str, int] = {}
_cache_lock = threading.Lock()


def _init() -> bool:
    global _client, _embed_fn, _available
    if _available:
        return True
    with _init_lock:
        if _available:
            return True
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except Exception:  # noqa: BLE001
            return False
        try:
            _client = chromadb.PersistentClient(path=_PERSIST_DIR)
            gemini_key = os.environ.get("GEMINI_API_KEY")
            if gemini_key:
                _embed_fn = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
                    api_key=gemini_key,
                    model_name="models/text-embedding-004"
                )
            else:
                _embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            _available = True
            _seed_knowledge()
        except Exception:  # noqa: BLE001
            _available = False
    return _available


def is_available() -> bool:
    return _init()


def preload() -> bool:
    """Warm up Chroma + the embedding model so the first query is fast.

    Safe to call from a background thread. Returns True if RAG is ready.
    """
    if not _init():
        return False
    try:
        # Force the sentence-transformer to load its weights now.
        _embed_query("warmup")
    except Exception:  # noqa: BLE001
        return False
    return True


def _get_collection(name: str):
    coll = _collections.get(name)
    if coll is None:
        coll = _client.get_or_create_collection(name=name, embedding_function=_embed_fn)
        _collections[name] = coll
    return coll


def _embed_query(query: str) -> list | None:
    """Embed the query once; returns a list of embeddings (or None on failure)."""
    try:
        emb = _embed_fn([query])
        # Normalise to plain python lists for Chroma.
        return [list(map(float, e)) for e in emb]
    except Exception:  # noqa: BLE001
        return None


def _bump_user(user_id: str) -> None:
    with _cache_lock:
        _user_version[user_id] = _user_version.get(user_id, 0) + 1
        # Drop this user's cached queries.
        stale = [k for k in _query_cache if k[0] == user_id]
        for k in stale:
            _query_cache.pop(k, None)


def _seed_knowledge() -> None:
    coll = _get_collection("financial_knowledge")
    if coll.count() >= len(KNOWLEDGE_DOCS):
        return
    ids = [f"kn_{i}" for i in range(len(KNOWLEDGE_DOCS))]
    metadatas = [{"kind": "knowledge"} for _ in KNOWLEDGE_DOCS]
    coll.upsert(documents=KNOWLEDGE_DOCS, ids=ids, metadatas=metadatas)


def index_user_memory(user_id: str, state: dict) -> None:
    """Auto-generate and embed per-user documents after processing."""
    if not _init():
        return
    coll = _get_collection("user_memory")
    docs: list[str] = []
    ids: list[str] = []
    metadatas: list[dict] = []

    def add(doc: str, doc_id: str, kind: str) -> None:
        docs.append(doc)
        ids.append(doc_id)
        metadatas.append({"user_id": user_id, "kind": kind})

    summary = state.get("monthly_summary", {})
    for month in summary.get("months", []):
        cats = summary["by_month_category"].get(month, {})
        parts = [f"{c}: Rs.{abs(v):,.0f}" for c, v in cats.items()]
        add(
            f"[{user_id}] In {month}, spending by category was: " + "; ".join(parts),
            f"{user_id}_summary_{month}",
            "summary",
        )

    for i, anom in enumerate(state.get("anomalies", [])):
        add(
            f"[{user_id}] Anomaly: {anom.get('message', '')}",
            f"{user_id}_anomaly_{i}",
            "anomaly",
        )

    hs = state.get("health_score", {})
    if hs:
        add(
            f"[{user_id}] Financial health score is {hs.get('score')} "
            f"({hs.get('rating')}), savings rate {hs.get('savings_rate', 0):.0%}.",
            f"{user_id}_score",
            "score",
        )

    if docs:
        coll.upsert(documents=docs, ids=ids, metadatas=metadatas)
        _bump_user(user_id)


def index_memory_items(user_id: str, items: list[dict]) -> None:
    """Embed long-term memory items for semantic recall (Phase 5).

    Each item: {"id": str, "text": str, "kind": str}. No-op if RAG unavailable.
    """
    if not _init() or not items:
        return
    coll = _get_collection("user_memory")
    docs, ids, metadatas = [], [], []
    for it in items:
        text = (it.get("text") or "").strip()
        if not text:
            continue
        docs.append(f"[{user_id}] {text}")
        ids.append(f"{user_id}_mem_{it.get('id')}")
        metadatas.append({"user_id": user_id, "kind": it.get("kind", "memory")})
    if docs:
        coll.upsert(documents=docs, ids=ids, metadatas=metadatas)
        _bump_user(user_id)


def index_whatif(user_id: str, whatif: dict) -> None:
    if not _init():
        return
    coll = _get_collection("user_memory")
    full = whatif["pay_full"]
    emi = whatif["emi"]
    doc = (
        f"[{user_id}] What-if purchase of Rs.{whatif['purchase_amount']:,.0f}: "
        f"pay-full score {full['health_score']}, EMI score {emi['health_score']} "
        f"(EMI Rs.{emi['emi_monthly']:,.0f}/mo over {whatif['tenure_months']} months)."
    )
    coll.upsert(
        documents=[doc],
        ids=[f"{user_id}_whatif_latest"],
        metadatas=[{"user_id": user_id, "kind": "whatif"}],
    )
    _bump_user(user_id)


def _query_knowledge(q_emb: list | None, query: str, k: int) -> list[tuple[str, float]]:
    coll = _get_collection("financial_knowledge")
    try:
        if q_emb is not None:
            res = coll.query(
                query_embeddings=q_emb, n_results=k, include=["documents", "distances"]
            )
        else:
            res = coll.query(
                query_texts=[query], n_results=k, include=["documents", "distances"]
            )
        docs = res.get("documents", [[]])[0]
        dists = res.get("distances", [[]])[0] or [0.0] * len(docs)
        return list(zip(docs, dists))
    except Exception:  # noqa: BLE001
        return []


def _query_memory(
    q_emb: list | None, query: str, user_id: str, k: int
) -> list[tuple[str, float]]:
    coll = _get_collection("user_memory")

    def run(where: dict | None):
        if q_emb is not None:
            return coll.query(
                query_embeddings=q_emb,
                n_results=k,
                where=where,
                include=["documents", "distances"],
            )
        return coll.query(
            query_texts=[query],
            n_results=k,
            where=where,
            include=["documents", "distances"],
        )

    try:
        # Server-side isolation by user metadata (fast + correct).
        res = run({"user_id": user_id})
        docs = res.get("documents", [[]])[0]
        if not docs:
            # Backward-compat: older docs have no metadata — fall back to a
            # broader query filtered by the user tag embedded in the text.
            res = run(None)
            docs = res.get("documents", [[]])[0]
            dists = res.get("distances", [[]])[0] or [0.0] * len(docs)
            return [(d, dist) for d, dist in zip(docs, dists) if f"[{user_id}]" in d]
        dists = res.get("distances", [[]])[0] or [0.0] * len(docs)
        return list(zip(docs, dists))
    except Exception:  # noqa: BLE001
        return []


def retrieve(query: str, user_id: str, k: int = 3) -> dict:
    """Return {context, sources, available} for a query.

    Embeds the query once, retrieves top-k from each collection, then merges
    and de-duplicates results ranked by distance. Results are cached per
    (user, query) and invalidated when the user's memory changes.
    """
    if not _init():
        return {"context": "", "sources": [], "available": False}

    with _cache_lock:
        version = _user_version.get(user_id, 0)
        cache_key = (user_id, query, k, version)
        hit = _query_cache.get(cache_key)
        if hit is not None:
            _query_cache.move_to_end(cache_key)
            return hit

    q_emb = _embed_query(query)
    knowledge = _query_knowledge(q_emb, query, k)
    memory = _query_memory(q_emb, query, user_id, k)

    # Merge, de-duplicate, and rank by ascending distance (closer = better).
    seen: set[str] = set()
    ranked: list[tuple[str, float]] = []
    for doc, dist in sorted(knowledge + memory, key=lambda x: x[1]):
        if doc in seen:
            continue
        seen.add(doc)
        ranked.append((doc, dist))

    sources = [doc for doc, _ in ranked]
    context = "\n".join(f"- {s}" for s in sources)
    result = {"context": context, "sources": sources, "available": True}

    with _cache_lock:
        _query_cache[cache_key] = result
        _query_cache.move_to_end(cache_key)
        while len(_query_cache) > _CACHE_MAX:
            _query_cache.popitem(last=False)

    return result


# --------------------------------------------------------------------------- #
# Phase 6 — Retrieval Visualization
# --------------------------------------------------------------------------- #
def _cosine(a, b) -> float:
    import numpy as np

    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _project_3d(query_emb: list, chunk_embs: list[list]) -> tuple[list, list[list]]:
    """Project the query + chunk embeddings into 3D for visualization.

    Uses PCA when there are enough points; otherwise pads the first dims. Always
    returns coordinates scaled to a pleasant [-3, 3] range.
    """
    import numpy as np

    mat = np.asarray([query_emb] + chunk_embs, dtype=float)
    n, d = mat.shape
    if n >= 4 and d >= 3:
        try:
            from sklearn.decomposition import PCA

            coords = PCA(n_components=3).fit_transform(mat)
        except Exception:  # noqa: BLE001
            coords = mat[:, :3]
    else:
        coords = np.zeros((n, 3))
        coords[:, : min(3, d)] = mat[:, : min(3, d)]

    # Scale to [-3, 3] per axis for stable framing in the 3D scene.
    mn, mx = coords.min(axis=0), coords.max(axis=0)
    span = np.where((mx - mn) == 0, 1.0, (mx - mn))
    scaled = (coords - mn) / span * 6.0 - 3.0
    return scaled[0].tolist(), [row.tolist() for row in scaled[1:]]


def _query_with_embeddings(collection: str, q_emb: list, k: int, where: dict | None):
    coll = _get_collection(collection)
    try:
        return coll.query(
            query_embeddings=q_emb,
            n_results=k,
            where=where,
            include=["documents", "distances", "embeddings", "metadatas"],
        )
    except Exception:  # noqa: BLE001
        return {}


def retrieve_trace(query: str, user_id: str, k: int = 4) -> dict:
    """Full, explainable retrieval trace for the RAG visualiser.

    Returns the query, embedding metadata, every retrieved chunk with its
    cosine similarity + rank + 3D coordinates, the query's 3D point, and the
    final assembled context. Never raises — returns available=False if RAG is off.
    """
    if not _init():
        return {"available": False, "reason": "RAG (chromadb) not available."}

    q_emb_list = _embed_query(query)
    if not q_emb_list:
        return {"available": False, "reason": "Could not embed the query."}
    q_emb = q_emb_list[0]

    raw: list[dict] = []
    for coll_name, where in (
        ("financial_knowledge", None),
        ("user_memory", {"user_id": user_id}),
    ):
        res = _query_with_embeddings(coll_name, [q_emb], k, where)

        # Chroma may return numpy arrays; avoid boolean checks on arrays.
        def _first(value):
            if value is None:
                return None
            try:
                inner = value[0]
            except (IndexError, TypeError, KeyError):
                return None
            return inner

        docs = _first(res.get("documents"))
        docs = list(docs) if docs is not None else []
        dists = _first(res.get("distances"))
        dists = list(dists) if dists is not None else [0.0] * len(docs)
        embs = _first(res.get("embeddings"))
        embs = list(embs) if embs is not None else [[] for _ in docs]

        for i, doc in enumerate(docs):
            if not doc:
                continue
            dist = float(dists[i]) if i < len(dists) else 0.0
            emb = list(embs[i]) if i < len(embs) and embs[i] is not None else []
            raw.append({
                "text": doc,
                "collection": coll_name,
                "distance": round(dist, 4),
                "similarity": round(max(0.0, _cosine(q_emb, emb)), 4) if len(emb) else 0.0,
                "embedding": emb,
            })

    # De-duplicate by text, keep the highest similarity instance.
    best: dict[str, dict] = {}
    for c in raw:
        if c["text"] not in best or c["similarity"] > best[c["text"]]["similarity"]:
            best[c["text"]] = c
    chunks = sorted(best.values(), key=lambda c: c["similarity"], reverse=True)

    # 3D projection of query + chunks.
    query_point = [0.0, 0.0, 0.0]
    if chunks:
        query_point, points = _project_3d(q_emb, [c["embedding"] for c in chunks])
        for c, p in zip(chunks, points):
            c["point"] = p

    # Assign ranks and drop the raw embedding vectors from the payload.
    for i, c in enumerate(chunks):
        c["rank"] = i + 1
        c.pop("embedding", None)

    top = chunks[:k]
    final_context = "\n".join(f"- {c['text']}" for c in top)

    return {
        "available": True,
        "query": query,
        "embedding": {
            "model": "all-MiniLM-L6-v2",
            "dimension": len(q_emb),
            "query_point": query_point,
        },
        "chunks": chunks,
        "top_k": len(top),
        "final_context": final_context,
        "stages": [
            "Question", "Embedding", "Retrieved Chunks",
            "Similarity Score", "Ranking", "Final Context", "LLM Response",
        ],
    }
