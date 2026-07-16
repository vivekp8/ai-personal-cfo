"""Financial memory retrieval (Phase 3/4/5) using Supabase pgvector.

Indexes core knowledge, per-user memory, and what-ifs. Provides semantic search.
Uses Supabase to ensure vectors persist across ephemeral container restarts on Render.
"""
from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict

import google.generativeai as genai
from supabase import create_client, Client

from .knowledge_seed import KNOWLEDGE_DOCS

logger = logging.getLogger("rag.retriever")

_client: Client | None = None
_available = False
_init_lock = threading.Lock()

# Versioned retrieval cache. Bumping a user's version invalidates their entries.
_CACHE_MAX = 256
_query_cache: "OrderedDict[tuple, dict]" = OrderedDict()
_user_version: dict[str, int] = {}
_cache_lock = threading.Lock()


def _init() -> bool:
    global _client, _available
    if _available:
        return True
    with _init_lock:
        if _available:
            return True
        try:
            supabase_url = os.environ.get("SUPABASE_URL")
            supabase_key = os.environ.get("SUPABASE_KEY")
            gemini_key = os.environ.get("GEMINI_API_KEY")

            if not supabase_url or not supabase_key or not gemini_key:
                return False

            genai.configure(api_key=gemini_key)
            _client = create_client(supabase_url, supabase_key)

            _available = True
            _seed_knowledge()
        except Exception as e:
            logger.error("Failed to initialize Supabase RAG: %s", e)
            _available = False
    return _available


def is_available() -> bool:
    return _init()


def preload() -> bool:
    """Warm up Supabase + the embedding model so the first query is fast."""
    if not _init():
        return False
    try:
        _embed_query("warmup")
    except Exception:  # noqa: BLE001
        return False
    return True


def _embed_query(query: str) -> list[float] | None:
    """Embed the query once; returns a list of embeddings (or None on failure)."""
    try:
        response = genai.embed_content(
            model="models/text-embedding-004",
            content=query,
            task_type="retrieval_query",
        )
        return response["embedding"]
    except Exception as e:
        logger.error("Failed to embed query: %s", e)
        return None

def _embed_documents(docs: list[str]) -> list[list[float]] | None:
    """Embed multiple documents."""
    if not docs:
        return []
    try:
        response = genai.embed_content(
            model="models/text-embedding-004",
            content=docs,
            task_type="retrieval_document",
        )
        return response["embedding"] if isinstance(response["embedding"][0], list) else [response["embedding"]]
    except Exception as e:
        logger.error("Failed to embed documents: %s", e)
        return None


def _bump_user(user_id: str) -> None:
    with _cache_lock:
        _user_version[user_id] = _user_version.get(user_id, 0) + 1
        # Drop this user's cached queries.
        stale = [k for k in _query_cache if k[0] == user_id]
        for k in stale:
            _query_cache.pop(k, None)


def _seed_knowledge() -> None:
    """Seeds static knowledge if not already present."""
    if not _client:
        return
    
    try:
        # Check if already seeded by querying
        res = _client.table("memory_docs").select("id", count="exact").eq("metadata->>kind", "knowledge").execute()
        if res.count and res.count >= len(KNOWLEDGE_DOCS):
            return

        embeddings = _embed_documents(KNOWLEDGE_DOCS)
        if not embeddings:
            return

        records = []
        for i, (doc, emb) in enumerate(zip(KNOWLEDGE_DOCS, embeddings)):
            records.append({
                "id": f"kn_{i}",
                "content": doc,
                "embedding": emb,
                "metadata": {"kind": "knowledge"}
            })
        
        _client.table("memory_docs").upsert(records).execute()
    except Exception as e:
        logger.error("Failed to seed knowledge: %s", e)


def index_user_memory(user_id: str, state: dict) -> None:
    """Auto-generate and embed per-user documents after processing."""
    if not _init() or not _client:
        return
    
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
        embeddings = _embed_documents(docs)
        if embeddings:
            records = [{"id": _id, "content": doc, "embedding": emb, "metadata": meta} 
                       for _id, doc, emb, meta in zip(ids, docs, embeddings, metadatas)]
            _client.table("memory_docs").upsert(records).execute()
            _bump_user(user_id)


def index_memory_items(user_id: str, items: list[dict]) -> None:
    """Embed long-term memory items for semantic recall (Phase 5)."""
    if not _init() or not items or not _client:
        return
    
    docs, ids, metadatas = [], [], []
    for it in items:
        text = (it.get("text") or "").strip()
        if not text:
            continue
        doc_str = f"[{user_id}] {text}"
        docs.append(doc_str)
        ids.append(f"{user_id}_mem_{it.get('id')}")
        metadatas.append({"user_id": user_id, "kind": it.get("kind", "memory")})
        
    if docs:
        embeddings = _embed_documents(docs)
        if embeddings:
            records = [{"id": _id, "content": doc, "embedding": emb, "metadata": meta} 
                       for _id, doc, emb, meta in zip(ids, docs, embeddings, metadatas)]
            _client.table("memory_docs").upsert(records).execute()
            _bump_user(user_id)


def index_whatif(user_id: str, whatif: dict) -> None:
    if not _init() or not _client:
        return
    
    full = whatif["pay_full"]
    emi = whatif["emi"]
    doc = (
        f"[{user_id}] What-if purchase of Rs.{whatif['purchase_amount']:,.0f}: "
        f"pay-full score {full['health_score']}, EMI score {emi['health_score']} "
        f"(EMI Rs.{emi['emi_monthly']:,.0f}/mo over {whatif['tenure_months']} months)."
    )
    
    embeddings = _embed_documents([doc])
    if embeddings:
        records = [{
            "id": f"{user_id}_whatif_latest",
            "content": doc,
            "embedding": embeddings[0],
            "metadata": {"user_id": user_id, "kind": "whatif"}
        }]
        _client.table("memory_docs").upsert(records).execute()
        _bump_user(user_id)


def _query_knowledge(q_emb: list[float] | None, k: int) -> list[tuple[str, float]]:
    if q_emb is None or not _client:
        return []
    try:
        res = _client.rpc("match_memories", {
            "query_embedding": q_emb,
            "match_threshold": 0.0,
            "match_count": k,
            "filter_metadata": {"kind": "knowledge"}
        }).execute()
        return [(match['content'], match['similarity']) for match in res.data]
    except Exception:  # noqa: BLE001
        return []


def _query_memory(q_emb: list[float] | None, user_id: str, k: int) -> list[tuple[str, float]]:
    if q_emb is None or not _client:
        return []
    try:
        res = _client.rpc("match_memories", {
            "query_embedding": q_emb,
            "match_threshold": 0.0,
            "match_count": k,
            "filter_metadata": {"user_id": user_id}
        }).execute()
        return [(match['content'], match['similarity']) for match in res.data]
    except Exception:  # noqa: BLE001
        return []


def retrieve(query: str, user_id: str, k: int = 3) -> dict:
    """Return {context, sources, available} for a query."""
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
    knowledge = _query_knowledge(q_emb, k)
    memory = _query_memory(q_emb, user_id, k)

    # Merge, de-duplicate, and rank by descending similarity (higher = better).
    seen: set[str] = set()
    ranked: list[tuple[str, float]] = []
    for doc, score in sorted(knowledge + memory, key=lambda x: x[1], reverse=True):
        if doc in seen:
            continue
        seen.add(doc)
        ranked.append((doc, score))

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

    mn, mx = coords.min(axis=0), coords.max(axis=0)
    span = np.where((mx - mn) == 0, 1.0, (mx - mn))
    coords = ((coords - mn) / span) * 6.0 - 3.0
    
    coords_list = coords.tolist()
    return coords_list[0], coords_list[1:]


def visualize_retrieval(query: str, user_id: str, k: int = 3) -> dict | None:
    """Return a point cloud representation of the latest query."""
    if not _init() or not _client:
        return None

    q_emb = _embed_query(query)
    if q_emb is None:
        return None

    # Fetch knowledge chunks with values. Supabase returns vector as string. We need to convert it.
    try:
        res_k = _client.rpc("match_memories", {
            "query_embedding": q_emb,
            "match_threshold": 0.0,
            "match_count": k,
            "filter_metadata": {"kind": "knowledge"}
        }).execute()
        
        res_m = _client.rpc("match_memories", {
            "query_embedding": q_emb,
            "match_threshold": 0.0,
            "match_count": k,
            "filter_metadata": {"user_id": user_id}
        }).execute()
    except Exception:
        return None

    matches = res_k.data + res_m.data
    if not matches:
        return None

    # To get raw embeddings for visualization, we need another query to pull the 'embedding' column
    # since our RPC doesn't return the raw vector to save bandwidth.
    ids_to_fetch = [m['id'] for m in matches]
    try:
        vec_res = _client.table("memory_docs").select("id, embedding").in_("id", ids_to_fetch).execute()
        vec_map = {row['id']: row['embedding'] for row in vec_res.data}
    except Exception:
        return None

    # Deduplicate matches
    seen = set()
    unique_matches = []
    for m in sorted(matches, key=lambda x: x['similarity'], reverse=True):
        text = m.get('content', '')
        if text not in seen and m['id'] in vec_map:
            seen.add(text)
            unique_matches.append(m)

    if not unique_matches:
        return None

    def _parse_vec(v):
        if isinstance(v, str):
            # pgvector format: "[0.1, 0.2, ...]"
            import ast
            return ast.literal_eval(v)
        return v

    chunk_embs = [_parse_vec(vec_map[m['id']]) for m in unique_matches]
    q3, c3 = _project_3d(q_emb, chunk_embs)

    chunks = []
    for m, c3_coord in zip(unique_matches, c3):
        chunks.append({
            "text": m.get('content', ''),
            "score": m.get('similarity', 0.0),
            "pos": c3_coord,
            "kind": m.get('metadata', {}).get('kind', 'unknown'),
        })

    return {
        "query": query,
        "query_pos": q3,
        "chunks": chunks,
    }
