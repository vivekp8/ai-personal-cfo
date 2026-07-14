# Phase 5 — Long-Term Memory

The assistant now "remembers" durable facts about the user across sessions and
recalls them automatically during conversations.

## What it remembers
Spending habits · recurring expenses · subscriptions · salary history · goals ·
preferences · conversation summaries.

## Design
- **Source of truth**: SQLite `memories(user_id, kind, mem_key, content, data,
  …)` — listable, reliable, unique per `(user, kind, key)`.
- **Semantic recall**: each item is embedded into ChromaDB (`user_memory`) via
  the retriever, in a **background thread** so a cold embedding-model load never
  blocks the API. SQLite is authoritative even if embedding is skipped.
- **Deterministic extraction**: `extract_memories(result)` derives facts from
  real transactions (recurring = merchant repeats across ≥2 months;
  subscriptions = recurring + known-service hints; salary = monthly income;
  habits = top category + typical savings rate). No invented facts.

## Engine (`agents/memory.py`)
- `remember_from_result(user_id, result)` — extract + upsert + embed on upload.
- `recall_context(user_id)` — compact, priority-ordered memory string injected
  into the copilot prompt (preferences/goals first).
- `all_memories(user_id)` — grouped by kind for the UI.
- `set_preference` / `add_goal` — user-owned durable memory.
- `summarize_conversation(user_id, history)` — rolling "recently asked about"
  summary persisted as memory.

## Integration (backward compatible)
- **Upload** (`_process_csv`) → `remember_from_result` (wrapped in try/except;
  never breaks ingestion).
- **Chat** (`/chat`) → `recall_context` is passed to `converse(..., memory_context=…)`
  and injected into the grounded prompt; after each turn `summarize_conversation`
  updates the rolling summary.
- The copilot prompt gained a "What you remember about this user" section.

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/memory/{user_id}` | all memories grouped by kind |
| POST | `/memory/preference` | `{user_id, key, value}` → save preference |
| POST | `/memory/goal` | `{user_id, name, target_amount?, note?}` → save goal |
| DELETE | `/memory/{user_id}?kind=` | clear all or one kind |

## Frontend (`components/MemoryPanel.tsx`)
Themed glass panel listing what the assistant remembers (salary, subscriptions,
recurring, habits, goals, preferences) with add-preference / add-goal controls
and clear actions. Wired into the dashboard grid. `api.ts` gains `getMemory`,
`addPreference`, `addGoal`, `clearMemory`, and `MemoryByKind`.

## Tests (`backend/tests/test_memory.py`)
Deterministic extraction of salary/recurring/subscription/habits, upsert +
grouped recall, preference & goal persistence, conversation summarisation, and
`recall_context` formatting. Full suite: 57 passing.

## Validation
- `pytest`: 57 passing. `tsc -b`: clean.
- In-process check: a 2-month statement produced salary, a Netflix subscription,
  rent as recurring, and habit facts, all recalled correctly.
