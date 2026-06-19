"""Power BI Dashboard Builder Agent: generates structured dashboard specs."""
from __future__ import annotations

import json
import traceback

from app.schemas.state import AnalyticsState
from app.schemas.dashboard import DashboardSpec
from app.services.gemini_service import get_gemini_service
from app.prompts.dashboard_prompt import DASHBOARD_SYSTEM, DASHBOARD_PROMPT


def powerbi_builder_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node: generates a full Power BI dashboard JSON specification
    using the analysis outputs from all upstream agents.
    """
    try:
        if not state.kpis or not state.insights:
            return {"error_message": "Missing KPIs or insights for dashboard generation.", "current_step": "error"}

        profiling = state.profiling_result

        # Serialize KPIs concisely for the prompt
        kpis_json = json.dumps(
            [{"id": k.id, "name": k.name, "category": k.category, "priority": k.priority,
              "unit": k.unit, "current_value": k.current_value} for k in state.kpis],
            indent=2
        )

        insights_summary = "\n".join(
            f"  [{i.priority}] {i.title}: {i.executive_summary}" for i in state.insights
        )

        viz_summary = json.dumps(
            [{"chart_type": v.get("chart_type"), "title": v.get("title"),
              "x_axis": v.get("x_axis"), "y_axis": v.get("y_axis")}
             for v in state.visualization_recommendations[:10]],
            indent=2
        )

        prompt = DASHBOARD_PROMPT.format(
            business_domain=state.business_domain,
            kpis_json=kpis_json,
            insights_summary=insights_summary,
            viz_summary=viz_summary,
            numeric_columns=", ".join(profiling.numeric_columns) if profiling else "",
            categorical_columns=", ".join(profiling.categorical_columns) if profiling else "",
            datetime_columns=", ".join(profiling.datetime_columns) if profiling else "",
        )

        gemini = get_gemini_service()
        raw_spec = gemini.generate_json(prompt, system_instruction=DASHBOARD_SYSTEM, temperature=0.3)

        # Parse into Pydantic model
        try:
            dashboard_spec = DashboardSpec(**raw_spec, raw_spec=raw_spec)
        except Exception:
            # Fallback: wrap raw spec
            dashboard_spec = DashboardSpec(
                title=raw_spec.get("title", f"{state.business_domain} Analytics Dashboard"),
                description=raw_spec.get("description", ""),
                target_audience=raw_spec.get("target_audience", "Executive Leadership"),
                global_filters=raw_spec.get("global_filters", []),
                data_refresh_frequency=raw_spec.get("data_refresh_frequency", "Daily"),
                executive_summary=raw_spec.get("executive_summary", ""),
                implementation_notes=raw_spec.get("implementation_notes", []),
                raw_spec=raw_spec,
            )

        return {
            "dashboard_spec": dashboard_spec,
            "current_step": "dashboard_built",
            "error_message": None,
        }

    except Exception as exc:
        return {
            "error_message": f"Dashboard build failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }
