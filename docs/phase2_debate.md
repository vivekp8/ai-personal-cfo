# Phase 2 — Multi-Agent Debate System

Eight specialists analyse the user's computed financial state, each with an
isolated responsibility, a confidence score, logged reasoning, retry and
timeout handling. A Final Decision Agent synthesises them into one
confidence-weighted, prioritised recommendation. State is shared through
LangGraph.

## Panel
Risk · Savings · Investment · Lifestyle · Budget · Tax · Financial Planner
→ **Final Decision Agent** (chair).

## Design (performance-safe)
- Each specialist has a **deterministic, data-grounded heuristic** and an
  optional LLM path. By default (`DEBATE_AGENT_LLM=0`) specialists use the
  heuristic — firing 8 concurrent LLM calls overwhelms rate-limited providers.
  The **decider** makes a single LLM call to synthesise a natural recommendation.
- Set `DEBATE_AGENT_LLM=1` (higher-tier keys) to enable per-agent LLM reasoning.
- **Retry + timeout** per LLM call (`_safe_generate`, tight timeout, bounded
  attempts) with a **45s overall debate deadline**; on breach it returns instant
  heuristic opinions. It can never hang the endpoint.
- Confidence is clamped to [0, 1]. Opinions are returned in canonical panel order.

## LangGraph
`START → (all specialists in parallel) → decider → END`, with the shared
`opinions` list merged by an `operator.add` reducer. If LangGraph is missing,
the identical panel runs concurrently via a thread pool.

## Files
- `agents/debate/base.py` — `AgentOpinion`, `SpecialistAgent`, `_safe_generate`,
  JSON opinion parsing.
- `agents/debate/specialists.py` — the 7 specialists + grounded heuristics.
- `agents/debate/decider.py` — Final Decision Agent (confidence-weighted,
  LLM-synthesised summary with deterministic fallback).
- `agents/debate/graph.py` — LangGraph orchestration, env gate, overall timeout,
  `run_debate`, `list_agents`.

## API
- `POST /debate` `{user_id, question?}` → `{opinions[], decision, meta}`
- `GET /debate/agents` → panel metadata

## Frontend
- `components/DebatePanel.tsx` — immersive glass panel: "Convene panel" button,
  animated deliberation, 3D-tilt opinion cards (tap to flip to key points),
  animated confidence bars, and a highlighted Final Decision card with a
  consensus gauge and ranked priority chips. Added to the dashboard grid.
- `api.ts` — `runDebate`, `AgentOpinion`, `DebateResult` types.

## Tests
`backend/tests/test_debate.py` (offline): panel size, per-agent valid opinions,
full run shape + priority ordering, fallback path, confidence clamping,
retry/timeout wrapper (times out and succeeds), JSON parsing.

## Validation
- `pytest`: full suite green (22 tests).
- Live `POST /debate`: ~1.0s, 7 opinions, LangGraph on, decider LLM-enriched.
- Diagnostics clean on all changed files.
