"""Phase 5 — Long-Term Memory.

Persists durable financial facts about the user so the assistant "remembers"
across sessions: spending habits, recurring expenses, subscriptions, salary
history, goals, preferences, and conversation summaries.

Source of truth is SQLite (listable, reliable); each item is also embedded in
ChromaDB (via the retriever) for semantic recall. Extraction from a processed
statement is fully deterministic — no invented facts.
"""
from __future__ import annotations

import logging
import re
import statistics
import threading
from collections import defaultdict

from db import database
from rag import retriever

logger = logging.getLogger("agents.memory")

KINDS = [
    "habit",
    "recurring",
    "subscription",
    "salary",
    "goal",
    "preference",
    "conversation_summary",
]

_SUBSCRIPTION_HINTS = (
    "netflix", "spotify", "prime", "hotstar", "disney", "youtube", "sony liv",
    "zee5", "gym", "fitness", "apple", "icloud", "google", "adobe", "canva",
    "membership", "subscription", "audible", "kindle", "linkedin", "coursera",
)


def _inr(n) -> str:
    try:
        return f"Rs.{abs(float(n)):,.0f}"
    except (TypeError, ValueError):
        return "Rs.0"


def _normalize_desc(desc: str) -> str:
    """Collapse a transaction description to a stable merchant key."""
    s = (desc or "").lower()
    s = re.sub(r"\b(upi|neft|imps|ach|pos|ref|txn|id|no)\b", " ", s)
    s = re.sub(r"[0-9]+", " ", s)          # strip reference numbers
    s = re.sub(r"[^a-z ]+", " ", s)         # strip punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s[:40]


# --------------------------------------------------------------------------- #
# Extraction (deterministic)
# --------------------------------------------------------------------------- #
def extract_memories(result: dict) -> list[dict]:
    """Derive durable memory items from a processed statement result."""
    txns = result.get("transactions", []) or []
    summary = result.get("monthly_summary", {}) or {}
    hs = result.get("health_score", {}) or {}
    items: list[dict] = []

    # ---- salary history (from monthly income) ----
    monthly_income = summary.get("monthly_income", {}) or {}
    for month, income in sorted(monthly_income.items()):
        if income and income > 0:
            items.append({
                "kind": "salary",
                "mem_key": f"salary_{month}",
                "content": f"Income in {month} was {_inr(income)}.",
                "data": {"month": month, "income": round(float(income), 2)},
            })

    # ---- recurring expenses & subscriptions ----
    groups: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
    for t in txns:
        amt = float(t.get("amount", 0) or 0)
        if amt >= 0:
            continue  # expenses only
        month = str(t.get("date", ""))[:7]
        key = _normalize_desc(t.get("description", ""))
        if key:
            groups[key].append((month, abs(amt), t.get("description", "")))

    for key, occ in groups.items():
        months = {m for m, _, _ in occ}
        if len(months) < 2:
            continue  # must repeat across months to be "recurring"
        amounts = [a for _, a, _ in occ]
        avg = round(statistics.mean(amounts), 2)
        label = max((d for _, _, d in occ), key=len).strip()[:48]
        is_sub = any(h in key for h in _SUBSCRIPTION_HINTS)
        kind = "subscription" if is_sub else "recurring"
        prefix = "Subscription" if is_sub else "Recurring payment"
        items.append({
            "kind": kind,
            "mem_key": f"{kind}_{key}",
            "content": f"{prefix}: '{label}' ~{_inr(avg)}/mo across {len(months)} months.",
            "data": {
                "merchant": label, "avg_amount": avg,
                "months": sorted(months), "occurrences": len(occ),
            },
        })

    # ---- habits ----
    totals = summary.get("category_totals", {}) or {}
    spend = sorted(((k, abs(v)) for k, v in totals.items() if v and v < 0),
                   key=lambda x: x[1], reverse=True)
    if not spend:
        spend = sorted(((k, abs(v)) for k, v in totals.items() if v),
                       key=lambda x: x[1], reverse=True)
    if spend:
        top_cat, top_val = spend[0]
        items.append({
            "kind": "habit", "mem_key": "habit_top_category",
            "content": f"Biggest spending category is {top_cat} ({_inr(top_val)} total).",
            "data": {"category": top_cat, "total": top_val},
        })
    if hs:
        rate = float(hs.get("savings_rate", 0) or 0)
        items.append({
            "kind": "habit", "mem_key": "habit_savings_rate",
            "content": f"Typical savings rate is {rate:.0%} (health score {hs.get('score')}).",
            "data": {"savings_rate": rate, "score": hs.get("score")},
        })

    return items


