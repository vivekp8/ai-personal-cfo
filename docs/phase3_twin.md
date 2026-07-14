# Phase 3 — Digital Financial Twin

A deterministic, year-by-year projection engine that turns the user's current
computed state into a future model, then derives retirement and goal outcomes.
Everything is pure math on real numbers — no LLM, no randomness — so results are
reproducible and explainable.

## Projection chain
current state → salary growth → expense growth → inflation → investment growth
→ emergency-fund coverage → retirement estimate → goal-achievement timelines.

## Engine (`agents/twin.py`)
- `ScenarioInput` — validated assumptions (ages, years, monthly income/expenses,
  current savings, salary/expense/inflation/investment rates, goals).
- `simulate(scenario) -> TwinResult`:
  - Monthly-compounded portfolio growth with end-of-month contributions.
  - **Floored at zero** — a portfolio never compounds into fantasy debt when
    expenses exceed income.
  - Nominal **and** inflation-adjusted (real) net worth each year.
  - Emergency-fund months = net worth ÷ current monthly expenses.
- Retirement: projected corpus at `retirement_age`, 4% safe-withdrawal income
  (nominal and real).
- Goals: first year each target is reached (or not), with years-to-reach.
- `defaults_from_result(result)` seeds income/expenses from the dashboard data.

## Persistence (`db/database.py`)
`simulations(id, user_id, name, params, result, created_at)` +
`save_simulation`, `list_simulations`, `get_simulation`, `delete_simulation`.

## API (`main.py`)
- `POST /twin/simulate` `{user_id, scenario, save?, name?}` → `{result, saved_id}`
- `POST /twin/compare` `{user_id, scenarios[]}` → `{results[]}`
- `GET /twin/scenarios/{user_id}` → saved simulations
- `DELETE /twin/scenario/{sim_id}?user_id=` → delete
Scenario overrides are merged onto data-derived defaults; invalid input → 422.

## Frontend
- `components/TwinPanel.tsx` — scenario controls (rates, ages, years, goals),
  run/save/compare, recharts net-worth-over-time visualisation, saved-scenario
  list, theme-consistent glass UI. Wired into the dashboard grid.
- `api.ts` — `simulateTwin`, `compareTwin`, `getSimulations`, `deleteSimulation`
  and the `ScenarioInput` / `TwinResult` / `SavedSimulation` types.

## Tests (`backend/tests/test_twin.py`, 10)
Projection shape, monotonic growth with positive savings, real < nominal,
negative-savings floor at zero, retirement math (4% rule), retirement
not-applicable without ages, goal timelines (reached/unreached), defaults, input
validation, and simulation persistence (save/list/get/delete).

## Validation
- `pytest`: full suite green (32 tests).
- `tsc -b`: frontend compiles clean.
- Live `POST /twin/simulate`: 25-year projection, retirement + goal outcomes.
