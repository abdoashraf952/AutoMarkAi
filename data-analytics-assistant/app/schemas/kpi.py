"""KPI Pydantic schemas."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class KPI(BaseModel):
    id: str
    name: str
    business_definition: str
    formula: Optional[str] = None
    required_columns: list[str] = Field(default_factory=list)
    priority: str  # "Critical", "High", "Medium", "Low"
    category: str  # "Revenue", "Operations", "Customer", "Financial", "HR", etc.
    why_important: str
    current_value: Optional[str] = None  # computed from data if possible
    unit: Optional[str] = None
    trend_direction: Optional[str] = None  # "up", "down", "stable", "unknown"
    benchmark: Optional[str] = None
