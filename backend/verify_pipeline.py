"""Quick manual verification of the deterministic pipeline against the sample."""
import json
import os

from orchestrator.pipeline import run_pipeline, using_langgraph

here = os.path.dirname(os.path.abspath(__file__))
sample = os.path.join(here, "..", "data", "sample_statements", "sample_1.csv")
with open(sample, "r", encoding="utf-8-sig") as fh:
    content = fh.read()

state = run_pipeline(content, "demo_user")
print("LangGraph active:", using_langgraph())
print("num transactions:", len(state["transactions"]))
print("months:", state["monthly_summary"]["months"])
print("monthly_income:", state["monthly_summary"]["monthly_income"])
print("monthly_expenses:", state["monthly_summary"]["monthly_expenses"])
print("category_totals:", json.dumps(state["monthly_summary"]["category_totals"], indent=2))
print("num anomalies:", len(state["anomalies"]))
for a in state["anomalies"]:
    print("  -", a["type"], a.get("month", a.get("date")), a["category"], a["amount"])
print("forecast:", json.dumps(state["forecast"], indent=2))
print("health_score:", json.dumps(state["health_score"], indent=2))
print("savings:", json.dumps(state["savings_suggestions"], indent=2))
