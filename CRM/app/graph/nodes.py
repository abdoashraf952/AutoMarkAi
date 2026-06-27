"""
app/graph/nodes.py — AutoMark AI CRM Agent (ORCAST)

LangGraph node implementations for the ORCAST agent.

LangChain is used for:
  - intent_classify  : ChatGoogleGenerativeAI.with_structured_output() replaces
                       manual JSON generation + _parse_json() parsing.
  - generate_response: ChatGoogleGenerativeAI.bind_tools() (via gemini_service)
                       replaces raw genai function-call parsing.

LangGraph wires these nodes into a deterministic StateGraph — nothing here
changes that topology or the tool execution logic.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

import structlog
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import traceable
from pydantic import BaseModel, Field

from config import settings
from app.graph.prompts import TOOLS, build_system_prompt
from app.graph.state import GraphState
from app.memory.postgres_memory import postgres_memory
from app.services.gemini_service import gemini_service
from app.tools.handoff_tool import escalate_to_human
from app.tools.hubspot_tool import crm_operation
from app.tools.lead_scoring_tool import score_lead
from app.tools.rag_tool import search_knowledge_base

logger = structlog.get_logger(__name__)

ALREADY_ESCALATED_MESSAGE = (
    "Your conversation has already been escalated to our team. "
    "A representative will follow up with you shortly."
)

VALID_INTENTS = {
    "crm_request",
    "knowledge_question",
    "lead_qualification",
    "escalation",
    "general_conversation",
}


# ─────────────────────────────────────────────────────────────────────────────
# Structured output schema for intent_classify
# ─────────────────────────────────────────────────────────────────────────────

class _IntentOutput(BaseModel):
    """Schema for ChatGoogleGenerativeAI.with_structured_output() in intent_classify."""

    intent: Literal[
        "crm_request",
        "knowledge_question",
        "lead_qualification",
        "escalation",
        "general_conversation",
    ] = Field(description="The intent of the customer's latest message.")
    rag_query: str = Field(
        default="",
        description="Question to search the knowledge base, or empty string.",
    )
    crm_data: dict = Field(
        default_factory=dict,
        description="Extracted contact data: email, firstname, lastname, phone, company.",
    )
    lead_signals: dict = Field(
        default_factory=dict,
        description="Lead qualification signals: budget, authority, engagement_level, interest_level.",
    )
    escalation_reason: str = Field(
        default="",
        description="Reason for escalation (for the human agent), or empty string.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_context_text(state: GraphState, tool_results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for m in state.get("recent_messages", []):
        lines.append(f"{m['role']}: {m['content']}")
    for tr in tool_results:
        lines.append(f"[Tool result — {tr['tool']}]: {json.dumps(tr['result'], default=str)}")
    lines.append(f"user: {state['user_message']}")
    return "\n".join(lines)


def _flatten_crm_data(raw: Any) -> dict:
    """Normalise crm_operation data arg — handles both dict and nested Pydantic model."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if v is not None}
    # Pydantic model (from with_structured_output or StructuredTool)
    if hasattr(raw, "model_dump"):
        return {k: v for k, v in raw.model_dump().items() if v is not None}
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# memory_load
# ─────────────────────────────────────────────────────────────────────────────

