"""LangGraph graph definition for the AutoMark AI campaign generation pipeline."""

from langgraph.types import Send
from langgraph.graph import END, StateGraph

from src.campaigns.nodes.creative import creative_node
from src.campaigns.nodes.media_buying import media_buying_node
from src.campaigns.nodes.merge import merge_node
from src.campaigns.nodes.orchestrator import orchestrator_node
from src.campaigns.nodes.strategy import strategy_node
from src.campaigns.state import CampaignState


def route_after_orchestrator(state: CampaignState):
    """After orchestrator: run the Strategist if we have a plan, else short-circuit."""
    if not state.get("campaign_plan"):
        return "merge_node"
    return "strategy_node"


def route_to_subagents(state: CampaignState):
    """
    Fan-out router called after strategy_node.

    Uses the Send API so creative_node and media_buying_node run in parallel.
    If the orchestrator failed (empty plan or errors), short-circuit to merge_node
    so the error surfaces cleanly without attempting sub-agents.
    """
    if not state.get("campaign_plan") or (
        state.get("errors") and not state.get("campaign_plan")
    ):
        return "merge_node"

    return [
        Send("creative_node", dict(state)),
        Send("media_buying_node", dict(state)),
    ]


def get_graph():
    """Build and compile the campaign generation graph. Safe to import without side effects."""
    builder = StateGraph(CampaignState)

    builder.add_node("orchestrator_node", orchestrator_node)
    builder.add_node("strategy_node", strategy_node)
    builder.add_node("creative_node", creative_node)
    builder.add_node("media_buying_node", media_buying_node)
    builder.add_node("merge_node", merge_node)

    builder.set_entry_point("orchestrator_node")

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

    builder.add_edge("creative_node", "merge_node")
    builder.add_edge("media_buying_node", "merge_node")
    builder.add_edge("merge_node", END)

    return builder.compile()
