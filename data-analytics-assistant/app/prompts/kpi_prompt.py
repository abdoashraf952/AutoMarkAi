"""Prompt templates for the KPI Discovery Agent."""

KPI_SYSTEM = """You are a Chief Analytics Officer with expertise in defining business KPIs across 
all major industries. You identify the most impactful, measurable, and actionable KPIs that 
drive business decision-making."""

KPI_PROMPT = """
Identify the most relevant KPIs for this business dataset.

## Business Context
- Domain: {business_domain}
- Business Context: {business_context}
- Key Entities: {key_entities}

## Available Columns
{column_details}

## Numeric Columns Available
{numeric_columns}

## Categorical Columns Available
{categorical_columns}

## Datetime Columns Available
{datetime_columns}

## Statistical Highlights
{stats_highlights}

Generate 6-10 specific, measurable KPIs that:
1. Can be computed from the available columns
2. Are directly relevant to the {business_domain} domain
3. Provide actionable business intelligence
4. Cover different priority levels

Return a JSON array of KPI objects:
[
  {{
    "id": "kpi_<unique_number>",
    "name": "<KPI Name>",
    "business_definition": "<Clear 1-2 sentence definition>",
    "formula": "<Mathematical formula using column names, or null>",
    "required_columns": ["<col1>", "<col2>"],
    "priority": "<Critical|High|Medium|Low>",
    "category": "<Revenue|Operations|Customer|Financial|HR|Quality|Growth>",
    "why_important": "<Why executives should care about this KPI>",
    "current_value": "<Computed value from data if possible, else null>",
    "unit": "<$|%|units|ratio|null>",
    "trend_direction": "<up|down|stable|unknown>",
    "benchmark": "<Industry benchmark or target, if known>"
  }}
]
"""
