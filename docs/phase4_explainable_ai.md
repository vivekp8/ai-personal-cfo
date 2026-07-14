# Phase 4 — Explainable AI Dashboard

Every AI-surfaced figure can be explained with eight transparent facets — and
never exposes chain-of-thought.

## The eight facets
Why · Evidence · Confidence · Retrieved Documents · Transactions Used ·
Formula Used · Model Used · Reasoning Summary.

## Subjects
`score` · `savings` · `forecast` · `anomaly` · `spending`.

## Engine (`agents/explainability.py`)
`build_explanation(subject, result) -> card`:
- **Deterministic & grounded** — all numbers come from the computed dashboard
  result; nothing is invented.
- **Formula transparency** — reproduces the exact health-score deductions
  (base 100 − savings penalty − min(anomalies×10,30) − emergency penalty −
  min(EMIs×5,15)), the savings-rate formula, the LinearRegression forecast, the
  anomaly rule, and category-sum spending.
- **Confidence** — deterministic figures score ~0.95–0.97; the forecast scales
  with months of history (naive average when < 2 months → low).
- **Transactions Used** — the actual rows behind the figure (reference-month
  transactions for score/savings, the flagged rows for anomalies, top outflows
  for spending).
- **Retrieved Documents** — best-effort RAG sources (empty if RAG unavailable).
- **Model Used** — names the deterministic engine plus the active narration
  provider, making the human/AI split explicit.
- **Reasoning Summary** — a short *conclusion*, explicitly not step-by-step CoT.

## API
- `GET /explain/subjects` → `{subjects: [...]}`
- `POST /explain` `{user_id, subject}` → the explanation card

## Frontend (`components/ExplainabilityPanel.tsx`)
Themed glass panel with a subject selector, a headline "why" + circular
confidence gauge, and a 3D-reveal grid of facets: Evidence (mono), Formula +
reasoning, Transactions Used (mini ledger), Retrieved Documents, and a Model
footer. Added to the dashboard grid; existing panels untouched (backward
compatible). `api.ts` gains `explainSubject` + `ExplanationCard`.

## Tests (`backend/tests/test_explainability.py`, 7)
Full-card shape for every subject, score breakdown matches the formula,
reference-month transaction selection, forecast confidence scales with history,
spending top-category, unknown-subject defaults to score, and a no-CoT-leak
guard. Full suite: 49 passing.

## Validation
- `pytest`: 49 passing. `tsc -b`: clean.
- Verified live-in-process for all 5 subjects with accurate formulas, evidence,
  confidence, transactions, and model attribution.
