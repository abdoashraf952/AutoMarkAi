"""
app/graph/state.py — AutoMark AI CRM Agent (ORCAST)

LangGraph state and the public response model returned by run_graph().
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GraphState(TypedDict, total=False):
    """Shared state threaded through every ORCAST graph node."""

    # ── Inbound message ──────────────────────────────────────────────────
    user_id: str
    source: str
    input_type: str
    user_message: str
    metadata: dict[str, Any]

    # ── Memory (populated by memory_load) ───────────────────────────────
    status: str
    summary: Optional[str]
    recent_messages: list[dict[str, Any]]
    lead_profile: dict[str, Any]

    # ── Routing (populated by intent_classify) ──────────────────────────
    intent: str
    intent_data: dict[str, Any]

    # ── Tool execution ────────────────────────────────────────────────────
    tool_results: list[dict[str, Any]]
    tools_called: list[str]

    # ── Output ────────────────────────────────────────────────────────────
    response: str
    escalated: bool
    lead_updated: bool


class AgentResponse(BaseModel):
    """Final structured response returned by run_graph()."""

    user_id: str
    source: str
    message: str
    tools_called: list[str] = Field(default_factory=list)
    lead_updated: bool = False
    escalated: bool = False
    timestamp: datetime = Field(default_factory=_utcnow)
