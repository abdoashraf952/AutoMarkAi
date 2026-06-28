"""Visualization Recommendation Agent: suggests optimal chart types."""
from __future__ import annotations

import traceback

from app.schemas.state import AnalyticsState
from app.services.gemini_service import get_gemini_service
from app.prompts.visualization_prompt import VIZ_SYSTEM, VIZ_PROMPT


def visualization_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node: recommends chart types for each KPI and insight,
    including Power BI visual type mappings.
    """
    try:
        if not state.kpis or not state.insights:
            return {"error_message": "Missing KPIs or insights for visualization.", "current_step": "error"}

        profiling = state.profiling_result

        kpis_names = "\n".join(
            f"  - {k.id}: {k.name} ({k.category}, {k.priority})" for k in state.kpis
        )
        insights_summary = "\n".join(
            f"  - {i.id}: {i.title} [{i.type}]" for i in state.insights
        )

        prompt = VIZ_PROMPT.format(
            business_domain=state.business_domain,
            kpis_names=kpis_names,
            numeric_columns=", ".join(profiling.numeric_columns) if profiling else "",
            categorical_columns=", ".join(profiling.categorical_columns) if profiling else "",
            datetime_columns=", ".join(profiling.datetime_columns) if profiling else "",
            insights_summary=insights_summary,
        )

        gemini = get_gemini_service()
        raw_vizs = gemini.generate_json(prompt, system_instruction=VIZ_SYSTEM, temperature=0.3)

        if not isinstance(raw_vizs, list):
            raw_vizs = raw_vizs.get("recommendations", [])

        return {
            "visualization_recommendations": raw_vizs,
            "current_step": "visualizations_recommended",
            "error_message": None,
        }

    except Exception as exc:
        return {
            "error_message": f"Visualization recommendation failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }
