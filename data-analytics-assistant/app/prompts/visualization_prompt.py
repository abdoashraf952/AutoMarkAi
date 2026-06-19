"""Prompt templates for the Visualization Recommendation Agent."""

VIZ_SYSTEM = """You are a Data Visualization Expert and Business Intelligence Architect. 
You select the optimal chart types that maximize clarity and insight communication 
for executive audiences."""

VIZ_PROMPT = """
Recommend the best visualizations for this business dataset.

## Business Context
- Domain: {business_domain}
- KPIs: {kpis_names}

## Available Columns
- Numeric: {numeric_columns}
- Categorical: {categorical_columns}
- Datetime: {datetime_columns}

## Key Insights to Visualize
{insights_summary}

For each KPI and key insight, recommend the most effective visualization.

Return a JSON array:
[
  {{
    "kpi_or_insight_id": "<id>",
    "title": "<Chart title>",
    "chart_name": "<Descriptive name>",
    "chart_type": "<bar|line|pie|donut|scatter|area|funnel|waterfall|heatmap|treemap|gauge|table|combo>",
    "x_axis": "<column name or null>",
    "y_axis": "<column name or null>",
    "series_column": "<column for series/legend or null>",
    "measures": ["<measure col1>"],
    "dimensions": ["<dimension col1>"],
    "aggregation": "<sum|avg|count|min|max|none>",
    "filters_suggested": ["<suggested filter>"],
    "why_this_chart": "<1-2 sentence rationale>",
    "business_purpose": "<What decision does this visual support?>",
    "powerbi_visual_type": "<clusteredBarChart|lineChart|pieChart|donutChart|scatterChart|areaChart|funnelChart|waterfallChart|matrixVisual|cardVisual|gaugeVisual|tableEx>"
  }}
]
"""
