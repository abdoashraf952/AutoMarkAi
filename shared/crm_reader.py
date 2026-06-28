"""
shared/crm_reader.py — load CRM tables as pandas DataFrames for Analytics.

Usage (inside Analytics agents or Streamlit):

    from shared.crm_reader import load_crm_table, CRM_TABLE_NAMES

    df = load_crm_table("leads")           # returns pd.DataFrame
    df = load_crm_table("conversations")
    df = load_crm_table("escalations")
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

CRM_TABLE_NAMES = ["leads", "conversations", "escalations"]

# Human-readable descriptions shown in the Analytics UI
CRM_TABLE_INFO = {
    "leads": "Lead profiles — scores, budgets, contact info collected by the CRM agent",
    "conversations": "Conversation memory — summary, message count, escalation status per user",
    "escalations": "Human handoff records — reason, priority, open/closed status",
}


def _get_engine():
    url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/automark")
    return create_engine(url, pool_pre_ping=True)


def load_crm_table(table: str, limit: int = 10_000) -> pd.DataFrame:
    """
    Load a CRM table from the shared automark database as a DataFrame.

    Parameters
    ----------
    table : one of 'leads', 'conversations', 'escalations'
    limit : maximum rows to load (default 10 000)

    Returns
    -------
    pd.DataFrame  (empty on error)
    """
    if table not in CRM_TABLE_NAMES:
        raise ValueError(f"Unknown CRM table '{table}'. Choose from {CRM_TABLE_NAMES}")

    engine = _get_engine()
    query = text(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT :lim")  # noqa: S608
    try:
        with engine.connect() as conn:
            return pd.read_sql(query, conn, params={"lim": limit})
    except Exception as exc:
        raise RuntimeError(f"Failed to load CRM table '{table}': {exc}") from exc
    finally:
        engine.dispose()


def crm_table_summary() -> dict[str, dict]:
    """Return row counts and latest update for each CRM table (for dashboard display)."""
    engine = _get_engine()
    summary: dict[str, dict] = {}
    try:
        with engine.connect() as conn:
            for tbl in CRM_TABLE_NAMES:
                result = conn.execute(
                    text(f"SELECT COUNT(*) as n, MAX(updated_at) as latest FROM {tbl}")  # noqa: S608
                ).fetchone()
                summary[tbl] = {
                    "rows":   result[0] if result else 0,
                    "latest": str(result[1])[:19] if result and result[1] else "—",
                    "info":   CRM_TABLE_INFO[tbl],
                }
    except Exception:
        for tbl in CRM_TABLE_NAMES:
            summary[tbl] = {"rows": 0, "latest": "—", "info": CRM_TABLE_INFO[tbl]}
    finally:
        engine.dispose()
    return summary
