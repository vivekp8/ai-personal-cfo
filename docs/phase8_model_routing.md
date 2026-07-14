# Phase 8 — Model Routing

Monitoring, selection, and observability for the multi-provider LLM router
(built on the existing routing system — not a second router).

## Priority chain
Gemini → Groq → GitHub Models → OpenRouter → Ollama (offline). Automatic
failover proceeds down the chain; conversation context is preserved because the
full message list is re-sent to the next provider.

## Router capabilities (`llm/router.py`)
- `all_providers()` — every known provider in priority order.
- `available_providers()` — those with credentials/config.
- `preferred()` / `set_preferred(name)` — **runtime** override of the preferred
  provider (validated; unknown → `ValueError`). A runtime override beats the
  `DEFAULT_PROVIDER` env var.
- `_selection()` — preferred first, then the rest as fallback (resilient even
  when forced).
- `health_check()` — concurrent per-provider liveness probe + the active
  provider (first healthy in priority order).

## Metrics / observability (`llm/metrics.py`)
Per provider: requests, successes, errors, avg latency, tokens, and an estimated
cost (`cost_estimate_usd` via a per-1k-token table). Plus totals and cache
hit/miss stats.

## API
- `GET /router/status` — consolidated dashboard payload: each provider with
  rank, model, health status, availability, request count, avg latency, errors,
  tokens, cost estimate; plus preferred, active, last provider, totals, cache.
- `POST /router/provider` `{provider}` — set the preferred provider at runtime
  (`auto` restores the full chain). 422 on unknown provider.

## Frontend (`components/RoutingPanel.tsx`)
Live model-routing dashboard: provider cards with health dot, rank, model,
availability, latency and cost; the active/preferred provider highlighted; and a
selector to force a provider or return to `auto`. `api.ts` gains
`getRouterStatus`, `setRouterProvider`, and the `RouterStatus` type. Wired into
the dashboard grid.

## Tests (`backend/tests/test_routing.py`, 7)
Default preferred is `auto`; `set_preferred` moves a provider first; `auto`/None
restores the chain; unknown provider rejected; runtime override beats env; an
unavailable preferred falls back to the available chain.

## Validation
- `pytest`: full suite green (76 tests). `tsc -b`: clean.
- Live `GET /router/status`: Groq active; providers ranked with health,
  availability, and cost. Live `POST /router/provider`: switching to `groq`
  reorders selection `['groq','github','ollama','openrouter','gemini']`; `auto`
  restores.

## Note on Claude/OpenAI
The generic spec lists Claude/OpenAI. This project's router ships the five
configured providers above; adding Claude/OpenAI is a drop-in new provider class
(implement `BaseProvider`, register in `_PROVIDER_ORDER`) gated by an API key —
no router changes required. Not added here because no keys are configured
(shipping an untested provider would be a stub).
