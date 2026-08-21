"""
Report Generator Agent
Produces a consolidated executive report from all analysis outputs.
The report is returned as a structured Markdown string suitable for
display, download, or conversion to PDF.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.analytics.schemas.state import AnalyticsState
from src.analytics.schemas.kpi import KPI
from src.analytics.schemas.insight import Insight


_PRIORITY_EMOJI = {
    "Critical": "🔴",
    "High": "🟠",
    "Medium": "🟡",
    "Low": "🟢",
}

_TYPE_EMOJI = {
    "trend": "📈",
    "opportunity": "💡",
    "risk": "⚠️",
    "performance": "📊",
    "anomaly": "🔍",
    "benchmark": "🏁",
}


def report_generator_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node (optional terminal step): assembles a full Markdown
    executive report from all prior agent outputs.

    Returns:
        dict with key "executive_report" containing a Markdown string,
        and "report_generated_at" with an ISO timestamp.
    """
    try:
        report_lines: list[str] = []

        # ── Cover ──────────────────────────────────────────────────────────
        report_lines += [
            f"# 📊 Executive Analytics Report",
            f"",
            f"**Dataset:** {state.file_name}  ",
            f"**Business Domain:** {state.business_domain}  ",
            f"**Generated:** {datetime.utcnow().strftime('%d %B %Y, %H:%M UTC')}  ",
            f"**Domain Confidence:** {state.domain_confidence * 100:.0f}%",
            f"",
            "---",
            "",
        ]

        # ── Dataset Summary ────────────────────────────────────────────────
        if state.dataset_summary:
            ds = state.dataset_summary
            report_lines += [
                "## 1. Dataset Overview",
                "",
                f"| Property | Value |",
                f"|---|---|",
                f"| Total Records | {ds.row_count:,} |",
                f"| Columns | {ds.column_count} |",
                f"| File Size | {state.file_size_bytes / 1024:.1f} KB |",
                f"| Memory Usage | {ds.memory_usage_mb} MB |",
                "",
            ]

        # ── Data Quality ───────────────────────────────────────────────────
        if state.profiling_result:
            pr = state.profiling_result
            report_lines += [
                "## 2. Data Quality",
                "",
                f"**Quality Score:** {pr.data_quality_score:.0f} / 100  ",
                f"**Missing Data:** {pr.total_missing_pct:.1f}%  ",
                f"**Duplicate Rows:** {pr.duplicate_row_count:,}",
                "",
            ]
            if pr.quality_issues:
                report_lines.append("**Issues Detected:**")
                for issue in pr.quality_issues:
                    report_lines.append(f"- ⚠️ {issue}")
                report_lines.append("")

            if pr.profiling_narrative:
                report_lines += [
                    "**Profiling Narrative:**",
                    "",
                    pr.profiling_narrative,
                    "",
                ]

            # Column type breakdown
            type_counts = {
                "Numeric": len(pr.numeric_columns),
                "Categorical": len(pr.categorical_columns),
                "Datetime": len(pr.datetime_columns),
                "Text": len(pr.text_columns),
            }
            report_lines += [
                "**Column Type Breakdown:**",
                "",
                "| Type | Count | Columns |",
                "|---|---|---|",
            ]
            for t, count in type_counts.items():
                cols_list = getattr(pr, f"{t.lower()}_columns", [])
                cols_preview = ", ".join(cols_list[:5])
                if len(cols_list) > 5:
                    cols_preview += f" (+{len(cols_list) - 5} more)"
                if count > 0:
                    report_lines.append(f"| {t} | {count} | {cols_preview} |")
            report_lines.append("")

        # ── Business Context ───────────────────────────────────────────────
        report_lines += [
            "## 3. Business Context",
            "",
            f"**Inferred Domain:** {state.business_domain}  ",
            f"**Confidence:** {state.domain_confidence * 100:.0f}%",
            "",
            state.domain_reasoning or "_No reasoning available._",
            "",
        ]

        # ── KPIs ───────────────────────────────────────────────────────────
        report_lines += [
            "## 4. Key Performance Indicators",
            "",
            f"*{len(state.kpis)} KPIs identified for the {state.business_domain} domain.*",
            "",
        ]

        # Group by priority
        for priority in ["Critical", "High", "Medium", "Low"]:
            priority_kpis = [k for k in state.kpis if k.priority == priority]
            if not priority_kpis:
                continue
            emoji = _PRIORITY_EMOJI.get(priority, "")
            report_lines.append(f"### {emoji} {priority} Priority KPIs")
            report_lines.append("")
            for kpi in priority_kpis:
                report_lines += [
                    f"#### {kpi.name}",
                    f"**Category:** {kpi.category}  ",
                    f"**Definition:** {kpi.business_definition}  ",
                ]
                if kpi.formula:
                    report_lines.append(f"**Formula:** `{kpi.formula}`  ")
                if kpi.current_value:
                    report_lines.append(f"**Current Value:** {kpi.current_value} {kpi.unit or ''}  ")
                if kpi.required_columns:
                    report_lines.append(f"**Required Columns:** {', '.join(kpi.required_columns)}  ")
                report_lines += [
                    f"**Why It Matters:** {kpi.why_important}",
                    "",
                ]

        # ── Insights ───────────────────────────────────────────────────────
        report_lines += [
            "## 5. Executive Insights",
            "",
            f"*{len(state.insights)} insights generated from data analysis.*",
            "",
        ]

        for priority in ["Critical", "High", "Medium", "Low"]:
            priority_insights = [i for i in state.insights if i.priority == priority]
            if not priority_insights:
                continue
            emoji = _PRIORITY_EMOJI.get(priority, "")
            report_lines.append(f"### {emoji} {priority} Priority Insights")
            report_lines.append("")
            for insight in priority_insights:
                type_emoji = _TYPE_EMOJI.get(insight.type.lower(), "📌")
                report_lines += [
                    f"#### {type_emoji} {insight.title}",
                    f"**Type:** {insight.type.title()} | **Confidence:** {insight.confidence}",
                    "",
                    f"**Summary:** {insight.executive_summary}",
                    "",
                    insight.detailed_analysis,
                    "",
                ]
                if insight.evidence:
                    report_lines.append("**Evidence:**")
                    for e in insight.evidence:
                        report_lines.append(f"- {e}")
                    report_lines.append("")
                report_lines += [
                    f"> **Recommendation:** {insight.recommendation}",
                    "",
                ]
                if insight.business_impact:
                    report_lines.append(f"*Business Impact: {insight.business_impact}*")
                    report_lines.append("")

        # ── Visualization Recommendations ──────────────────────────────────
        if state.visualization_recommendations:
            report_lines += [
                "## 6. Visualization Recommendations",
                "",
                "| Chart Title | Type | X Axis | Y Axis | Purpose |",
                "|---|---|---|---|---|",
            ]
            for v in state.visualization_recommendations:
                report_lines.append(
                    f"| {v.get('title', '')} | {v.get('chart_type', '')} "
                    f"| {v.get('x_axis', '—')} | {v.get('y_axis', '—')} "
                    f"| {v.get('business_purpose', '')} |"
                )
            report_lines.append("")

        # ── Footer ─────────────────────────────────────────────────────────
        report_lines += [
            "---",
            "",
            f"*Report generated by AI-Powered Data Analytics Assistant*  ",
            f"*Session: {state.session_id[:16]}…*  ",
            f"*{datetime.utcnow().strftime('%d %B %Y, %H:%M UTC')}*",
        ]

        report_markdown = "\n".join(report_lines)

        return {
            "executive_report": report_markdown,
            "report_generated_at": datetime.utcnow().isoformat(),
            "current_step": "report_generated",
            "error_message": None,
        }

    except Exception as exc:
        import traceback
        return {
            "error_message": f"Report generation failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }
