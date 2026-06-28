"""Data Profiling Agent: deep statistical analysis and quality assessment."""
from __future__ import annotations

import traceback

from app.agents.data_loader import get_cached_dataframe
from app.schemas.state import AnalyticsState
from app.services.gemini_service import get_gemini_service
from app.services.statistics_service import StatisticsService
from app.prompts.profiling_prompt import PROFILING_SYSTEM, PROFILING_PROMPT

_stats_service = StatisticsService()


def profiling_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node: profiles each column, computes quality metrics,
    and uses Gemini to generate a narrative summary.
    """
    try:
        if not state.dataset_summary:
            return {"error_message": "No dataset summary available for profiling.", "current_step": "error"}

        df = get_cached_dataframe(state.file_path)
        if df is None:
            return {"error_message": "DataFrame not in cache. Reload the file.", "current_step": "error"}

        summary = state.dataset_summary
        profiling = _stats_service.profile_dataframe(df, summary)

        # Build column summary for the prompt
        col_summary_lines = []
        for cp in profiling.column_profiles:
            line = f"  - {cp.name} ({cp.inferred_type}): {cp.null_pct}% null, {cp.unique_count} unique"
            if cp.mean is not None:
                line += f", mean={cp.mean:.2f}, min={cp.min_val}, max={cp.max_val}"
            elif cp.top_categories:
                top = cp.top_categories[0]
                line += f", top='{top['value']}' ({top['pct']}%)"
            col_summary_lines.append(line)

        prompt = PROFILING_PROMPT.format(
            file_name=summary.file_name,
            row_count=summary.row_count,
            column_count=summary.column_count,
            memory_mb=summary.memory_usage_mb,
            quality_score=profiling.data_quality_score,
            missing_pct=profiling.total_missing_pct,
            duplicate_count=profiling.duplicate_row_count,
            column_summary="\n".join(col_summary_lines),
            quality_issues="\n".join(f"- {i}" for i in profiling.quality_issues) or "None detected",
        )

        gemini = get_gemini_service()
        narrative = gemini.generate(prompt, system_instruction=PROFILING_SYSTEM, temperature=0.3)
        profiling.profiling_narrative = narrative

        return {
            "profiling_result": profiling,
            "current_step": "profiled",
            "error_message": None,
        }

    except Exception as exc:
        return {
            "error_message": f"Profiling failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }
