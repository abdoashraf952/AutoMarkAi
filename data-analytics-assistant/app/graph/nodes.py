"""LangGraph node wrappers that translate between dict state and AnalyticsState."""
from __future__ import annotations

from typing import Any

from app.schemas.state import AnalyticsState
from app.agents import (
    data_loader_agent,
    profiling_agent,
    business_analysis_agent,
    kpi_discovery_agent,
    insight_generation_agent,
    visualization_agent,
    powerbi_builder_agent,
    report_generator_agent,
    chat_orchestrator_agent,
)


def _merge(base: AnalyticsState, updates: dict[str, Any]) -> AnalyticsState:
    """Return a new AnalyticsState with the given fields updated."""
    data = base.model_dump()
    data.update({k: v for k, v in updates.items() if v is not None or k == "error_message"})
    return AnalyticsState(**data)


# Each node receives and returns the full state dict (LangGraph convention)

def node_data_loader(state: dict) -> dict:
    s = AnalyticsState(**state)
    result = data_loader_agent(s)
    return {**state, **result}


def node_profiling(state: dict) -> dict:
    s = AnalyticsState(**state)
    result = profiling_agent(s)
    if "profiling_result" in result and hasattr(result["profiling_result"], "model_dump"):
        result["profiling_result"] = result["profiling_result"].model_dump()
    return {**state, **result}


def node_business_analysis(state: dict) -> dict:
    s = AnalyticsState(**state)
    result = business_analysis_agent(s)
    return {**state, **result}


def node_kpi_discovery(state: dict) -> dict:
    s = AnalyticsState(**state)
    result = kpi_discovery_agent(s)
    if "kpis" in result:
        result["kpis"] = [k.model_dump() if hasattr(k, "model_dump") else k for k in result["kpis"]]
    return {**state, **result}


def node_insight_generation(state: dict) -> dict:
    s = AnalyticsState(**state)
    result = insight_generation_agent(s)
    if "insights" in result:
        result["insights"] = [i.model_dump() if hasattr(i, "model_dump") else i for i in result["insights"]]
    return {**state, **result}


def node_visualization(state: dict) -> dict:
    s = AnalyticsState(**state)
    result = visualization_agent(s)
    return {**state, **result}


def node_powerbi_builder(state: dict) -> dict:
    s = AnalyticsState(**state)
    result = powerbi_builder_agent(s)
    if "dashboard_spec" in result and hasattr(result["dashboard_spec"], "model_dump"):
        result["dashboard_spec"] = result["dashboard_spec"].model_dump()
    return {**state, **result}


def node_report_generator(state: dict) -> dict:
    s = AnalyticsState(**state)
    result = report_generator_agent(s)
    return {**state, **result}


def node_chat_orchestrator(state: dict) -> dict:
    s = AnalyticsState(**state)
    result = chat_orchestrator_agent(s)
    if "chat_history" in result:
        result["chat_history"] = [
            m.model_dump() if hasattr(m, "model_dump") else m for m in result["chat_history"]
        ]
    return {**state, **result}


def should_continue_or_error(state: dict) -> str:
    """Conditional edge: route to error node or continue."""
    if state.get("error_message"):
        return "error"
    return "continue"


def route_after_load(state: dict) -> str:
    if state.get("error_message"):
        return "error"
    if state.get("is_follow_up"):
        return "chat"
    return "continue"
