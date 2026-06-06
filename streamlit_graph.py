"""Streamlit graph — full pipeline with question_generator, review_node, and MemorySaver."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from nodes.creative import creative_node
from nodes.media_buying import media_buying_node
from nodes.merge import merge_node
from nodes.orchestrator import orchestrator_node
from nodes.question_generator import question_generator_node
from nodes.review import review_node
from state import CampaignState


def _route_to_subagents(state: CampaignState):
    """Fan-out to creative and media branches after orchestrator."""
    if not state.get("campaign_plan") or (
        state.get("errors") and not state.get("campaign_plan")
    ):
        return "merge_node"
    return [
        Send("creative_node", dict(state)),
        Send("media_buying_node", dict(state)),
    ]


def _route_after_review(state: CampaignState):
    """After review_node: loop back to creative_node if text rejected, else proceed to merge."""
    if state.get("review_stage") == "redo_creative":
        return "creative_node"
    return "merge_node"


def get_streamlit_graph():
    """
    Build and compile the full Streamlit graph with MemorySaver checkpointer.

    Topology:
        START
          -> question_generator_node   [interrupt: questions]
          -> orchestrator_node
          -> fan-out (Send):
               creative_node           [LLM text + Imagen images]
               media_buying_node       [budget + audience]
        creative_node
          -> review_node               [interrupt: image_review, interrupt: text_review]
        review_node --[done]---------> merge_node -> END
        review_node --[redo_creative]-> creative_node  (loop)
        media_buying_node -----------> merge_node -> END
    """
    builder = StateGraph(CampaignState)

    builder.add_node("question_generator_node", question_generator_node)
    builder.add_node("orchestrator_node", orchestrator_node)
    builder.add_node("creative_node", creative_node)
    builder.add_node("media_buying_node", media_buying_node)
    builder.add_node("review_node", review_node)
    builder.add_node("merge_node", merge_node)

    builder.set_entry_point("question_generator_node")
    builder.add_edge("question_generator_node", "orchestrator_node")

    builder.add_conditional_edges(
        "orchestrator_node",
        _route_to_subagents,
        ["creative_node", "media_buying_node", "merge_node"],
    )

    builder.add_edge("creative_node", "review_node")
    builder.add_conditional_edges(
        "review_node",
        _route_after_review,
        ["creative_node", "merge_node"],
    )
    builder.add_edge("media_buying_node", "merge_node")
    builder.add_edge("merge_node", END)

    return builder.compile(checkpointer=MemorySaver())