async def memory_load(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    memory = await postgres_memory.load(state["user_id"], source=state["source"])
    return {
        **state,
        "status": memory["status"],
        "summary": memory["summary"],
        "recent_messages": memory["recent_messages"],
        "lead_profile": memory["lead"],
        "tool_results": [],
        "tools_called": [],
        "escalated": False,
        "lead_updated": False,
    }


def route_after_memory(state: GraphState) -> str:
    if state.get("status") == "escalated":
        return "already_escalated"
    return "intent_classify"


@traceable(name="already_escalated")
async def already_escalated(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    logger.info("graph.already_escalated", user_id=state["user_id"])
    return {**state, "response": ALREADY_ESCALATED_MESSAGE, "escalated": True}


# ─────────────────────────────────────────────────────────────────────────────
# intent_classify  — LangChain with_structured_output
# ─────────────────────────────────────────────────────────────────────────────

_INTENT_PROMPT = """Classify the latest customer message into exactly ONE intent
and extract any structured data needed to act on it.

Intent definitions:
- "crm_request": the user shared contact info (name/email/phone) worth saving to the CRM.
- "knowledge_question": the user is asking about products, pricing, policies, or company info.
- "lead_qualification": the message reveals budget, authority, engagement, or interest signals.
- "escalation": the user explicitly asks for a human, or is frustrated/complaining.
- "general_conversation": none of the above (greetings, small talk, unclear).

## Conversation Summary
{summary}

## Lead Profile
{lead_profile}

## Latest Customer Message
{message}"""


@traceable(name="intent_classify")
async def intent_classify(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    prompt = _INTENT_PROMPT.format(
        summary=state.get("summary") or "(none)",
        lead_profile=json.dumps(state.get("lead_profile") or {}, default=str),
        message=state["user_message"],
    )

    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        temperature=0.0,
        google_api_key=settings.GEMINI_API_KEY,
    )
    structured = llm.with_structured_output(_IntentOutput)

    try:
        result: _IntentOutput = await structured.ainvoke([HumanMessage(content=prompt)])
        intent = result.intent if result.intent in VALID_INTENTS else "general_conversation"
        parsed = {
            "intent": intent,
            "rag_query": result.rag_query,
            "crm_data": result.crm_data,
            "lead_signals": result.lead_signals,
            "escalation_reason": result.escalation_reason,
        }
    except Exception as exc:
        logger.warning("graph.intent_classify.error", user_id=state["user_id"], error=str(exc))
        intent = "general_conversation"
        parsed = {"intent": intent}

    logger.info("graph.intent_classified", user_id=state["user_id"], intent=intent)
    return {**state, "intent": intent, "intent_data": parsed}


def route_by_intent(state: GraphState) -> str:
    return {
        "crm_request": "hubspot_node",
        "knowledge_question": "rag_node",
        "lead_qualification": "lead_scoring_node",
        "escalation": "handoff_node",
        "general_conversation": "generate_response",
    }.get(state["intent"], "generate_response")


# ─────────────────────────────────────────────────────────────────────────────
# hubspot_node
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="hubspot_node")
async def hubspot_node(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    lead = state.get("lead_profile") or {}
    crm_data = {k: v for k, v in (state.get("intent_data", {}).get("crm_data") or {}).items() if v}

    if lead.get("name") and "firstname" not in crm_data and "lastname" not in crm_data:
        parts = lead["name"].split(" ", 1)
        crm_data["firstname"] = parts[0]
        if len(parts) > 1:
            crm_data["lastname"] = parts[1]
    crm_data.setdefault("email", lead.get("email"))
    crm_data.setdefault("phone", lead.get("phone"))
    crm_data = {k: v for k, v in crm_data.items() if v}

    if not crm_data:
        return state

    if lead.get("hubspot_contact_id"):
        operation = "update_contact"
        crm_data["contact_id"] = lead["hubspot_contact_id"]
    else:
        operation = "create_contact"

    result = await crm_operation(operation, crm_data)

    if not result.get("success"):
        logger.warning("hubspot_node.skipped", reason=result.get("error", "unknown"))
        return {
            **state,
            "tool_results": state["tool_results"] + [{"tool": "crm_operation", "result": result}],
            "tools_called": state["tools_called"] + ["crm_operation"],
        }

    lead_updates: dict[str, Any] = {}
    if result.get("contact_id"):
        lead_updates["hubspot_contact_id"] = result["contact_id"]
    for field in ("email", "phone"):
        if crm_data.get(field):
            lead_updates[field] = crm_data[field]
    full_name = " ".join(
        p for p in (crm_data.get("firstname", ""), crm_data.get("lastname", "")) if p
    ).strip()
    if full_name:
        lead_updates["name"] = full_name

    if lead_updates:
        await postgres_memory.update_lead(state["user_id"], lead_updates)

    return {
        **state,
        "tool_results": state["tool_results"] + [{"tool": "crm_operation", "result": result}],
        "tools_called": state["tools_called"] + ["crm_operation"],
        "lead_updated": bool(lead_updates) or state.get("lead_updated", False),
        "lead_profile": {**lead, **lead_updates},
    }


# ─────────────────────────────────────────────────────────────────────────────
# rag_node
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="rag_node")
async def rag_node(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    query = state.get("intent_data", {}).get("rag_query") or state["user_message"]
    result = await search_knowledge_base(query)
    return {
        **state,
        "tool_results": state["tool_results"] + [{"tool": "search_knowledge_base", "result": result}],
        "tools_called": state["tools_called"] + ["search_knowledge_base"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# lead_scoring_node
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="lead_scoring_node")
async def lead_scoring_node(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    lead = state.get("lead_profile") or {}
    signals = state.get("intent_data", {}).get("lead_signals") or {}

    args = {
        "name": lead.get("name"),
        "email": lead.get("email"),
        "phone": lead.get("phone"),
        "budget": signals.get("budget") or lead.get("budget", "unknown"),
        "authority": signals.get("authority") or lead.get("authority", "unknown"),
        "engagement_level": signals.get("engagement_level", lead.get("engagement_level", 0)),
        "interest_level": signals.get("interest_level", lead.get("interest_level", 0)),
    }

    result = score_lead(args)

    lead_updates = {
        "lead_score": result["score"],
        "lead_temperature": result["temperature"],
        "budget": args["budget"],
        "authority": args["authority"],
        "engagement_level": args["engagement_level"],
        "interest_level": args["interest_level"],
    }
    await postgres_memory.update_lead(state["user_id"], lead_updates)

    return {
        **state,
        "tool_results": state["tool_results"] + [{"tool": "score_lead", "result": result}],
        "tools_called": state["tools_called"] + ["score_lead"],
        "lead_updated": True,
        "lead_profile": {**lead, **lead_updates},
    }


def route_after_scoring(state: GraphState) -> str:
    lead = state.get("lead_profile") or {}
    if lead.get("lead_temperature") == "qualified":
        return "handoff_node"
    return "generate_response"


# ─────────────────────────────────────────────────────────────────────────────
# handoff_node
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="handoff_node")
async def handoff_node(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    lead = state.get("lead_profile") or {}
    reason = (
        state.get("intent_data", {}).get("escalation_reason")
        or (
            f"Lead qualified — score {lead.get('lead_score')}/100"
            if lead.get("lead_temperature") == "qualified"
            else ""
        )
        or "Escalation requested"
    )
    priority = "high" if lead.get("lead_temperature") == "qualified" else "medium"

    result = await escalate_to_human(
        user_id=state["user_id"], reason=reason, priority=priority, lead=lead
    )

    return {
        **state,
        "tool_results": state["tool_results"] + [{"tool": "escalate_to_human", "result": result}],
        "tools_called": state["tools_called"] + ["escalate_to_human"],
        "escalated": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# generate_response  — LangChain bind_tools via gemini_service
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="generate_response")
async def generate_response(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    system_prompt = build_system_prompt(state)

    tool_results = list(state.get("tool_results", []))
    tools_called = list(state.get("tools_called", []))
    lead_profile = dict(state.get("lead_profile") or {})
    lead_updated = state.get("lead_updated", False)
    escalated = state.get("escalated", False)

    text = ""
    for _ in range(max(1, settings.MAX_AGENT_ITERATIONS)):
        context_text = _build_context_text(state, tool_results)
        result = await gemini_service.generate_with_tools(
            messages=[{"role": "user", "content": context_text}],
            tools=TOOLS,
            system_prompt=system_prompt,
        )

        calls = result.get("function_calls", [])
        if not calls:
            text = result["text"]
            break

        for call in calls:
            name = call["name"]
            # args arrive as a plain dict from generate_with_tools
            args = call.get("args", {}) or {}
            tools_called.append(name)

            if name == "search_knowledge_base":
                tr = await search_knowledge_base(args.get("query", ""))

            elif name == "crm_operation":
                operation = args.get("operation", "")
                # data may be a nested dict or a Pydantic model instance
                data = _flatten_crm_data(args.get("data", {}))
                if operation == "update_contact" and lead_profile.get("hubspot_contact_id"):
                    data.setdefault("contact_id", lead_profile["hubspot_contact_id"])
                tr = await crm_operation(operation, data)

                updates: dict[str, Any] = {}
                if tr.get("contact_id"):
                    updates["hubspot_contact_id"] = tr["contact_id"]
                for field in ("email", "phone"):
                    if data.get(field):
                        updates[field] = data[field]
                full_name = " ".join(
                    p for p in (data.get("firstname", ""), data.get("lastname", "")) if p
                ).strip()
                if full_name:
                    updates["name"] = full_name
                if updates:
                    await postgres_memory.update_lead(state["user_id"], updates)
                    lead_profile.update(updates)
                    lead_updated = True

            elif name == "score_lead":
                tr = score_lead(args)
                updates = {
                    "lead_score": tr["score"],
                    "lead_temperature": tr["temperature"],
                    "budget": args.get("budget", "unknown"),
                    "authority": args.get("authority", "unknown"),
                    "engagement_level": args.get("engagement_level", 0),
                    "interest_level": args.get("interest_level", 0),
                }
                await postgres_memory.update_lead(state["user_id"], updates)
                lead_profile.update(updates)
                lead_updated = True

            elif name == "escalate_to_human":
                tr = await escalate_to_human(
                    user_id=state["user_id"],
                    reason=args.get("reason", "Escalation requested"),
                    priority=args.get("priority", "medium"),
                    lead=lead_profile,
                )
                escalated = True

            else:
                tr = {"error": f"Unknown tool: {name}"}

            tool_results.append({"tool": name, "result": tr})

    if not text:
        followup_prompt = (
            f"{system_prompt}\n\n## Conversation\n"
            f"{_build_context_text(state, tool_results)}\n\n"
            "Respond directly to the customer's latest message now, in plain text."
        )
        text = await gemini_service.generate_text(followup_prompt, temperature=0.3)

    if not text:
        text = "I've made a note of that. Is there anything else I can help you with?"

    return {
        **state,
        "response": text,
        "tool_results": tool_results,
        "tools_called": tools_called,
        "lead_profile": lead_profile,
        "lead_updated": lead_updated,
        "escalated": escalated,
    }


# ─────────────────────────────────────────────────────────────────────────────
# save_memory
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="save_memory")
async def save_memory(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    user_id = state["user_id"]
    await postgres_memory.append_message(user_id, "user", state["user_message"], source=state["source"])
    await postgres_memory.append_message(user_id, "assistant", state["response"])

    if state.get("escalated"):
        await postgres_memory.update_status(user_id, "escalated")

    return state


# ─────────────────────────────────────────────────────────────────────────────
# messaging_node
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="messaging_node")
async def messaging_node(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    """Deliver the response to the originating channel. Vapi is a no-op here —
    its response is returned directly in the webhook HTTP body."""
    if state["source"] == "vapi":
        return state

    from app.services.gemini_service import UnifiedMessage
    from app.tools.messaging_tool import send_reply

    message = UnifiedMessage(
        user_id=state["user_id"],
        source=state["source"],
        input_type=state.get("input_type", "text"),
        content=state["user_message"],
        metadata=state.get("metadata", {}),
    )
    await send_reply(message, state["response"])
    return state
