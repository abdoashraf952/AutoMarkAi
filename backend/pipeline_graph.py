"""Full campaign pipeline graph — real estate interview, photo selection, review.

This is the interactive (human-in-the-loop) graph that backs the FastAPI server
in `api.py`, which the Next.js frontend drives over HTTP/SSE.

Phase 0 change: routing functions are now imported from nodes/supervisor.py
so they live in one place. Graph topology and all node behaviour are unchanged.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from AutoMarkAi.backend.nodes.creative import creative_node
from AutoMarkAi.backend.nodes.media_buying import media_buying_node
from AutoMarkAi.backend.nodes.merge import merge_node
from AutoMarkAi.backend.nodes.orchestrator import orchestrator_node
from AutoMarkAi.backend.nodes.question_generator import (
    question_ask_node,
    question_gen_node,
    route_after_gen,
    target_ask_node,
    target_gen_node,
)
from AutoMarkAi.backend.nodes.review import (
    photo_select_node,
    text_review_node,
)
from AutoMarkAi.backend.nodes.strategy import strategy_node

# Phase 0: routing functions centralised here.
from AutoMarkAi.backend.nodes.supervisor import (
    route_after_orchestrator,
    route_after_text_review,
    route_to_subagents,
)
from AutoMarkAi.backend.state import CampaignState


def get_pipeline_graph():
    """
    Build and compile the full pipeline graph with a MemorySaver checkpointer.

    Topology (unchanged from pre-Phase-0):
        START
          -> target_gen_node           [analyse units, rank campaign targets]
          -> target_ask_node           [interrupt: campaign_target  (skipped in guided/autopilot)]
          -> question_gen_node         [next fixed question / follow-up / done]
               --(ask)--> question_ask_node [interrupt: questions] --loop--> question_gen_node
               --(done)--> orchestrator_node
          -> strategy_node             [persona + channels + dayparting]
          -> fan-out (Send):
               creative_node           [real estate ad copy + real photos]
               media_buying_node       [HOUSING-compliant targeting]
        creative_node ---------------> photo_select_node [interrupt: photo_select (skipped in autopilot)]
        photo_select_node -----------> text_review_node  [interrupt: text_review (skipped in autopilot)]
        text_review_node --[done]----> merge_node -> END
        text_review_node --[redo]----> creative_node  (loop, copy only)
        media_buying_node -----------> merge_node -> END
    """
    builder = StateGraph(CampaignState)

    builder.add_node("target_gen_node", target_gen_node)
    builder.add_node("target_ask_node", target_ask_node)
    builder.add_node("question_gen_node", question_gen_node)
    builder.add_node("question_ask_node", question_ask_node)
    builder.add_node("orchestrator_node", orchestrator_node)
    builder.add_node("strategy_node", strategy_node)
    builder.add_node("creative_node", creative_node)
    builder.add_node("media_buying_node", media_buying_node)
    builder.add_node("photo_select_node", photo_select_node)
    builder.add_node("text_review_node", text_review_node)
    builder.add_node("merge_node", merge_node)

    builder.set_entry_point("target_gen_node")
    builder.add_edge("target_gen_node", "target_ask_node")
    builder.add_edge("target_ask_node", "question_gen_node")
    builder.add_conditional_edges(
        "question_gen_node",
        route_after_gen,
        ["question_ask_node", "orchestrator_node"],
    )
    builder.add_edge("question_ask_node", "question_gen_node")

    builder.add_conditional_edges(
        "orchestrator_node",
        route_after_orchestrator,
        ["strategy_node", "merge_node"],
    )
    builder.add_conditional_edges(
        "strategy_node",
        route_to_subagents,
        ["creative_node", "media_buying_node", "merge_node"],
    )

    builder.add_edge("creative_node", "photo_select_node")
    builder.add_edge("photo_select_node", "text_review_node")
    builder.add_conditional_edges(
        "text_review_node",
        route_after_text_review,
        ["creative_node", "merge_node"],
    )
    builder.add_edge("media_buying_node", "merge_node")
    builder.add_edge("merge_node", END)

    return builder.compile(checkpointer=MemorySaver())
