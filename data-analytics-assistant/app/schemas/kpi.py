"""KPI Pydantic schemas."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class KPI(BaseModel):
    id: str
    name: str
    business_definition: str
    formula: Optional[str] = None
    required_columns: list[str] = Field(default_factory=list)
    priority: str  # "Critical", "High", "Medium", "Low"
    category: str  # "Revenue", "Operations", "Customer", "Financial", "HR", etc.
    why_important: str
    current_value: Optional[str] = None
    unit: Optional[str] = None
    trend_direction: Optional[str] = None  # "up", "down", "stable", "unknown"
    benchmark: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_str_fields(cls, data: Any) -> Any:
        """Coerce numeric LLM outputs to str before Pydantic validates field types."""
        if not isinstance(data, dict):
            return data
        for field in ("current_value", "unit", "trend_direction", "benchmark", "formula"):
            v = data.get(field)
            if v is not None and not isinstance(v, str):
                data[field] = str(v)
        return data
