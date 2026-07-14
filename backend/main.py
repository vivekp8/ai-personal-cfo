"""AI Personal CFO — FastAPI backend.

Wires the deterministic pipeline (Phases 1-2), RAG (Phase 3), explainer/LLM
(Phase 4), what-if simulator (Phase 5), and voice (Phase 6) behind one API.
"""
from __future__ import annotations

import io
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()

import llm  # noqa: E402
from agents import llm_client  # noqa: E402
from agents import twin  # noqa: E402
from agents.copilot import converse  # noqa: E402
from agents.debate import list_agents, run_debate  # noqa: E402
from agents import memory as memory_agent  # noqa: E402
from agents.explainability import SUBJECTS as EXPLAIN_SUBJECTS  # noqa: E402
from agents.explainability import build_explanation  # noqa: E402
from agents import goal_planner  # noqa: E402
from agents.twin import ScenarioInput  # noqa: E402
from agents.explainer import explain  # noqa: E402
from agents.ingestion_agent import IngestionError  # noqa: E402
from agents.whatif import simulate_purchase  # noqa: E402
from db import database  # noqa: E402
from llm import Message  # noqa: E402
from llm.router import router as llm_router  # noqa: E402
from orchestrator.pipeline import run_pipeline, using_langgraph  # noqa: E402
from orchestrator.trace import WORKFLOW_NODES, build_graph  # noqa: E402
from rag import retriever  # noqa: E402
from voice import voice_service  # noqa: E402

app = FastAPI(title="AI Personal CFO", version="1.0.0")

# CORS: restrict origins in production via ALLOWED_ORIGINS (comma-separated).
# Default "*" for local dev. Credentials are only enabled when origins are
# explicitly listed, since "*" + credentials is rejected by browsers and unsafe.
_origins_env = os.getenv("ALLOWED_ORIGINS", "*").strip()
_allow_origins = (
    ["*"] if _origins_env == "*"
    else [o.strip() for o in _origins_env.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_USER = "demo_user"

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
_SAMPLES_DIR = os.path.join(_DATA_DIR, "sample_statements")

# Last workflow trace per user (Phase 7). In-memory so revisiting the dashboard
# shows the real per-node timings without re-persisting/polluting score history.
_LAST_WORKFLOW: dict[str, dict] = {}


@app.on_event("startup")
def _startup() -> None:
    database.init_db()
    # Warm up Whisper + RAG in the background so the first request is fast.
    import threading

    threading.Thread(target=voice_service.preload, daemon=True).start()
    threading.Thread(target=retriever.preload, daemon=True).start()


# ---------- Phase 0 ----------
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/capabilities")
def capabilities() -> dict:
    """Report which optional subsystems are live vs degraded."""
    return {
        "llm_configured": llm_client.is_configured(),
        "llm_providers": llm_router.available_providers(),
        "rag_available": retriever.is_available(),
        "langgraph": using_langgraph(),
        "whisper": voice_service.whisper_available(),
        "gtts": voice_service.gtts_available(),
        "voice": voice_service.capabilities(),
    }


# ---------- LLM router: health, metrics, direct access, streaming ----------
@app.get("/health/llm")
async def health_llm() -> dict:
    """Per-provider health plus the currently active provider."""
    return await llm_router.health_check()


@app.get("/metrics/llm")
def metrics_llm() -> dict:
    """Aggregate LLM usage metrics (latency, tokens, errors, cost, cache)."""
    return llm.metrics.snapshot()


# ---------- Phase 8: Model Routing (monitoring + selection) ----------
_PROVIDER_LABELS = {
    "gemini": "Google Gemini",
    "groq": "Groq",
    "github": "GitHub Models (OpenAI)",
    "openrouter": "OpenRouter (Claude/OpenAI/…)",
    "ollama": "Ollama (local, offline)",
}


@app.get("/router/status")
async def router_status() -> dict:
    """Consolidated view for the model-routing dashboard: per-provider health,
    priority rank, availability, plus aggregate metrics and the active provider.
    """
    health = await llm_router.health_check()
    metrics = llm.metrics.snapshot()
    order = llm_router.all_providers()
    available = set(llm_router.available_providers())
    per = metrics.get("providers", {})

    providers = []
    for rank, name in enumerate(order, start=1):
        pm = per.get(name, {})
        reqs = pm.get("requests", 0) or 0
        avg_latency = (pm.get("total_latency_ms", 0.0) / reqs) if reqs else 0.0
        providers.append({
            "name": name,
            "label": _PROVIDER_LABELS.get(name, name),
            "rank": rank,
            "model": getattr(llm_router._providers[name], "model", ""),
            "status": health.get(name, "not_configured"),
            "available": name in available,
            "offline": name == "ollama",
            "requests": reqs,
            "avg_latency_ms": round(avg_latency, 1),
            "errors": pm.get("errors", 0),
            "total_tokens": pm.get("total_tokens", 0),
            "cost_estimate_usd": pm.get("cost_estimate_usd", 0.0),
        })

    return {
        "providers": providers,
        "preferred": llm_router.preferred(),
        "active_provider": health.get("active_provider", "none"),
        "last_provider": llm_router.last_provider,
        "totals": metrics.get("totals", {}),
        "cache": metrics.get("cache", {}),
    }


class ProviderSelectRequest(BaseModel):
    provider: str = "auto"


@app.post("/router/provider")
def router_set_provider(req: ProviderSelectRequest) -> dict:
    """Set the preferred provider at runtime ('auto' restores the full chain)."""
    try:
        chosen = llm_router.set_preferred(req.provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"preferred": chosen, "selection": llm_router._selection()}


class LLMChatRequest(BaseModel):
    messages: list[dict] = Field(..., description="[{role, content}, ...]")
    temperature: float = 0.7
    max_tokens: int | None = None
    use_cache: bool = True


@app.post("/llm/chat")
async def llm_chat(req: LLMChatRequest) -> dict:
    """Direct router access: returns the first successful provider response."""
    try:
        msgs = [Message(**m) for m in req.messages]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Invalid messages: {exc}") from exc
    try:
        resp = await llm_router.chat(
            msgs,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            use_cache=req.use_cache,
        )
    except llm.ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return resp.model_dump()


@app.post("/llm/stream")
async def llm_stream(req: LLMChatRequest):
    """Stream tokens in real time (text/event-stream) with provider failover."""
    try:
        msgs = [Message(**m) for m in req.messages]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Invalid messages: {exc}") from exc

    async def event_source():
        try:
            async for chunk in llm_router.stream(
                msgs, temperature=req.temperature, max_tokens=req.max_tokens
            ):
                yield f"data: {chunk}\n\n"
        except llm.ProviderError as exc:
            yield f"data: [error] {exc}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


def _serialize(state: dict) -> dict:
    return {
        "user_id": state.get("user_id"),
        "transactions": state.get("categorized", []),
        "monthly_summary": state.get("monthly_summary", {}),
        "anomalies": state.get("anomalies", []),
        "forecast": state.get("forecast", {}),
        "health_score": state.get("health_score", {}),
        "savings_suggestions": state.get("savings_suggestions", []),
    }


_FORMAT_LABELS = {
    "csv": "CSV", "tsv": "TSV", "txt": "Text", "xlsx": "Excel", "xlsm": "Excel",
    "xls": "Excel (legacy)", "ods": "OpenDocument", "json": "JSON", "pdf": "PDF",
}


def _process_csv(content: str | bytes, user_id: str, filename: str | None = None) -> dict:
    from orchestrator.pipeline import run_pipeline_traced
    from orchestrator.trace import WorkflowTracer

    tracer = WorkflowTracer()
    name = (filename or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    size = len(content) if content is not None else 0
    fmt = _FORMAT_LABELS.get(ext, ext.upper() or "auto")
    tracer.record("upload", "ok", 0.0, 0, None, f"{fmt} • {size:,} bytes")

    try:
        state = run_pipeline_traced(content, user_id, filename, tracer)
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc

    result = _serialize(state)

    def _persist() -> dict:
        database.save_transactions(user_id, state.get("categorized", []))
        database.save_result(user_id, result)
        return result

    def _remember() -> int:
        try:
            retriever.index_user_memory(user_id, state)
        except Exception:  # noqa: BLE001
            pass
        try:
            return memory_agent.remember_from_result(user_id, result)
        except Exception:  # noqa: BLE001
            return 0

    tracer.step("persist", _persist, detail_fn=lambda _o: "saved")
    tracer.step(
        "memory", _remember,
        detail_fn=lambda n: f"{n} facts remembered" if isinstance(n, int) else "indexed",
    )

    result["workflow"] = {
        "trace": tracer.as_list(),
        "edges": [{"from": a["id"], "to": b["id"]}
                  for a, b in zip(WORKFLOW_NODES, WORKFLOW_NODES[1:])],
        "langgraph": using_langgraph(),
        "total_ms": tracer.total_ms(),
        "format": fmt,
    }
    _LAST_WORKFLOW[user_id] = result["workflow"]
    return result


# ---------- Phase 1 ----------
_SUPPORTED_EXTS = {"csv", "tsv", "txt", "xlsx", "xlsm", "xls", "ods", "json", "pdf"}


@app.post("/upload")
async def upload(file: UploadFile = File(...), user_id: str = Form(DEFAULT_USER)) -> dict:
    name = (file.filename or "").strip()
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext and ext not in _SUPPORTED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '.{ext}'. Supported: "
                + ", ".join(sorted(_SUPPORTED_EXTS))
                + "."
            ),
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    # Pass raw bytes through; the ingestion layer decodes/decodes per format.
    return _process_csv(raw, user_id, filename=name or "upload.csv")


@app.get("/samples")
def list_samples() -> dict:
    if not os.path.isdir(_SAMPLES_DIR):
        return {"samples": []}
    return {
        "samples": sorted(
            f for f in os.listdir(_SAMPLES_DIR) if f.lower().endswith(".csv")
        )
    }


@app.post("/load-sample")
def load_sample(name: str = Form(...), user_id: str = Form(DEFAULT_USER)) -> dict:
    safe = os.path.basename(name)
    path = os.path.join(_SAMPLES_DIR, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Sample not found: {safe}")
    with open(path, "r", encoding="utf-8-sig") as fh:
        content = fh.read()
    # Pass the sample's filename so the workflow reports the real format.
    return _process_csv(content, user_id, filename=safe)


def _require_result(user_id: str) -> dict:
    result = database.get_result(user_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail="No data yet. Upload a statement first."
        )
    return result


@app.get("/dashboard/{user_id}")
def dashboard(user_id: str) -> dict:
    return _require_result(user_id)


@app.get("/forecast/{user_id}")
def forecast(user_id: str) -> dict:
    return _require_result(user_id).get("forecast", {})


@app.get("/health-score/{user_id}")
def health_score(user_id: str) -> dict:
    return _require_result(user_id).get("health_score", {})


# ---------- Phase 4: chat ----------
class ChatRequest(BaseModel):
    user_id: str = DEFAULT_USER
    query: str


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    """Memory-aware copilot: grounds answers in computed data + RAG + history
    + durable long-term memory (Phase 5)."""
    result = _require_result(req.user_id)
    history = database.get_conversation(req.user_id, limit=20)
    rag = retriever.retrieve(req.query, req.user_id)
    memory_context = memory_agent.recall_context(req.user_id)
    answer = converse(req.query, result, rag, history, memory_context=memory_context)
    # Persist both turns so follow-up questions have context.
    database.save_message(req.user_id, "user", req.query)
    database.save_message(
        req.user_id,
        "assistant",
        answer["response"],
        intent=answer.get("intent"),
        llm_used=answer.get("llm_used"),
    )
    # Keep a rolling durable summary of recent topics.
    try:
        memory_agent.summarize_conversation(
            req.user_id, history + [{"role": "user", "content": req.query}]
        )
    except Exception:  # noqa: BLE001
        pass
    return answer


@app.get("/chat/history/{user_id}")
def chat_history(user_id: str) -> dict:
    """Return the persisted conversation for a user (chronological)."""
    return {"history": database.get_conversation(user_id, limit=200)}


# ---------- Phase 2: multi-agent debate ----------
class DebateRequest(BaseModel):
    user_id: str = DEFAULT_USER
    question: str = ""


@app.post("/debate")
def debate(req: DebateRequest) -> dict:
    """Run the specialist panel over the user's computed financial state."""
    result = _require_result(req.user_id)
    return run_debate(result, req.question)


@app.get("/debate/agents")
def debate_agents() -> dict:
    """List the specialist panel (metadata for the UI)."""
    return {"agents": list_agents()}


# ---------- Phase 4: Explainable AI ----------
# ---------- Phase 9: Goal Planner ----------
@app.get("/goals/types")
def goal_types_endpoint() -> dict:
    """List supported goal presets."""
    return {"types": goal_planner.goal_types()}


class GoalCreateRequest(BaseModel):
    user_id: str = DEFAULT_USER
    name: str
    goal_type: str = "custom"
    target_amount: float
    current_saved: float = 0.0
    target_months: int | None = None
    monthly_contribution: float | None = None


def _plan_for_row(row: dict, surplus: float, ef_months: float) -> dict:
    plan = goal_planner.plan_goal(
        goal_type=row["goal_type"],
        target_amount=row["target_amount"],
        current_saved=row.get("current_saved", 0.0) or 0.0,
        target_months=row.get("target_months"),
        monthly_contribution=row.get("monthly_contribution"),
        monthly_surplus=surplus,
        emergency_fund_months=ef_months,
    )
    return {"id": row.get("id"), "name": row.get("name"), **plan}


@app.post("/goals")
def create_goal(req: GoalCreateRequest) -> dict:
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="name is required.")
    if req.target_amount <= 0:
        raise HTTPException(status_code=422, detail="target_amount must be positive.")

    surplus, ef_months = goal_planner.surplus_from_result(database.get_result(req.user_id))
    goal_id = database.save_goal(
        req.user_id, req.name.strip(), req.goal_type, req.target_amount,
        req.current_saved, req.target_months, req.monthly_contribution,
    )
    # Mirror into long-term memory so the copilot is aware of the goal.
    try:
        memory_agent.add_goal(req.user_id, req.name.strip(), req.target_amount)
    except Exception:  # noqa: BLE001
        pass

    row = {
        "id": goal_id, "name": req.name.strip(), "goal_type": req.goal_type,
        "target_amount": req.target_amount, "current_saved": req.current_saved,
        "target_months": req.target_months, "monthly_contribution": req.monthly_contribution,
    }
    return {"goal": _plan_for_row(row, surplus, ef_months)}


@app.get("/goals/{user_id}")
def list_goals_endpoint(user_id: str) -> dict:
    """Return the user's goals, each with a freshly-computed plan."""
    surplus, ef_months = goal_planner.surplus_from_result(database.get_result(user_id))
    goals = [_plan_for_row(r, surplus, ef_months) for r in database.list_goals(user_id)]
    return {"goals": goals, "monthly_surplus": round(surplus, 2)}


@app.delete("/goals/{goal_id}")
def delete_goal_endpoint(goal_id: int, user_id: str = DEFAULT_USER) -> dict:
    ok = database.delete_goal(goal_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return {"status": "deleted", "id": goal_id}


@app.get("/explain/subjects")
def explain_subjects() -> dict:
    """List the explainable dashboard subjects."""
    return {"subjects": EXPLAIN_SUBJECTS}


class ExplainRequest(BaseModel):
    user_id: str = DEFAULT_USER
    subject: str = "score"


@app.post("/explain")
def explain_endpoint(req: ExplainRequest) -> dict:
    """Return a transparent explanation card for one dashboard figure."""
    result = _require_result(req.user_id)
    return build_explanation(req.subject, result)


# ---------- Phase 6: Retrieval Visualization ----------
class RagTraceRequest(BaseModel):
    user_id: str = DEFAULT_USER
    query: str
    k: int = 4


@app.post("/rag/trace")
def rag_trace(req: RagTraceRequest) -> dict:
    """Return the full RAG retrieval trace for the interactive visualiser."""
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query is required.")
    return retriever.retrieve_trace(req.query.strip(), req.user_id, k=max(1, min(req.k, 10)))


# ---------- Phase 7: Workflow Visualization ----------
@app.get("/workflow/graph")
def workflow_graph() -> dict:
    """Static analysis-graph definition (skeleton for the visualiser)."""
    return {**build_graph(), "supported_formats": sorted(_SUPPORTED_EXTS), "langgraph": using_langgraph()}


@app.get("/workflow/trace/{user_id}")
def workflow_trace(user_id: str) -> dict:
    """Return the workflow trace from the user's last processed upload."""
    cached = _LAST_WORKFLOW.get(user_id)
    if cached:
        return cached
    result = database.get_result(user_id)
    if result and "workflow" in result:
        return result["workflow"]
    # No run yet — return the static graph skeleton so the UI can still render.
    return {
        **build_graph(),
        "trace": None,
        "langgraph": using_langgraph(),
        "supported_formats": sorted(_SUPPORTED_EXTS),
    }


# ---------- Phase 5: Long-Term Memory ----------
@app.get("/memory/{user_id}")
def get_memory(user_id: str) -> dict:
    """Return everything the assistant remembers, grouped by kind."""
    return {"memory": memory_agent.all_memories(user_id)}


class PreferenceRequest(BaseModel):
    user_id: str = DEFAULT_USER
    key: str
    value: str


@app.post("/memory/preference")
def add_preference(req: PreferenceRequest) -> dict:
    if not req.key.strip() or not req.value.strip():
        raise HTTPException(status_code=422, detail="key and value are required.")
    return memory_agent.set_preference(req.user_id, req.key.strip(), req.value.strip())


class GoalRequest(BaseModel):
    user_id: str = DEFAULT_USER
    name: str
    target_amount: float | None = None
    note: str = ""


@app.post("/memory/goal")
def add_goal(req: GoalRequest) -> dict:
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="name is required.")
    return memory_agent.add_goal(req.user_id, req.name.strip(), req.target_amount, req.note.strip())


@app.delete("/memory/{user_id}")
def clear_memory(user_id: str, kind: str | None = None) -> dict:
    """Clear a user's long-term memory (optionally only one kind)."""
    removed = database.delete_memories(user_id, kind)
    return {"status": "cleared", "removed": removed, "kind": kind}


# ---------- Phase 3: Digital Financial Twin ----------
def _build_scenario(user_id: str, overrides: dict) -> ScenarioInput:
    """Merge user-provided overrides onto data-derived defaults."""
    result = _require_result(user_id)
    merged = {**twin.defaults_from_result(result), **(overrides or {})}
    try:
        return ScenarioInput(**merged)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Invalid scenario: {exc}") from exc


class TwinSimulateRequest(BaseModel):
    user_id: str = DEFAULT_USER
    scenario: dict = Field(default_factory=dict)
    save: bool = False
    name: str | None = None


@app.post("/twin/simulate")
def twin_simulate(req: TwinSimulateRequest) -> dict:
    """Project the user's finances forward under one scenario."""
    scenario = _build_scenario(req.user_id, req.scenario)
    if req.name:
        scenario.name = req.name
    result = twin.simulate(scenario)
    payload = result.model_dump()
    saved_id = None
    if req.save:
        saved_id = database.save_simulation(
            req.user_id, scenario.name, scenario.model_dump(), payload
        )
    return {"result": payload, "saved_id": saved_id}


class TwinCompareRequest(BaseModel):
    user_id: str = DEFAULT_USER
    scenarios: list[dict]


@app.post("/twin/compare")
def twin_compare(req: TwinCompareRequest) -> dict:
    """Run several scenarios side by side for comparison."""
    if not req.scenarios:
        raise HTTPException(status_code=422, detail="Provide at least one scenario.")
    results = []
    for overrides in req.scenarios:
        scenario = _build_scenario(req.user_id, overrides)
        results.append(twin.simulate(scenario).model_dump())
    return {"results": results}


@app.get("/twin/scenarios/{user_id}")
def twin_scenarios(user_id: str) -> dict:
    """List a user's saved simulations."""
    return {"scenarios": database.list_simulations(user_id)}


@app.delete("/twin/scenario/{sim_id}")
def twin_delete(sim_id: int, user_id: str = DEFAULT_USER) -> dict:
    ok = database.delete_simulation(sim_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Simulation not found.")
    return {"status": "deleted", "id": sim_id}


@app.delete("/chat/history/{user_id}")
def clear_chat_history(user_id: str) -> dict:
    """Clear a user's conversation memory."""
    removed = database.clear_conversation(user_id)
    return {"status": "cleared", "removed": removed}


# ---------- Phase 5: what-if ----------
class WhatIfRequest(BaseModel):
    user_id: str = DEFAULT_USER
    purchase_amount: float
    tenure_months: int = 12
    current_savings: float | None = None
    explain: bool = True


@app.post("/whatif")
def whatif(req: WhatIfRequest) -> dict:
    result = _require_result(req.user_id)
    sim = simulate_purchase(
        req.purchase_amount,
        result.get("monthly_summary", {}),
        result.get("health_score", {}),
        tenure_months=req.tenure_months,
        current_savings=req.current_savings,
    )
    try:
        retriever.index_whatif(req.user_id, sim)
    except Exception:  # noqa: BLE001
        pass

    explanation = None
    if req.explain:
        query = (
            f"Should I buy something for Rs.{req.purchase_amount:,.0f}? "
            f"Compare paying in full vs EMI over {req.tenure_months} months."
        )
        rag = retriever.retrieve(query, req.user_id)
        result_with_sim = {**result, "whatif_result": sim}
        explanation = explain(query, result_with_sim, rag)

    return {"simulation": sim, "explanation": explanation}


# ---------- Phase 6: voice ----------
@app.post("/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    out = voice_service.transcribe(raw, suffix=suffix)
    if not out["available"]:
        raise HTTPException(status_code=503, detail=out["error"])
    # Log the detected speech so it's visible in the server terminal.
    if out.get("error"):
        print(f"[voice] transcription error: {out['error']}", flush=True)
    else:
        print(f"[voice] detected speech: {out.get('text', '')!r}", flush=True)
    return out


class SpeakRequest(BaseModel):
    text: str


@app.post("/voice/speak")
def voice_speak(req: SpeakRequest):
    audio, error = voice_service.synthesize(req.text)
    if audio is None:
        raise HTTPException(status_code=503, detail=error or "TTS failed")
    return StreamingResponse(io.BytesIO(audio), media_type="audio/mpeg")


@app.get("/voice/config")
def voice_config() -> dict:
    """Voice subsystem capabilities + effective .env configuration (for the UI)."""
    return voice_service.capabilities()


@app.get("/voice/metrics")
def voice_metrics() -> dict:
    """Observability: STT/TTS latency, fallbacks, provider usage, errors."""
    return voice_service.metrics()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
