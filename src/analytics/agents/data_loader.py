"""Data Loader Agent: reads, validates, and summarizes the input dataset.

Supports two sources:
  - File upload (CSV / Excel): uses DataFrameService (existing)
  - SQL query / table: uses SQLSourceService (new, read-only)

Once a DataFrame is loaded it is cached in-process under a cache key so
that every downstream agent can retrieve it without re-reading.
"""
from __future__ import annotations

import os
import traceback

from src.analytics.schemas.state import AnalyticsState
from src.analytics.schemas.datasource import DataSource
from src.analytics.services.dataframe_service import DataFrameService
from src.analytics.services.sql_source_service import get_sql_source_service

_df_service = DataFrameService()

# In-process DataFrame cache; keyed by a stable identifier for the source.
# File path is used for file sources; "<source_label>" for SQL sources.
_DATAFRAME_CACHE: dict = {}


def data_loader_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node: loads the dataset from either a file or a SQL source,
    extracts a DatasetSummary, and caches the DataFrame for downstream agents.
    """
    try:
        source = state.data_source

        # ── SQL source path ───────────────────────────────────────────────────
        if source and source.kind == "sql":
            return _load_from_sql(source)

        # ── File source path (default / backward-compat) ──────────────────────
        return _load_from_file(state)

    except Exception as exc:
        return {
            "error_message": f"Data loading failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }


# ── Private helpers ───────────────────────────────────────────────────────────

def _load_from_file(state: AnalyticsState) -> dict:
    if not state.file_path or not os.path.exists(state.file_path):
        return {
            "error_message": f"File not found: {state.file_path}",
            "current_step": "error",
        }

    df = _df_service.load_file(state.file_path)
    summary = _df_service.extract_summary(df, state.file_name)
    _DATAFRAME_CACHE[state.file_path] = df

    return {
        "dataset_summary": summary,
        "current_step": "data_loaded",
        "error_message": None,
    }


def _load_from_sql(source: DataSource) -> dict:
    if not source.connection_url or not source.query:
        return {
            "error_message": "SQL source requires both connection_url and query.",
            "current_step": "error",
        }

    svc = get_sql_source_service()
    df, summary = svc.load(
        connection_url=source.connection_url,
        query_or_table=source.query,
        source_label=source.source_label,
    )
    _DATAFRAME_CACHE[source.source_label] = df

    return {
        "dataset_summary": summary,
        # Mirror file-source fields so downstream agents don't need to branch
        "file_name": source.source_label,
        "file_path": source.source_label,
        "current_step": "data_loaded",
        "error_message": None,
    }


# ── Public cache accessor ─────────────────────────────────────────────────────

def get_cached_dataframe(cache_key: str):
    """Retrieve the cached DataFrame by file path or SQL source label."""
    return _DATAFRAME_CACHE.get(cache_key)
