"""Central LangGraph state schema."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator
from app.schemas.dataset import DatasetSummary, ProfilingResult
from app.schemas.kpi import KPI
from app.schemas.insight import Insight
from app.schemas.chat import ChatMessage
from app.schemas.datasource import DataSource


class AnalyticsState(BaseModel):
    """
    Central state object passed through the LangGraph workflow.
    LangGraph stores state as plain dicts; this model coerces nested dicts
    back into typed Pydantic models on construction.
    """

    # Session
    session_id: str = ""
    analysis_id: Optional[str] = None

    # Data source (file upload or SQL query)
    data_source: Optional[DataSource] = None

    # User input
    user_query: str = ""
    follow_up_query: Optional[str] = None

    # File info (kept for backward compat with file-upload path)
    file_name: str = ""
    file_path: str = ""
    file_size_bytes: int = 0

    # Data (serializable summaries only — no raw DataFrames)
    dataset_summary: Optional[DatasetSummary] = None
    profiling_result: Optional[ProfilingResult] = None

    # Business context
    business_domain: str = ""
    domain_confidence: float = 0.0
    domain_reasoning: str = ""

    # Outputs
    kpis: list[KPI] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    visualization_recommendations: list[dict[str, Any]] = Field(default_factory=list)

    # Conversation
    chat_history: list[ChatMessage] = Field(default_factory=list)

    # Workflow control
    current_step: str = "start"
    error_message: Optional[str] = None
    is_follow_up: bool = False

    # Generated report
    executive_report: Optional[str] = None
    report_generated_at: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="before")
    @classmethod
    def coerce_nested(cls, values: Any) -> Any:
        """Coerce dict → typed model for nested fields that LangGraph serialises as dicts."""
        if not isinstance(values, dict):
            return values

        # data_source
        ds_raw = values.get("data_source")
        if isinstance(ds_raw, dict):
            values["data_source"] = DataSource(**ds_raw)

        # dataset_summary
        ds = values.get("dataset_summary")
        if isinstance(ds, dict):
            values["dataset_summary"] = DatasetSummary(**ds)

        # profiling_result
        pr = values.get("profiling_result")
        if isinstance(pr, dict):
            values["profiling_result"] = ProfilingResult(**pr)

        # kpis
        kpis = values.get("kpis", [])
        values["kpis"] = [KPI(**k) if isinstance(k, dict) else k for k in kpis]

        # insights
        insights = values.get("insights", [])
        values["insights"] = [Insight(**i) if isinstance(i, dict) else i for i in insights]

        # chat_history
        history = values.get("chat_history", [])
        values["chat_history"] = [ChatMessage(**m) if isinstance(m, dict) else m for m in history]

        return values
