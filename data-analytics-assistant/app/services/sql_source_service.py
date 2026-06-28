"""Read-only SQL → DataFrame bridge.

Accepts either a whitelisted table name or a single SELECT statement.
Connects with a per-request SQLAlchemy engine, enforces a row cap and
statement timeout, then discards the connection. No rows are persisted
beyond the in-process DataFrame cache.
"""
from __future__ import annotations

import re
import pandas as pd
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine

from app.schemas.dataset import DatasetSummary

# ── Safety limits ─────────────────────────────────────────────────────────────
MAX_ROWS: int = 100_000
STATEMENT_TIMEOUT_MS: int = 30_000          # 30 s for PostgreSQL
_READ_ONLY_RE = re.compile(
    r"^\s*SELECT\b", re.IGNORECASE | re.MULTILINE
)
_DANGEROUS_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|EXEC|EXECUTE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _validate_query(sql: str) -> None:
    """Raise ValueError if the SQL is not a plain SELECT."""
    stripped = sql.strip().rstrip(";")
    if not _READ_ONLY_RE.match(stripped):
        raise ValueError("Only SELECT statements are allowed as SQL sources.")
    if _DANGEROUS_RE.search(stripped):
        raise ValueError("SQL source contains disallowed keywords.")


def _build_limited_query(sql: str) -> str:
    """Wrap the user query in a subquery with a hard row cap."""
    inner = sql.strip().rstrip(";")
    return f"SELECT * FROM ({inner}) AS _src LIMIT {MAX_ROWS}"


def _set_pg_timeout(connection, _record):
    """Set statement_timeout on every new PostgreSQL connection."""
    try:
        connection.execute(
            text(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
        )
    except Exception:
        pass  # non-PostgreSQL drivers may not support this; ignore


class SQLSourceService:
    """
    Loads a pandas DataFrame from a read-only SQL query or table name.

    Usage
    -----
    svc = SQLSourceService()
    df, summary = svc.load(
        connection_url="postgresql://reader:pass@host:5432/db",
        query_or_table="sales_data",          # table name
    )
    # — or —
    df, summary = svc.load(
        connection_url="...",
        query_or_table="SELECT * FROM sales_data WHERE year = 2024",
    )
    """

    def load(
        self,
        connection_url: str,
        query_or_table: str,
        source_label: str = "sql_source",
    ) -> tuple[pd.DataFrame, DatasetSummary]:
        """
        Return (DataFrame, DatasetSummary) from a read-only SQL source.

        Parameters
        ----------
        connection_url : str
            SQLAlchemy connection URL. Credentials are supplied per-request
            and not stored after this call returns.
        query_or_table : str
            Either a bare table name (letters, digits, underscores, optional
            schema prefix) or a SELECT statement.
        source_label : str
            Human-readable name used as the DatasetSummary file_name.
        """
        sql = self._resolve_to_select(query_or_table)
        _validate_query(sql)
        limited_sql = _build_limited_query(sql)

        engine = create_engine(
            connection_url,
            pool_pre_ping=True,
            # NullPool: discard connection immediately after use
            poolclass=__import__(
                "sqlalchemy.pool", fromlist=["NullPool"]
            ).NullPool,
        )
        # Register timeout hook for PostgreSQL
        event.listen(engine, "connect", _set_pg_timeout)

        try:
            with engine.connect() as conn:
                df = pd.read_sql(text(limited_sql), conn)
        finally:
            engine.dispose()

        if df.empty:
            raise ValueError("SQL query returned no rows.")

        summary = self._extract_summary(df, source_label)
        return df, summary

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_to_select(query_or_table: str) -> str:
        """If input looks like a bare table name, wrap it in SELECT *."""
        stripped = query_or_table.strip()
        # A bare table name: only word chars and dots (schema.table)
        if re.match(r"^[\w\.]+$", stripped):
            return f"SELECT * FROM {stripped}"
        return stripped

    @staticmethod
    def _extract_summary(df: pd.DataFrame, source_label: str) -> DatasetSummary:
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        sample_rows = []
        for row in df.head(5).to_dict(orient="records"):
            clean = {
                k: (None if (isinstance(v, float) and (v != v)) else v)
                for k, v in row.items()
            }
            sample_rows.append(clean)

        return DatasetSummary(
            file_name=source_label,
            row_count=len(df),
            column_count=len(df.columns),
            columns=list(df.columns),
            dtypes=dtypes,
            memory_usage_mb=round(
                df.memory_usage(deep=True).sum() / (1024 ** 2), 3
            ),
            sample_rows=sample_rows,
        )


# ── Module-level singleton ────────────────────────────────────────────────────
_instance: SQLSourceService | None = None


def get_sql_source_service() -> SQLSourceService:
    global _instance
    if _instance is None:
        _instance = SQLSourceService()
    return _instance
