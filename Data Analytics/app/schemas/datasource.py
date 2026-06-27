"""DataSource descriptor — describes where the input data comes from."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel


class DataSource(BaseModel):
    """
    Describes the origin of the dataset fed into the analytics pipeline.

    kind="file"  → file_path is set; connection_url and query are None.
    kind="sql"   → connection_url and query are set; file_path is None.
    """
    kind: Literal["file", "sql"] = "file"

    # File source
    file_path: Optional[str] = None
    file_name: Optional[str] = None

    # SQL source
    connection_url: Optional[str] = None
    query: Optional[str] = None
    source_label: str = "sql_source"
