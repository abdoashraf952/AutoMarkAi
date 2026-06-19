"""Insight Pydantic schemas."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Insight(BaseModel):
    id: str
    title: str
    type: str  # "trend", "opportunity", "risk", "performance", "anomaly", "benchmark"
    priority: str  # "Critical", "High", "Medium", "Low"
    executive_summary: str  # 1-2 sentence headline
    detailed_analysis: str  # full analysis paragraph
    evidence: list[str] = Field(default_factory=list)  # specific data points
    recommendation: str
    affected_kpis: list[str] = Field(default_factory=list)
    business_impact: Optional[str] = None
    confidence: str = "High"  # "High", "Medium", "Low"
