"""DataFrame loading and processing service."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from app.schemas.dataset import DatasetSummary


class DataFrameService:
    """Handles loading, validation, and basic processing of uploaded datasets."""

    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
    MAX_SAMPLE_ROWS = 5

    def load_file(self, file_path: str) -> pd.DataFrame:
        """Load a CSV or Excel file into a DataFrame."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}. Supported: {self.SUPPORTED_EXTENSIONS}")

        if ext == ".csv":
            df = pd.read_csv(file_path, low_memory=False)
        else:
            df = pd.read_excel(file_path)

        return df

    def extract_summary(self, df: pd.DataFrame, file_name: str) -> DatasetSummary:
        """Build a serializable DatasetSummary from a DataFrame."""
        sample = df.head(self.MAX_SAMPLE_ROWS).replace({np.nan: None})
        sample_rows = sample.to_dict(orient="records")

        return DatasetSummary(
            file_name=file_name,
            row_count=len(df),
            column_count=len(df.columns),
            columns=list(df.columns),
            dtypes={col: str(df[col].dtype) for col in df.columns},
            memory_usage_mb=round(df.memory_usage(deep=True).sum() / (1024 * 1024), 3),
            sample_rows=sample_rows,
        )

    def clean_for_serialization(self, obj):
        """Recursively replace numpy/nan types for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self.clean_for_serialization(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.clean_for_serialization(v) for v in obj]
        if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
            return None
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return obj
