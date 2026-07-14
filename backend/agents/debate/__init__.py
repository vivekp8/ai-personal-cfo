"""Phase 2 — Multi-Agent Debate System.

Eight specialist agents analyse the user's computed financial state, each with
an isolated responsibility, a confidence score, logged reasoning, retry and
timeout handling. A Final Decision Agent synthesises their opinions into one
prioritised recommendation. State is shared through LangGraph when available.
"""
from __future__ import annotations

from .base import AgentOpinion, SpecialistAgent
from .graph import run_debate, list_agents

__all__ = ["AgentOpinion", "SpecialistAgent", "run_debate", "list_agents"]