# --------------------------------------------------------------------------- #
# Store / recall orchestration
# --------------------------------------------------------------------------- #
def _embed(user_id: str, items: list[dict]) -> None:
    """Embed memory items into ChromaDB for semantic recall.

    Runs in a background thread so a cold embedding-model load never blocks the
    API response — the SQLite write is already the source of truth.
    """
    if not items:
        return

    def _work() -> None:
        try:
            retriever.index_memory_items(
                user_id,
                [{"id": it["mem_key"], "text": it["content"], "kind": it["kind"]} for it in items],
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("memory embedding skipped: %s", exc)

    threading.Thread(target=_work, daemon=True).start()


# Kinds that are re-derived from the statement on every upload. These are
# pruned to the latest extraction so stale facts (e.g. subscriptions from a
# previously-loaded sample) never linger. User-authored kinds (goal,
# preference) and conversation summaries are intentionally excluded.
_DERIVED_KINDS = ["salary", "subscription", "recurring", "habit"]


def remember_from_result(user_id: str, result: dict) -> int:
    """Extract and persist durable memories after a statement is processed.

    Auto-derived memories are reconciled against the fresh extraction: anything
    no longer detected (e.g. a subscription that isn't in the new data) is
    removed, so the panel never shows stale/demo facts.
    """
    items = extract_memories(result)
    for it in items:
        database.upsert_memory(user_id, it["kind"], it["mem_key"], it["content"], it["data"])

    # Drop stale auto-derived memories that weren't in this extraction.
    fresh_keys = [it["mem_key"] for it in items if it["kind"] in _DERIVED_KINDS]
    removed = database.prune_memories(user_id, _DERIVED_KINDS, fresh_keys)
    if removed:
        logger.info("pruned %d stale long-term memories for user=%s", removed, user_id)

    _embed(user_id, items)
    logger.info("stored %d long-term memories for user=%s", len(items), user_id)
    return len(items)


def reconcile_derived(user_id: str) -> int:
    """Prune auto-derived memories not supported by the user's current statement.

    Guards against stale/demo facts lingering when the active data no longer
    contains them — e.g. subscriptions from a previously-loaded sample that the
    user's real statement doesn't have. Called on read (memory panel fetch) so
    the panel always reflects the current data, even if an upload-time prune was
    missed. No-op when there is no processed result yet (nothing to reconcile
    against), so we never wipe memories just because data hasn't loaded.
    Returns rows removed.
    """
    result = database.get_result(user_id)
    if not result:
        return 0
    items = extract_memories(result)
    fresh_keys = [it["mem_key"] for it in items if it["kind"] in _DERIVED_KINDS]
    removed = database.prune_memories(user_id, _DERIVED_KINDS, fresh_keys)
    if removed:
        logger.info("reconciled %d stale long-term memories for user=%s", removed, user_id)
    return removed


def set_preference(user_id: str, key: str, value: str) -> dict:
    content = f"Preference — {key}: {value}"
    database.upsert_memory(user_id, "preference", f"pref_{key}", content, {"key": key, "value": value})
    _embed(user_id, [{"kind": "preference", "mem_key": f"pref_{key}", "content": content}])
    return {"kind": "preference", "key": key, "value": value}


def add_goal(user_id: str, name: str, target_amount: float | None = None, note: str = "") -> dict:
    parts = [f"Goal: {name}"]
    if target_amount:
        parts.append(f"target {_inr(target_amount)}")
    if note:
        parts.append(note)
    content = " — ".join(parts)
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "goal"
    database.upsert_memory(
        user_id, "goal", f"goal_{key}", content,
        {"name": name, "target_amount": target_amount, "note": note},
    )
    _embed(user_id, [{"kind": "goal", "mem_key": f"goal_{key}", "content": content}])
    return {"kind": "goal", "name": name, "target_amount": target_amount, "note": note}


def summarize_conversation(user_id: str, history: list[dict], max_turns: int = 12) -> str | None:
    """Persist a compact summary of recent conversation as long-term memory."""
    user_msgs = [m.get("content", "") for m in history if m.get("role") == "user"]
    if not user_msgs:
        return None
    recent = [m.strip() for m in user_msgs[-max_turns:] if m.strip()]
    if not recent:
        return None
    summary = "Recently asked about: " + "; ".join(recent[-5:])
    database.upsert_memory(
        user_id, "conversation_summary", "recent_topics", summary,
        {"turns": len(recent)},
    )
    _embed(user_id, [{"kind": "conversation_summary", "mem_key": "recent_topics", "content": summary}])
    return summary


def recall_context(user_id: str, max_items: int = 12) -> str:
    """Build a compact durable-memory string to inject into the copilot prompt."""
    mems = database.get_memories(user_id)
    if not mems:
        return ""
    # Prioritise the most decision-relevant kinds.
    priority = {"preference": 0, "goal": 1, "subscription": 2, "habit": 3,
                "recurring": 4, "salary": 5, "conversation_summary": 6}
    mems.sort(key=lambda m: priority.get(m["kind"], 9))
    lines = [f"- ({m['kind']}) {m['content']}" for m in mems[:max_items]]
    return "\n".join(lines)


def all_memories(user_id: str) -> dict:
    """Return memories grouped by kind for the API/UI."""
    grouped: dict[str, list[dict]] = {k: [] for k in KINDS}
    for m in database.get_memories(user_id):
        grouped.setdefault(m["kind"], []).append(m)
    return grouped
