"""Prompt templates for the Power BI Dashboard Agent."""

DASHBOARD_SYSTEM = """You are a Power BI Solutions Architect and Executive Dashboard Designer. 
You create structured, actionable dashboard specifications that can be directly implemented 
by Power BI developers. Your designs follow Microsoft best practices and executive UX standards."""

DASHBOARD_PROMPT = """
Generate a complete Power BI dashboard specification for this business analytics solution.

## Business Context
- Domain: {business_domain}
- Target Audience: C-Suite Executives and Senior Managers

## Identified KPIs
{kpis_json}

## Key Insights
{insights_summary}

## Visualization Recommendations
{viz_summary}

## Available Columns
- Numeric: {numeric_columns}
- Categorical: {categorical_columns}
- Datetime: {datetime_columns}

Design a multi-page Power BI dashboard. Return a complete JSON specification:

{{
  "title": "<Dashboard Title>",
  "description": "<Dashboard purpose and scope>",
  "target_audience": "Executive Leadership",
  "global_filters": ["<filter1>", "<filter2>"],
  "data_refresh_frequency": "Daily",
  "executive_summary": "<2-3 paragraph executive summary of the dashboard's value>",
  "implementation_notes": ["<note1>", "<note2>"],
  "pages": [
    {{
      "page_name": "<Page Name>",
      "page_number": 1,
      "purpose": "<What business question does this page answer?>",
      "slicers": ["<slicer column>"],
      "kpi_cards": [
        {{
          "title": "<KPI Card Title>",
          "measure": "<DAX measure or column>",
          "format": "<currency|percentage|number|decimal>",
          "comparison": "<vs previous period or null>",
          "position": {{"row": 1, "col": 1, "width": 2, "height": 1}}
        }}
      ],
      "visuals": [
        {{
          "id": "visual_1",
          "title": "<Visual Title>",
          "chart_type": "<bar|line|pie|scatter|table|funnel|waterfall>",
          "x_axis": "<column>",
          "y_axis": "<column>",
          "legend": "<column or null>",
          "measures": ["<measure>"],
          "dimensions": ["<dimension>"],
          "filters": ["<filter>"],
          "drill_down": "<drill-down column or null>",
          "position": {{"row": 2, "col": 1, "width": 4, "height": 3}},
          "business_purpose": "<Decision this visual supports>"
        }}
      ],
      "theme": "Corporate"
    }}
  ]
}}

Create 3 pages: (1) Executive Overview, (2) Detailed Analysis, (3) Trends & Forecasting
"""
