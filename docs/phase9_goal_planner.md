# Phase 9 — Goal Planner

Create financial goals and get an auto-computed plan: timeline, required monthly
saving, risk band, completion probability, and a month-by-month trajectory. All
math is deterministic and reproducible.

## Goal types
Emergency Fund · Vacation · Car · Wedding · Education · House · Retirement ·
Custom — each with a sensible default horizon and an assumed return for the
money set aside (short goals in cash, long goals invested).

## Engine (`agents/goal_planner.py`)
- `plan_goal(...)` computes, given a target + the user's monthly surplus:
  - **Fixed-timeline mode** (`target_months` given): the required monthly
    contribution via the future-value-of-annuity formula (accounting for growth
    on money already saved), and a completion probability from
    `surplus / required`.
  - **Auto-timeline mode** (no target date): simulates month-by-month with
    compounding to find when the target is reached (capped at 50 years →
    `reachable=false` if never).
  - **Completion probability** — a transparent ratio-based proxy, reduced when
    the emergency fund is < 3 months (non-emergency goals).
  - **Risk band** — Low / Medium / High from probability + emergency-fund depth.
  - **Trajectory** — down-sampled cumulative-balance series for the chart.
- `surplus_from_result(result)` derives monthly surplus + emergency-fund months
  from the computed dashboard data.

## Persistence (`db/database.py`)
`financial_goals(id, user_id, name, goal_type, target_amount, current_saved,
target_months, monthly_contribution, created_at)` + `save_goal`, `list_goals`,
`delete_goal`. Goals are also mirrored into long-term memory so the copilot
knows about them.

## API
- `GET /goals/types` → presets
- `POST /goals` `{user_id, name, goal_type, target_amount, current_saved?,
  target_months?, monthly_contribution?}` → the goal with its computed plan
- `GET /goals/{user_id}` → all goals, each re-planned against the latest surplus,
  plus `monthly_surplus`
- `DELETE /goals/{goal_id}?user_id=` → remove

## Frontend (`components/GoalPlannerPanel.tsx`)
Create form (type, name, target, saved, months), and per-goal cards with a 3D
tilt, animated progress bar, a completion-probability gauge, a Recharts
trajectory sparkline, and timeline / need-per-month / risk stats. Added to the
dashboard grid. `api.ts` gains `getGoalTypes`, `getGoals`, `createGoal`,
`deleteGoal` + types.

## Tests (`backend/tests/test_goal_planner.py`, 10)
Presets present; fixed-timeline required-monthly + high odds; underfunded → low
odds/high risk; auto-timeline from surplus; unreachable with no contribution;
progress %; emergency-fund fragility penalty; already-reached; surplus
extraction; and goal persistence (save/list/delete).

## Validation
- `pytest`: full suite green (86 tests). `tsc -b`: clean.
- Live: emergency-fund goal (₹13,477/mo, 99%, Low) and an auto-timeline house
  goal (85 months, reachable, 84%) computed against a ₹46,025 surplus.
