"""Power BI Dashboard Pydantic schemas."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class KPICard(BaseModel):
    title: str
    measure: str
    format: str  # "currency", "percentage", "number", "decimal"
    comparison: Optional[str] = None  # e.g., "vs previous period"
    position: dict[str, int] = Field(default_factory=dict)  # {row, col, width, height}


class Visual(BaseModel):
    id: str
    title: str
    chart_type: str  # "bar", "line", "pie", "scatter", "table", "funnel", "waterfall"
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    legend: Optional[str] = None
    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    drill_down: Optional[str] = None
    position: dict[str, int] = Field(default_factory=dict)
    business_purpose: str = ""


class DashboardPage(BaseModel):
    page_name: str
    page_number: int
    purpose: str
    kpi_cards: list[KPICard] = Field(default_factory=list)
    visuals: list[Visual] = Field(default_factory=list)
    slicers: list[str] = Field(default_factory=list)
    theme: str = "Corporate"


class DashboardSpec(BaseModel):
    title: str
    description: str
    target_audience: str
    pages: list[DashboardPage] = Field(default_factory=list)
    global_filters: list[str] = Field(default_factory=list)
    data_refresh_frequency: str = "Daily"
    executive_summary: str = ""
    implementation_notes: list[str] = Field(default_factory=list)
    raw_spec: dict[str, Any] = Field(default_factory=dict)
