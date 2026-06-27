"""LangGraph StateGraph workflow for the analytics pipeline."""
from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph, END

from app.graph.nodes import (
    node_data_loader,
    node_profiling,
    node_business_analysis,
    node_kpi_discovery,
    node_insight_generation,
    node_visualization,
    node_report_generator,
    node_chat_orchestrator,
    should_continue_or_error,
    route_after_load,
)

# ── State TypedDict for LangGraph ─────────────────────────────────────────────
# LangGraph requires a TypedDict or Annotated schema for state; we use dict[str, Any]
# and rely on our AnalyticsState Pydantic model internally within each node.

def build_analytics_graph() -> Any:
    """
    Build and compile the full analytics LangGraph workflow.

    Pipeline (new analysis):
        data_loader → profiling → business_analysis → kpi_discovery
        → insight_generation → visualization → report_generator → END

    Pipeline (follow-up query):
        data_loader → chat_orchestrator → END

    Error path: any node → error_handler → END
    """
    graph = StateGraph(dict)

    # ── Register nodes ────────────────────────────────────────────────────────
    graph.add_node("data_loader", node_data_loader)
    graph.add_node("profiling", node_profiling)
    graph.add_node("business_analysis", node_business_analysis)
    graph.add_node("kpi_discovery", node_kpi_discovery)
    graph.add_node("insight_generation", node_insight_generation)
    graph.add_node("visualization", node_visualization)
    graph.add_node("report_generator", node_report_generator)
    graph.add_node("chat_orchestrator", node_chat_orchestrator)
    graph.add_node("error_handler", _error_handler_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point("data_loader")

    # After data_loader: new analysis vs. follow-up vs. error
    graph.add_conditional_edges(
        "data_loader",
        route_after_load,
        {
            "continue": "profiling",
            "chat": "chat_orchestrator",
            "error": "error_handler",
        }
    )

    # ── Sequential analysis pipeline with per-step error gates ───────────────
    _add_sequential_edge(graph, "profiling", "business_analysis")
    _add_sequential_edge(graph, "business_analysis", "kpi_discovery")
    _add_sequential_edge(graph, "kpi_discovery", "insight_generation")
    _add_sequential_edge(graph, "insight_generation", "visualization")
    _add_sequential_edge(graph, "visualization", "report_generator")

    # ── Terminal edges ────────────────────────────────────────────────────────
    graph.add_edge("report_generator", END)
    graph.add_edge("chat_orchestrator", END)
    graph.add_edge("error_handler", END)

    return graph.compile()


def _add_sequential_edge(graph: StateGraph, from_node: str, to_node: str) -> None:
    """Add a conditional edge that routes to error_handler on pipeline failure."""
    graph.add_conditional_edges(
        from_node,
        should_continue_or_error,
        {
            "continue": to_node,
            "error": "error_handler",
        }
    )


def _error_handler_node(state: dict) -> dict:
    """Terminal error node: logs and preserves the error message in state."""
    error = state.get("error_message", "Unknown error occurred")
    print(f"[ANALYTICS PIPELINE ERROR] {error}")
    return {**state, "current_step": "error"}


# ── Singleton compiled graph ──────────────────────────────────────────────────
_compiled_graph = None


def get_analytics_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_analytics_graph()
    return _compiled_graph
