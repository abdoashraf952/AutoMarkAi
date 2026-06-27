"""Statistical analysis service for dataset profiling."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.schemas.dataset import ColumnProfile, ProfilingResult, DatasetSummary


class StatisticsService:
    """Computes detailed statistical profiles for DataFrame columns."""

    MAX_SAMPLE_VALUES = 5
    MAX_TOP_CATEGORIES = 10

    def profile_dataframe(self, df: pd.DataFrame, summary: DatasetSummary) -> ProfilingResult:
        """Build a full ProfilingResult from a DataFrame."""
        column_profiles = [self._profile_column(df, col) for col in df.columns]

        numeric_cols = [p.name for p in column_profiles if p.inferred_type == "numeric"]
        categorical_cols = [p.name for p in column_profiles if p.inferred_type == "categorical"]
        datetime_cols = [p.name for p in column_profiles if p.inferred_type == "datetime"]
        text_cols = [p.name for p in column_profiles if p.inferred_type == "text"]

        total_cells = df.shape[0] * df.shape[1]
        total_missing = df.isnull().sum().sum()
        total_missing_pct = round(float(total_missing / total_cells * 100), 2) if total_cells > 0 else 0.0
        duplicate_count = int(df.duplicated().sum())

        quality_issues = []
        if total_missing_pct > 20:
            quality_issues.append(f"High missing data rate: {total_missing_pct:.1f}%")
        if duplicate_count > 0:
            quality_issues.append(f"{duplicate_count} duplicate rows detected")
        high_null_cols = [p.name for p in column_profiles if p.null_pct > 50]
        if high_null_cols:
            quality_issues.append(f"Columns >50% null: {', '.join(high_null_cols)}")

        quality_score = max(0.0, 100.0 - total_missing_pct - (duplicate_count / max(len(df), 1) * 10))

        return ProfilingResult(
            dataset_summary=summary,
            column_profiles=column_profiles,
            total_missing_pct=total_missing_pct,
            duplicate_row_count=duplicate_count,
            numeric_columns=numeric_cols,
            categorical_columns=categorical_cols,
            datetime_columns=datetime_cols,
            text_columns=text_cols,
            data_quality_score=round(quality_score, 1),
            quality_issues=quality_issues,
        )

    def _profile_column(self, df: pd.DataFrame, col: str) -> ColumnProfile:
        series = df[col]
        null_count = int(series.isnull().sum())
        null_pct = round(float(null_count / len(series) * 100), 2) if len(series) > 0 else 0.0
        unique_count = int(series.nunique())
        unique_pct = round(float(unique_count / len(series) * 100), 2) if len(series) > 0 else 0.0

        inferred_type = self._infer_type(series)
        sample_values = [v for v in series.dropna().head(self.MAX_SAMPLE_VALUES).tolist()]
        sample_values = [self._safe_val(v) for v in sample_values]

        profile = ColumnProfile(
            name=col,
            dtype=str(series.dtype),
            inferred_type=inferred_type,
            null_count=null_count,
            null_pct=null_pct,
            unique_count=unique_count,
            unique_pct=unique_pct,
            sample_values=sample_values,
        )

        if inferred_type == "numeric":
            numeric = pd.to_numeric(series, errors="coerce").dropna()
            if len(numeric) > 0:
                profile.mean = self._safe_val(float(numeric.mean()))
                profile.median = self._safe_val(float(numeric.median()))
                profile.std = self._safe_val(float(numeric.std()))
                profile.min_val = self._safe_val(float(numeric.min()))
                profile.max_val = self._safe_val(float(numeric.max()))
                profile.q25 = self._safe_val(float(numeric.quantile(0.25)))
                profile.q75 = self._safe_val(float(numeric.quantile(0.75)))

        elif inferred_type == "categorical":
            top = series.value_counts().head(self.MAX_TOP_CATEGORIES)
            profile.top_categories = [
                {"value": str(k), "count": int(v), "pct": round(float(v / len(series) * 100), 1)}
                for k, v in top.items()
            ]

        return profile

    @staticmethod
    def _infer_type(series: pd.Series) -> str:
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"
        if pd.api.types.is_bool_dtype(series):
            return "boolean"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        # Try parsing as datetime
        sample = series.dropna().head(20)
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pd.to_datetime(sample, infer_datetime_format=False, format="mixed")
            return "datetime"
        except Exception:
            pass
        # High cardinality → text; low cardinality → categorical
        if series.nunique() / max(len(series), 1) > 0.5:
            return "text"
        return "categorical"

    @staticmethod
    def _safe_val(v: Any) -> Any:
        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            return None
        return v
