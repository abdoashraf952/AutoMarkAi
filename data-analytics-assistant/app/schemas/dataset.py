"""Dataset and profiling Pydantic schemas."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    inferred_type: str  # "numeric", "categorical", "datetime", "text", "boolean"
    null_count: int
    null_pct: float
    unique_count: int
    unique_pct: float
    sample_values: list[Any] = Field(default_factory=list)
    # Numeric stats
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    q25: Optional[float] = None
    q75: Optional[float] = None
    # Categorical stats
    top_categories: list[dict[str, Any]] = Field(default_factory=list)


class DatasetSummary(BaseModel):
    file_name: str
    row_count: int
    column_count: int
    columns: list[str]
    dtypes: dict[str, str]
    memory_usage_mb: float
    has_header: bool = True
    encoding: str = "utf-8"
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)  # first 5 rows


class ProfilingResult(BaseModel):
    dataset_summary: DatasetSummary
    column_profiles: list[ColumnProfile] = Field(default_factory=list)
    total_missing_pct: float
    duplicate_row_count: int
    numeric_columns: list[str] = Field(default_factory=list)
    categorical_columns: list[str] = Field(default_factory=list)
    datetime_columns: list[str] = Field(default_factory=list)
    text_columns: list[str] = Field(default_factory=list)
    data_quality_score: float  # 0-100
    quality_issues: list[str] = Field(default_factory=list)
    profiling_narrative: str = ""
