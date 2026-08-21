"""
app/graph/orchestrator.py — AutoMark AI CRM Agent (ORCAST)

Builds and compiles the ORCAST LangGraph StateGraph, and exposes
`run_graph()` as the single entrypoint used by every channel adapter.

Graph wiring
------------
memory_load -> [already escalated?]
    -> already_escalated -> save_memory
    -> intent_classify -> [conditional by intent]
        -> hubspot_node       -> generate_response
        -> rag_node           -> generate_response
        -> lead_scoring_node  -> [conditional: qualified?]
            -> handoff_node   -> generate_response
            -> generate_response
        -> handoff_node       -> generate_response
        -> generate_response (general_conversation)
generate_response -> save_memory -> messaging_node -> END
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, StateGraph

from src.crm.graph import nodes
from src.crm.graph.state import AgentResponse, GraphState
from src.crm.services.gemini_service import UnifiedMessage

logger = structlog.get_logger(__name__)


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("memory_load", nodes.memory_load)
    graph.add_node("already_escalated", nodes.already_escalated)
    graph.add_node("intent_classify", nodes.intent_classify)
    graph.add_node("hubspot_node", nodes.hubspot_node)
    graph.add_node("rag_node", nodes.rag_node)
    graph.add_node("lead_scoring_node", nodes.lead_scoring_node)
    graph.add_node("handoff_node", nodes.handoff_node)
    graph.add_node("generate_response", nodes.generate_response)
    graph.add_node("save_memory", nodes.save_memory)
    graph.add_node("messaging_node", nodes.messaging_node)

    graph.set_entry_point("memory_load")

    graph.add_conditional_edges(
        "memory_load",
        nodes.route_after_memory,
        {
            "already_escalated": "already_escalated",
            "intent_classify": "intent_classify",
        },
    )

    graph.add_conditional_edges(
        "intent_classify",
        nodes.route_by_intent,
        {
            "hubspot_node": "hubspot_node",
            "rag_node": "rag_node",
            "lead_scoring_node": "lead_scoring_node",
            "handoff_node": "handoff_node",
            "generate_response": "generate_response",
        },
    )

    graph.add_edge("hubspot_node", "generate_response")
    graph.add_edge("rag_node", "generate_response")
    graph.add_edge("handoff_node", "generate_response")

    graph.add_conditional_edges(
        "lead_scoring_node",
        nodes.route_after_scoring,
        {
            "handoff_node": "handoff_node",
            "generate_response": "generate_response",
        },
    )

    graph.add_edge("already_escalated", "save_memory")
    graph.add_edge("generate_response", "save_memory")
    graph.add_edge("save_memory", "messaging_node")
    graph.add_edge("messaging_node", END)

    return graph.compile()


compiled_graph = build_graph()


async def run_graph(message: UnifiedMessage) -> AgentResponse:
    """Run the ORCAST graph for a single inbound message and return the
    agent's reply. This is the single entrypoint used by every channel
    adapter (Messenger, Facebook Page Comments, Vapi)."""
    log = logger.bind(user_id=message.user_id, source=message.source)
    log.info("orchestrator.run_graph.start")

    initial_state: GraphState = {
        "user_id": message.user_id,
        "source": message.source,
        "input_type": message.input_type,
        "user_message": message.content,
        "metadata": message.metadata,
    }

    final_state = await compiled_graph.ainvoke(initial_state)

    log.info(
        "orchestrator.run_graph.done",
        tools_called=final_state.get("tools_called", []),
        escalated=final_state.get("escalated", False),
    )

    return AgentResponse(
        user_id=message.user_id,
        source=message.source,
        message=final_state.get("response", ""),
        tools_called=final_state.get("tools_called", []),
        lead_updated=final_state.get("lead_updated", False),
        escalated=final_state.get("escalated", False),
    )
