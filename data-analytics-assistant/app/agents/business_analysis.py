"""Business Analysis Agent: infers domain, entities, and business context."""
from __future__ import annotations

import json
import traceback

from app.schemas.state import AnalyticsState
from app.services.gemini_service import get_gemini_service
from app.prompts.business_prompt import BUSINESS_SYSTEM, BUSINESS_PROMPT


def business_analysis_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node: uses Gemini to infer the business domain and context
    from column names, types, and sample data.
    """
    try:
        if not state.profiling_result or not state.dataset_summary:
            return {"error_message": "Missing profiling data for business analysis.", "current_step": "error"}

        profiling = state.profiling_result
        summary = state.dataset_summary

        # Build column details string
        col_details = []
        for cp in profiling.column_profiles:
            detail = f"  - {cp.name}: {cp.inferred_type}"
            if cp.sample_values:
                samples = str(cp.sample_values[:3])
                detail += f" | samples: {samples}"
            col_details.append(detail)

        # Stats summary (numeric cols)
        stats_lines = []
        for cp in profiling.column_profiles:
            if cp.inferred_type == "numeric" and cp.mean is not None:
                stats_lines.append(f"  - {cp.name}: mean={cp.mean:.2f}, min={cp.min_val}, max={cp.max_val}")

        prompt = BUSINESS_PROMPT.format(
            file_name=summary.file_name,
            row_count=summary.row_count,
            column_count=summary.column_count,
            column_details="\n".join(col_details),
            sample_data=json.dumps(summary.sample_rows[:3], indent=2, default=str),
            stats_summary="\n".join(stats_lines) or "No numeric columns",
        )

        gemini = get_gemini_service()
        result = gemini.generate_json(prompt, system_instruction=BUSINESS_SYSTEM, temperature=0.2)

        return {
            "business_domain": result.get("business_domain", "Other"),
            "domain_confidence": float(result.get("domain_confidence", 0.5)),
            "domain_reasoning": result.get("domain_reasoning", ""),
            "current_step": "business_analyzed",
            "error_message": None,
        }

    except Exception as exc:
        return {
            "error_message": f"Business analysis failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }
