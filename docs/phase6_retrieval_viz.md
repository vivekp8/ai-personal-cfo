# Phase 6 — Retrieval Visualization (Interactive 3D)

Makes RAG transparent: shows the full pipeline
**Question → Embedding → Retrieved Chunks → Similarity Score → Ranking →
Final Context → LLM Response** with real numbers and an interactive 3D
embedding space.

## Backend (`rag/retriever.py`)
- `retrieve_trace(query, user_id, k)` returns a full, explainable trace:
  - the query and embedding metadata (model `all-MiniLM-L6-v2`, 384 dims),
  - every retrieved chunk with **cosine similarity**, **distance**, **rank**,
    source collection (knowledge vs your memory), and a **3D coordinate**,
  - the query's own 3D point, the assembled **final context**, and the stage list.
- `_project_3d` reduces the 384-dim query + chunk embeddings to 3D via **PCA**
  (falls back to first dims for tiny sets), scaled to a stable [-3, 3] frame so
  closer spheres genuinely mean more similar.
- Numpy-safe extraction (fixed a real bug: Chroma returns embeddings as numpy
  arrays, which broke the previous `array or [[]]` fallback).
- Never raises — returns `available: false` when RAG is off.

## API
- `POST /rag/trace` `{user_id, query, k}` → the trace (k clamped 1–10).

## Frontend
- `three/RetrievalScene.tsx` — react-three-fiber embedding space: a pulsing
  **query** node, **chunk spheres** positioned at their 3D coordinates (size ∝
  similarity, colour by collection), animated **connection lines** (opacity/width
  ∝ similarity), `OrbitControls` (drag/zoom), click-to-select with a wireframe
  highlight and billboarded rank/score labels.
- `components/RetrievalExplorer.tsx` — full-screen immersive overlay hosting the
  3D scene (transient WebGL context, wrapped in an `ErrorBoundary` with a text
  fallback), the animated 7-stage pipeline, a ranked chunk list with similarity
  bars, per-chunk cosine/distance, a legend, and the final-context preview.
- `components/RetrievalPanel.tsx` — dashboard card: query box + examples,
  animated stage flow, inline chunk similarity bars, and an **"Immersive 3D"**
  button that opens the explorer. Added to the dashboard grid.
- `api.ts` — `ragTrace` + `RagTraceResult` / `RagChunk` types.

## Crash-safety
The 3D `Canvas` only mounts while the explorer overlay is open (transient
context) and is `ErrorBoundary`-wrapped, avoiding the multi-context WebGL issue
seen earlier. The inline dashboard view is pure DOM/framer-motion.

## Tests (`backend/tests/test_retrieval.py`, 5)
Cosine helper, 3D projection shape/range, full trace structure (ranked by
similarity, ranks 1..n, 3D points, embeddings stripped, stages + context),
unavailable path, and de-duplication. Full suite: **62 passing**.

## Validation
- In-process trace on a real query returned 384-dim embeddings, correct cosine
  ranking (emergency-fund chunks top), PCA 3D points, knowledge + memory mix.
- `tsc -b` clean.
