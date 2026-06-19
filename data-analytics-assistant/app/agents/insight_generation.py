"""Insight Generation Agent: produces executive-level data-driven insights."""
from __future__ import annotations

import json
import traceback
import uuid

from app.agents.data_loader import get_cached_dataframe
from app.schemas.state import AnalyticsState
from app.schemas.insight import Insight
from app.services.gemini_service import get_gemini_service
from app.prompts.insight_prompt import INSIGHT_SYSTEM, INSIGHT_PROMPT


def insight_generation_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node: generates data-driven executive insights using Gemini,
    grounded in actual computed statistics from the dataset.
    """
    try:
        if not state.profiling_result or not state.kpis:
            return {"error_message": "Missing profiling or KPIs for insight generation.", "current_step": "error"}

        profiling = state.profiling_result
        summary = state.dataset_summary

        # Compute richer column statistics from cached DataFrame
        df = get_cached_dataframe(state.file_path)
        column_stats_lines = []
        if df is not None:
            for col in profiling.numeric_columns[:10]:
                s = df[col].dropna()
                if len(s) > 0:
                    column_stats_lines.append(
                        f"  {col}: sum={s.sum():,.2f}, mean={s.mean():,.2f}, "
                        f"median={s.median():,.2f}, std={s.std():,.2f}, "
                        f"min={s.min():,.2f}, max={s.max():,.2f}"
                    )
            for col in profiling.categorical_columns[:5]:
                vc = df[col].value_counts().head(5)
                column_stats_lines.append(f"  {col}: {dict(vc)}")

        # KPI summary for context
        kpis_summary = "\n".join(
            f"  - [{k.priority}] {k.name}: {k.business_definition} | Value: {k.current_value or 'N/A'}"
            for k in state.kpis
        )

        prompt = INSIGHT_PROMPT.format(
            business_domain=state.business_domain,
            business_context=state.domain_reasoning,
            kpis_summary=kpis_summary,
            stats_highlights="\n".join(column_stats_lines) or "See column statistics",
            row_count=summary.row_count,
            numeric_columns=", ".join(profiling.numeric_columns),
            categorical_columns=", ".join(profiling.categorical_columns),
            time_dimension=", ".join(profiling.datetime_columns) or "None",
            column_stats="\n".join(column_stats_lines),
        )

        gemini = get_gemini_service()
        raw_insights = gemini.generate_json(prompt, system_instruction=INSIGHT_SYSTEM, temperature=0.4)

        if not isinstance(raw_insights, list):
            raw_insights = raw_insights.get("insights", [])

        insights = []
        for raw in raw_insights:
            if not raw.get("id"):
                raw["id"] = f"insight_{uuid.uuid4().hex[:8]}"
            insights.append(Insight(**raw))

        return {
            "insights": insights,
            "current_step": "insights_generated",
            "error_message": None,
        }

    except Exception as exc:
        return {
            "error_message": f"Insight generation failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }
