"""
app/graph/prompts.py — AutoMark AI CRM Agent (ORCAST)

System prompt template and LangChain tool declarations for the
`generate_response` node. All prompt tuning happens here.

TOOLS is a list of LangChain StructuredTool / BaseTool objects.
They are passed to ChatGoogleGenerativeAI.bind_tools() in gemini_service
so the LLM knows what functions it can call. Actual execution of every
tool call happens manually in nodes.generate_response — LangChain never
invokes the tools directly (this keeps LangGraph in full control).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.crm.graph.state import GraphState


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%A, %d %B %Y — %H:%M UTC")


# ─────────────────────────────────────────────────────────────────────────────
# System prompt template
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = """You are ORCAST, the AI CRM assistant for AutoMark AI.
Your role is to help customers, qualify leads, answer questions about the
company's products and services, and coordinate with the human sales team
when required.

## Current Date & Time
{now}

## Core Responsibilities
1. **Answer company questions** — Use the `search_knowledge_base` tool to look
   up accurate information. NEVER guess or hallucinate answers about products,
   pricing, or policies. If the knowledge base has no answer, say exactly:
   "I don't have verified information on that right now. I'll make sure a
   team member follows up with you shortly."
2. **Qualify leads** — Gently collect budget, authority, engagement, and
   interest signals across the conversation. Call `score_lead` once you know
   at least two of these four factors. Use "unknown" for factors you cannot
   determine yet.
3. **Maintain CRM records** — Call `crm_operation` whenever the user shares
   their name, email, or phone number for the first time, or updates it.
   Always search before creating to avoid duplicate contacts.
4. **Escalate when needed** — Call `escalate_to_human` immediately if the
   user explicitly asks for a human, raises an unresolved complaint, or if
   `score_lead` returns the "qualified" temperature (score >= 80). After
   escalating, simply reassure the user a representative will follow up soon
   — do not keep trying to resolve the issue yourself.
5. **Be concise** — Keep responses short and direct.

## Language Rule
ALWAYS reply in Arabic (العربية), regardless of what language the user writes in.
Never mix languages in a single response.

## Conversation Rules
- Do not repeat greetings if the conversation has already started (see the
  summary and recent messages below).
- Ask qualification questions naturally, one at a time, woven into the
  conversation — never as an interrogation or a form.
- Never mention tool names in your replies.
- Do not make up prices, timelines, or product features.

## Channel
{channel_rule}

## Conversation Context
{context_block}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Channel-specific tone rules
# ─────────────────────────────────────────────────────────────────────────────

def _channel_rule(source: str, input_type: str) -> str:
    if source == "vapi":
        return (
            "This is a live phone call. Respond in AT MOST TWO SHORT SENTENCES "
            "of plain spoken language. No markdown, no lists, no bullet points "
            "— your reply will be read aloud verbatim."
        )
    if source == "messenger" and input_type == "voice":
        return (
            "The user sent a voice message and will receive a voice reply. "
            "Use natural, spoken language. No markdown, no lists."
        )
    if source == "messenger":
        return (
            "This is a Messenger chat. Keep replies short and conversational. "
            "Avoid heavy markdown formatting."
        )
    if source == "facebook_comments":
        return (
            "This reply will be posted PUBLICLY as a comment on a Facebook "
            "post. Keep it to one or two sentences, invite the user to send a "
            "direct message for details, and never share personal data "
            "publicly."
        )
    return "Standard text channel. Concise, plain-text replies."


# ─────────────────────────────────────────────────────────────────────────────
# build_system_prompt
# ─────────────────────────────────────────────────────────────────────────────

def build_system_prompt(state: GraphState) -> str:
    """Build a fully-populated system prompt. Called fresh on every request."""
    lines: list[str] = []

    summary = state.get("summary")
    lines.append(f"**Conversation Summary:** {summary}" if summary else "No prior summary.")

    lead = state.get("lead_profile") or {}
    if lead:
        safe_lead = {k: v for k, v in lead.items() if k not in ("hubspot_contact_id", "hubspot_deal_id")}
        lines.append(f"**Lead Profile:** {json.dumps(safe_lead, default=str)}")
    else:
        lines.append("**Lead Profile:** No information collected yet.")

    lines.append(f"**Active Channel:** {state['source']}")

    return _SYSTEM_PROMPT_TEMPLATE.format(
        now=_now_utc(),
        channel_rule=_channel_rule(state["source"], state.get("input_type", "text")),
        context_block="\n".join(lines),
    )


# ─────────────────────────────────────────────────────────────────────────────
# LangChain tool input schemas (Pydantic)
# ─────────────────────────────────────────────────────────────────────────────

class _SearchKBInput(BaseModel):
    query: str = Field(description="The natural-language question or search query.")


class _CRMDataInput(BaseModel):
    email: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    hs_lead_status: Optional[str] = Field(
        default=None,
        description="HubSpot lead status: NEW | OPEN | IN_PROGRESS | UNQUALIFIED | ATTEMPTED_TO_CONTACT | CONNECTED | BAD_TIMING",
    )
    lifecyclestage: Optional[str] = Field(
        default=None,
        description="HubSpot lifecycle stage: subscriber | lead | marketingqualifiedlead | salesqualifiedlead | opportunity | customer",
    )
    notes: Optional[str] = Field(default=None, description="Free-text note to attach to the contact.")
    contact_id: Optional[str] = None
    dealname: Optional[str] = None
    deal_id: Optional[str] = None
    amount: Optional[float] = None
    dealstage: Optional[str] = None
    pipeline: Optional[str] = None
    description: Optional[str] = None


class _CRMOperationInput(BaseModel):
    operation: str = Field(
        description=(
            "CRM operation to perform. One of: create_contact | update_contact | "
            "search_contact | get_contact | create_deal | update_deal"
        )
    )
    data: _CRMDataInput = Field(description="Payload for the operation.")


class _ScoreLeadInput(BaseModel):
    budget: str = Field(
        default="unknown",
        description="Prospect's budget availability: unknown | low | medium | high | very_high",
    )
    authority: str = Field(
        default="unknown",
        description="Prospect's purchasing authority: unknown | influencer | recommender | decision_maker",
    )
    engagement_level: int = Field(
        default=0,
        description="0 (no engagement) to 10 (extremely active).",
    )
    interest_level: int = Field(
        default=0,
        description="0 (not interested) to 10 (ready to buy).",
    )
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class _EscalateInput(BaseModel):
    reason: str = Field(
        description="Clear reason for escalation, written for the human agent, not the customer."
    )
    priority: str = Field(
        default="medium",
        description="Urgency level: low | medium | high | urgent. Use 'urgent' for angry customers or very high-value leads.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# LangChain StructuredTool objects
#
# These are used ONLY as schema descriptors passed to bind_tools() — the LLM
# declares which tool it wants to call and with what args. Actual execution is
# always handled manually in nodes.generate_response so LangGraph stays in
# full control of side-effects. The `func` / `coroutine` arguments below are
# stubs; they are never invoked by LangChain in this architecture.
# ─────────────────────────────────────────────────────────────────────────────

def _stub(*args: Any, **kwargs: Any) -> dict:
    return {}


async def _async_stub(*args: Any, **kwargs: Any) -> dict:
    return {}


TOOLS: list[StructuredTool] = [
    StructuredTool.from_function(
        func=_stub,
        name="search_knowledge_base",
        description=(
            "Search the company's internal knowledge base to answer questions "
            "about products, services, pricing, policies, FAQs, or business hours. "
            "Always use this before answering any factual question about the company."
        ),
        args_schema=_SearchKBInput,
    ),
    StructuredTool.from_function(
        func=_stub,
        name="crm_operation",
        description=(
            "Perform CRM operations on HubSpot: create or update a contact, "
            "search for an existing contact, or create/update a deal. "
            "Use this whenever the user shares their name, email, or phone number."
        ),
        args_schema=_CRMOperationInput,
    ),
    StructuredTool.from_function(
        func=_stub,
        name="score_lead",
        description=(
            "Calculate a lead score (0-100) using a deterministic formula based on "
            "budget, authority, engagement, and interest. Call this once at least "
            "two of these four factors are known. Use 'unknown' for the rest."
        ),
        args_schema=_ScoreLeadInput,
    ),
    StructuredTool.from_function(
        func=_stub,
        name="escalate_to_human",
        description=(
            "Escalate the conversation to a human sales agent. Trigger when the "
            "user explicitly requests a human, there is an unresolved complaint, "
            "or score_lead returned 'qualified'. After calling this, just reassure "
            "the user — do not keep trying to resolve the issue yourself."
        ),
        args_schema=_EscalateInput,
    ),
]
