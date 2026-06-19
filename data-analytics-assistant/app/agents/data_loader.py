"""Data Loader Agent: reads, validates, and summarizes uploaded files."""
from __future__ import annotations

import os
import traceback

from app.schemas.state import AnalyticsState
from app.services.dataframe_service import DataFrameService

_df_service = DataFrameService()

# In-process DataFrame cache (keyed by file_path); avoids re-reading on follow-ups
_DATAFRAME_CACHE: dict = {}


def data_loader_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node: loads the uploaded file, extracts a DatasetSummary,
    and caches the DataFrame in-memory for downstream agents.
    """
    try:
        if not state.file_path or not os.path.exists(state.file_path):
            return {"error_message": f"File not found: {state.file_path}", "current_step": "error"}

        df = _df_service.load_file(state.file_path)
        summary = _df_service.extract_summary(df, state.file_name)

        # Cache DataFrame for other agents in this process
        _DATAFRAME_CACHE[state.file_path] = df

        return {
            "dataset_summary": summary,
            "current_step": "data_loaded",
            "error_message": None,
        }

    except Exception as exc:
        return {
            "error_message": f"Data loading failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }


def get_cached_dataframe(file_path: str):
    """Retrieve the cached DataFrame for a given file path."""
    return _DATAFRAME_CACHE.get(file_path)
