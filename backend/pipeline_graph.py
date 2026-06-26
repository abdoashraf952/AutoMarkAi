"""Full campaign pipeline graph — question_generator, review nodes, and MemorySaver.

This is the interactive (human-in-the-loop) graph that backs the FastAPI server
in `api.py`, which the Next.js frontend drives over HTTP/SSE.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Send

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
    image_pick_node,
    image_regen_node,
    image_review_node,
    text_review_node,
)
from AutoMarkAi.backend.nodes.strategy import strategy_node
from AutoMarkAi.backend.state import CampaignState


def _route_after_orchestrator(state: CampaignState):
    """After orchestrator: run the Strategist if we have a plan, else short-circuit."""
    if not state.get("campaign_plan"):
        return "merge_node"
    return "strategy_node"


def _route_to_subagents(state: CampaignState):
    """Fan-out to creative and media branches after the Strategist."""
    if not state.get("campaign_plan"):
        return "merge_node"
    return [
        Send("creative_node", dict(state)),
        Send("media_buying_node", dict(state)),
    ]


def _route_after_image_review(state: CampaignState):
    """After image_review_node: regenerate, jump to the picker, or move to text review."""
    route = state.get("review_route")
    if route == "to_regen":
        return "image_regen_node"
    if route == "to_pick":
        return "image_pick_node"
    return "text_review_node"


def _route_after_text_review(state: CampaignState):
    """After text_review_node: loop back to creative_node if text rejected, else merge."""
    if state.get("review_stage") == "redo_creative":
        return "creative_node"
    return "merge_node"


def get_pipeline_graph():
    """
    Build and compile the full pipeline graph with a MemorySaver checkpointer.

    Topology:
        START
          -> target_gen_node           [analyse product, rank campaign targets]
          -> target_ask_node           [interrupt: campaign_target]  --sets goal-->
          -> question_gen_node         [decide+generate next adaptive question]
               --(ask)--> question_ask_node [interrupt: questions] --loop--> question_gen_node
               --(done)--> orchestrator_node
          -> strategy_node             [persona + channels + dayparting]
          -> fan-out (Send):
               creative_node           [LLM text + Gemini images]
               media_buying_node       [budget + audience]
        creative_node
          -> image_review_node         [interrupt: image_review]
        image_review_node --[to_regen]-> image_regen_node -> image_review_node  (loop)
        image_review_node --[to_pick]--> image_pick_node   [interrupt: max_regenerations_exceeded]
        image_review_node --[to_text]--> text_review_node  [interrupt: text_review]
        image_pick_node --------------> text_review_node
        text_review_node --[done]------> merge_node -> END
        text_review_node --[redo]------> creative_node  (loop, copy only)
        media_buying_node -------------> merge_node -> END

    Image generation only ever runs inside image_regen_node, which has no
    interrupt — so resuming an interrupt never replays (or re-bills) a
    generation.
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
    builder.add_node("image_review_node", image_review_node)
    builder.add_node("image_regen_node", image_regen_node)
    builder.add_node("image_pick_node", image_pick_node)
    builder.add_node("text_review_node", text_review_node)
    builder.add_node("merge_node", merge_node)

    # Fixed campaign-target question first, then the adaptive interview:
    #   target_gen → target_ask → question_gen ─(ask)→ question_ask ─(loop)→ question_gen
    #                                          └─(done)──────────────────→ orchestrator
    builder.set_entry_point("target_gen_node")
    builder.add_edge("target_gen_node", "target_ask_node")
    builder.add_edge("target_ask_node", "question_gen_node")
    builder.add_conditional_edges(
        "question_gen_node",
        route_after_gen,
        ["question_ask_node", "orchestrator_node"],
    )
    builder.add_edge("question_ask_node", "question_gen_node")

    # orchestrator -> strategy_node -> fan-out (so creative/media can use the persona)
    builder.add_conditional_edges(
        "orchestrator_node",
        _route_after_orchestrator,
        ["strategy_node", "merge_node"],
    )
    builder.add_conditional_edges(
        "strategy_node",
        _route_to_subagents,
        ["creative_node", "media_buying_node", "merge_node"],
    )

    builder.add_edge("creative_node", "image_review_node")
    builder.add_conditional_edges(
        "image_review_node",
        _route_after_image_review,
        ["image_regen_node", "image_pick_node", "text_review_node"],
    )
    builder.add_edge("image_regen_node", "image_review_node")
    builder.add_edge("image_pick_node", "text_review_node")
    builder.add_conditional_edges(
        "text_review_node",
        _route_after_text_review,
        ["creative_node", "merge_node"],
    )
    builder.add_edge("media_buying_node", "merge_node")
    builder.add_edge("merge_node", END)

    return builder.compile(checkpointer=MemorySaver())
