"""KPI Discovery Agent: identifies measurable KPIs from data and domain context."""
from __future__ import annotations

import traceback
import uuid

from app.schemas.state import AnalyticsState
from app.schemas.kpi import KPI
from app.services.gemini_service import get_gemini_service
from app.prompts.kpi_prompt import KPI_SYSTEM, KPI_PROMPT


def kpi_discovery_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node: uses Gemini to discover relevant KPIs based on
    dataset structure and business domain.
    """
    try:
        if not state.profiling_result:
            return {"error_message": "Missing profiling result for KPI discovery.", "current_step": "error"}

        profiling = state.profiling_result
        summary = state.dataset_summary

        # Build rich column descriptions
        col_details = []
        for cp in profiling.column_profiles:
            line = f"  - {cp.name} ({cp.inferred_type})"
            if cp.inferred_type == "numeric" and cp.mean is not None:
                line += f": range [{cp.min_val} – {cp.max_val}], mean={cp.mean:.2f}"
            elif cp.inferred_type == "categorical" and cp.top_categories:
                top = [c["value"] for c in cp.top_categories[:3]]
                line += f": top values → {top}"
            col_details.append(line)

        # Stats highlights for numeric columns
        stats_highlights = []
        for cp in profiling.column_profiles:
            if cp.inferred_type == "numeric" and cp.mean is not None:
                stats_highlights.append(
                    f"  {cp.name}: total={cp.mean * summary.row_count:.0f} (estimated), "
                    f"avg={cp.mean:.2f}, max={cp.max_val}"
                )

        prompt = KPI_PROMPT.format(
            business_domain=state.business_domain,
            business_context=state.domain_reasoning,
            key_entities="Inferred from column analysis",
            column_details="\n".join(col_details),
            numeric_columns=", ".join(profiling.numeric_columns) or "None",
            categorical_columns=", ".join(profiling.categorical_columns) or "None",
            datetime_columns=", ".join(profiling.datetime_columns) or "None",
            stats_highlights="\n".join(stats_highlights) or "No numeric stats available",
        )

        gemini = get_gemini_service()
        raw_kpis = gemini.generate_json(prompt, system_instruction=KPI_SYSTEM, temperature=0.25)

        if not isinstance(raw_kpis, list):
            raw_kpis = raw_kpis.get("kpis", [])

        kpis = []
        for raw in raw_kpis:
            # Ensure unique ID
            if not raw.get("id"):
                raw["id"] = f"kpi_{uuid.uuid4().hex[:8]}"
            kpis.append(KPI(**raw))

        return {
            "kpis": kpis,
            "current_step": "kpis_discovered",
            "error_message": None,
        }

    except Exception as exc:
        return {
            "error_message": f"KPI discovery failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }
