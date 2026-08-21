"""Prompt templates for the Insight Generation Agent."""

INSIGHT_SYSTEM = """You are a Chief Data Officer producing executive-level business intelligence reports. 
Your insights are data-driven, specific, actionable, and written for C-suite audiences. 
You never make generic statements — every insight is backed by specific numbers from the data."""

INSIGHT_PROMPT = """
Generate executive-level insights from this business dataset analysis.

## Business Context
- Domain: {business_domain}
- Business Summary: {business_context}

## Identified KPIs
{kpis_summary}

## Statistical Highlights
{stats_highlights}

## Data Profile
- Total Records: {row_count:,}
- Numeric columns: {numeric_columns}
- Categorical columns: {categorical_columns}
- Time dimension: {time_dimension}

## Column Statistics
{column_stats}

Generate 5-8 high-quality executive insights. Each insight must:
- Reference specific numbers, percentages, or patterns from the data
- Connect to business impact (revenue, efficiency, risk, growth)
- Include a clear, actionable recommendation
- Be suitable for a board-level presentation

For sales / retail / e-commerce data you MUST include at least one insight
for each of the following four modules (if the data supports it):
1. Best-selling products — which products/categories drive the most revenue or volume
2. VIP customers — highest-value customers by revenue, frequency, or recency (RFM)
3. Revenue & sales over time — trend, growth rate, seasonality, peak periods
4. Social / engagement signals — repeat purchases, return rate, discount sensitivity

Return a JSON array:
[
  {{
    "id": "insight_<number>",
    "title": "<Punchy, specific insight title>",
    "type": "<trend|opportunity|risk|performance|anomaly|benchmark>",
    "priority": "<Critical|High|Medium|Low>",
    "executive_summary": "<1-2 sentence headline with specific numbers>",
    "detailed_analysis": "<2-3 paragraph detailed analysis with data evidence>",
    "evidence": ["<specific data point 1>", "<specific data point 2>", "<specific data point 3>"],
    "recommendation": "<Specific, actionable recommendation for leadership>",
    "affected_kpis": ["<kpi_id1>", "<kpi_id2>"],
    "business_impact": "<Quantified or qualified business impact statement>",
    "confidence": "<High|Medium|Low>"
  }}
]
"""
