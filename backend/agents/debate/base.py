"""Base specialist agent: LLM-backed with retry, timeout, and a deterministic
fallback so an opinion is always produced (production-safe, never fakes data).
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable

from pydantic import BaseModel, Field, field_validator

from agents import llm_client

logger = logging.getLogger("agents.debate")

# Per-agent LLM guardrails. The router already retries/fails-over internally,
# so a single agent-level attempt with a tight timeout keeps the panel fast
# even when a provider is rate-limited.
DEFAULT_TIMEOUT_S = 12.0
DEFAULT_ATTEMPTS = 1


class AgentOpinion(BaseModel):
    """A single specialist's opinion. Confidence is clamped to [0, 1]."""

    agent: str
    role: str
    icon: str = "🧠"
    stance: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    confidence: float = 0.6
    llm_used: bool = False
    latency_ms: float = 0.0
    retries: int = 0
    error: str | None = None

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, v: float) -> float:
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, v))


# Heuristic returns: (stance, summary, key_points, confidence)
Heuristic = Callable[[dict], tuple[str, str, list[str], float]]


def _safe_generate(
    prompt: str, timeout_s: float, attempts: int
) -> tuple[str | None, int, str | None]:
    """Call the LLM with a hard timeout and bounded retries.

    Returns (text, retries_used, error). ``text`` is None if all attempts fail.
    """
    last_err: str | None = None
    for i in range(attempts):
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(llm_client.generate, prompt)
                text = fut.result(timeout=timeout_s)
            if text and not text.startswith("[LLM error"):
                return text, i, None
            last_err = text or "empty response"
        except FuturesTimeout:
            last_err = f"timeout after {timeout_s}s"
            logger.warning("debate agent LLM timeout (attempt %d)", i + 1)
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            logger.warning("debate agent LLM error (attempt %d): %s", i + 1, exc)
    return None, attempts, last_err


def _parse_json_opinion(text: str) -> tuple[str, str, list[str], float] | None:
    """Best-effort parse of a JSON opinion object from model output."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    stance = str(obj.get("stance", "")).strip()
    summary = str(obj.get("summary", "")).strip()
    kp = obj.get("key_points", [])
    if isinstance(kp, str):
        kp = [kp]
    key_points = [str(x).strip() for x in kp if str(x).strip()][:5]
    conf = obj.get("confidence", 0.6)
    if not stance or not summary:
        return None
    return stance, summary, key_points, conf


class SpecialistAgent:
    """A financial specialist with one focus area.

    Subclasses/instances provide a ``focus`` (used in the prompt) and a
    ``heuristic`` (deterministic fallback grounded in computed numbers).
    """

    def __init__(
        self,
        name: str,
        role: str,
        icon: str,
        focus: str,
        heuristic: Heuristic,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        attempts: int = DEFAULT_ATTEMPTS,
    ) -> None:
        self.name = name
        self.role = role
        self.icon = icon
        self.focus = focus
        self.heuristic = heuristic
        self.timeout_s = timeout_s
        self.attempts = attempts

    # ---- prompt ---------------------------------------------------------- #
    def build_prompt(self, ctx: dict) -> str:
        question = ctx.get("question") or "Give your professional assessment of this user's finances."
        data = json.dumps(ctx.get("data", {}), indent=2, default=str)
        return f"""You are the {self.role} on a financial advisory panel.
Your sole focus: {self.focus}

STRICT RULES:
- Use ONLY the numbers in the data below. Never invent figures.
- Stay strictly within your focus area; ignore concerns owned by other agents.
- Do NOT reveal step-by-step reasoning. Give conclusions only.

User's computed financial data:
{data}

Panel question: {question}

Respond with ONLY a JSON object, no prose, in exactly this shape:
{{"stance": "<3-6 word position>", "summary": "<2-3 sentence assessment grounded in the numbers>", "key_points": ["<short point>", "<short point>"], "confidence": <0.0-1.0>}}"""

    # ---- analysis -------------------------------------------------------- #
    def analyze(self, ctx: dict) -> AgentOpinion:
        start = time.perf_counter()
        f_stance, f_summary, f_points, f_conf = self.heuristic(ctx.get("data", {}))

        # Per-agent LLM enrichment is opt-in (ctx["use_llm"]). By default the
        # panel uses fast, grounded heuristics — running 8 LLM calls per debate
        # is slow and hits provider rate limits. The decider still uses one LLM
        # call to synthesise a natural final recommendation.
        text, retries, err = (None, 0, None)
        if ctx.get("use_llm") and llm_client.is_configured():
            text, retries, err = _safe_generate(
                self.build_prompt(ctx), self.timeout_s, self.attempts
            )

        latency = (time.perf_counter() - start) * 1000

        if text:
            parsed = _parse_json_opinion(text)
            if parsed:
                stance, summary, key_points, conf = parsed
                logger.info("%s opinion via LLM (conf=%.2f)", self.name, conf)
                return AgentOpinion(
                    agent=self.name,
                    role=self.role,
                    icon=self.icon,
                    stance=stance or f_stance,
                    summary=summary,
                    key_points=key_points or f_points,
                    confidence=conf,
                    llm_used=True,
                    latency_ms=latency,
                    retries=retries,
                )
            # Model replied but not as JSON — use its prose, heuristic scaffold.
            logger.info("%s opinion via LLM (unstructured)", self.name)
            return AgentOpinion(
                agent=self.name,
                role=self.role,
                icon=self.icon,
                stance=f_stance,
                summary=text.strip()[:600],
                key_points=f_points,
                confidence=f_conf,
                llm_used=True,
                latency_ms=latency,
                retries=retries,
            )

        # Deterministic fallback (offline / error).
        logger.info("%s opinion via heuristic fallback (%s)", self.name, err or "no LLM")
        return AgentOpinion(
            agent=self.name,
            role=self.role,
            icon=self.icon,
            stance=f_stance,
            summary=f_summary,
            key_points=f_points,
            confidence=f_conf,
            llm_used=False,
            latency_ms=latency,
            retries=retries,
            error=err,
        )
