# Phase 7 — Workflow Visualization

Animated, interactive visualization of the real analysis pipeline every upload
flows through — for **any supported file format**, not just CSV.

## Pipeline (traced)
Upload → Parser → Categorizer → Aggregator → Anomaly → Forecaster →
Health Score → Savings → Memory → Persist → (deferred) Retriever → LLM Router →
Response.

The first eight run on every upload; Memory + Persist follow; the chat stages
(Retriever/LLM/Response) are marked **deferred** and light up per question.

## Any file format
`/upload` accepts CSV, TSV, TXT, Excel (.xlsx/.xlsm/.xls), OpenDocument (.ods),
JSON, and PDF. The **Upload** node reports the detected format + byte size, and
the **Parser** node reports the transaction count — every format then flows
through the identical downstream nodes. Verified live with CSV and JSON.

## Backend
- `orchestrator/trace.py` — `WorkflowTracer` records per-node `status`,
  `duration_ms`, `retries`, `error`, and a human `detail`. `step()` times a
  node, supports retries, and **re-raises** on final failure (never masks
  errors). `WORKFLOW_NODES` / `WORKFLOW_EDGES` define the graph; `build_graph()`
  returns the static skeleton.
- `orchestrator/pipeline.py` — `run_pipeline_traced(content, user_id, filename,
  tracer)` runs the **exact production nodes** sequentially, instrumented (same
  results as the LangGraph path).
- `main.py` — `_process_csv` records the Upload node (format + bytes), runs the
  traced pipeline, then traces Persist + Memory; stores the trace per user in
  `_LAST_WORKFLOW` and embeds it in the upload response.
- Endpoints: `GET /workflow/graph` (skeleton) and `GET /workflow/trace/{user_id}`
  (last run with timings/status/errors).

## Frontend
- `components/WorkflowPanel.tsx` — dashboard card: animated node chips with
  status colors, per-node timing + detail, total time, LangGraph badge, and an
  **"Immersive 3D"** button.
- `components/WorkflowExplorer.tsx` + `three/WorkflowScene.tsx` — a WebGL 3D
  flow graph: nodes as status-colored objects, animated connectors, click-to-
  inspect, OrbitControls. WebGL is created **only on demand** and wrapped in an
  `ErrorBoundary` (crash-safe — cannot black-screen the app).
- `api.ts` — `getWorkflowTrace`, `getWorkflowGraph`, and the `WorkflowNode` /
  `WorkflowTrace` types.

## Tests (`backend/tests/test_workflow.py`, 7)
Tracer records ok/timing/detail, retry-then-succeed, error-records-and-reraises,
deferred nodes flagged, total_ms accumulation, and a full `run_pipeline_traced`
over a CSV that touches every analysis node.

## Validation
- `pytest`: full suite green (69 tests). `tsc -b`: clean.
- Live: CSV (74 txns) and JSON both traced through all 10 nodes with real
  per-node timings; JSON reported format "JSON".
