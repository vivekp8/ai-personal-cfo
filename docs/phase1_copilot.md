# Phase 1 — AI Financial Copilot

A memory-aware, multi-turn conversational layer on top of the existing
deterministic financial pipeline. It extends (does not replace) the previous
single-shot `/chat` explainer.

## What it does
- Natural-language, context-aware conversations grounded in the user's data.
- Uses **RAG** (financial knowledge + per-user memory) and the **LLM router**.
- Understands previous turns, so **follow-up questions** resolve correctly
  (e.g. "why is it at that level?" refers to the prior answer).
- Explains every financial metric using only computed numbers — **never invents
  figures**. If a number is missing it says so.
- Degrades gracefully: with no LLM configured, returns a deterministic,
  clearly-labelled computed answer.

## Architecture
```
POST /chat
  → load conversation history (SQLite)
  → RAG retrieve (knowledge + user memory)
  → copilot.converse(query, computed_result, rag, history)
       → intent routing → data slice → grounded prompt (+ history) → LLM router
  → persist user + assistant turns
  → return {response, intent, retrieved_context, llm_used}
```

## Backend
- `agents/copilot.py` — `converse(query, result, rag, history)`; builds a
  history-aware, strictly-grounded prompt; falls back to the deterministic
  explainer when the LLM is unavailable or errors. Structured logging via the
  `agents.copilot` logger.
- `db/database.py` — new `conversations` table + helpers:
  - `save_message(user_id, role, content, intent=None, llm_used=None)`
  - `get_conversation(user_id, limit=50)` — chronological, most-recent-N
  - `clear_conversation(user_id)` — returns rows removed
- `main.py` endpoints:
  - `POST /chat` — now memory-aware (backward-compatible response shape)
  - `GET /chat/history/{user_id}` — `{ history: [...] }`
  - `DELETE /chat/history/{user_id}` — `{ status, removed }`

## Frontend
- `api.ts` — `getChatHistory`, `clearChatHistory`, `ChatHistoryMessage` type.
- `components/ChatPanel.tsx` — loads persisted history on mount, renders it, and
  adds a **Clear** button that wipes conversation memory.

## Tests
`backend/tests/test_copilot.py` (all green, no network/LLM calls):
- LLM path threads history into the prompt and marks `llm_used=True`.
- Fallback path when LLM not configured (grounded, `llm_used=False`).
- LLM-error path surfaces `llm_error` and still answers deterministically.
- Conversation persistence: save / ordered retrieval / limit / clear.
- Import-smoke test to guard wiring.

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_copilot.py -q`

## Validation performed
- `pytest` full suite: 14 passed.
- Live: two-turn chat where a subjectless follow-up resolved against the prior
  turn; history persisted (4 rows) and `DELETE` cleared it (removed=4).
- Type/diagnostics clean on all changed backend and frontend files.

## Backward compatibility
- `/chat` response shape is unchanged; only conversation memory was added.
- The `/whatif` endpoint still uses `explainer.explain` unchanged.
