"""Repository layer: all analytics database CRUD operations.

Operates on the shared models (src/shared/models.py) through a sync SQLAlchemy
session, because the analytics agents and pandas both run synchronously.

Sessions carry an optional `user_id` so an authenticated caller only ever sees
their own analyses; rows created before auth existed keep a NULL user_id.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.analytics.schemas import AnalyticsState, ChatMessage, Insight, KPI
from src.shared.models import (
    Analysis,
    AnalyticsSession,
    ChatMessage as ChatMessageModel,
    InsightRecord,
    KPIRecord,
)


def _scoped_id(analysis_id: str, model_id: str) -> str:
    """Namespace a per-analysis model id so it is unique across analyses.

    Truncated to the column width (36) with a hash tail, so long ids stay
    unique rather than colliding after a plain cut.
    """
    raw = f"{analysis_id}:{model_id}"
    if len(raw) <= 36:
        return raw
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{raw[:27]}:{digest}"


class AnalyticsRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Sessions ──────────────────────────────────────────────────────────────

    def get_or_create_session(
        self, session_id: str, user_id: Optional[str] = None
    ) -> AnalyticsSession:
        obj = self.db.query(AnalyticsSession).filter_by(id=session_id).first()
        if not obj:
            obj = AnalyticsSession(id=session_id, user_id=user_id)
            self.db.add(obj)
            self.db.flush()
        elif user_id and obj.user_id is None:
            # Claim a pre-auth session for the now-authenticated user.
            obj.user_id = user_id
            self.db.flush()
        return obj

    def get_user_sessions(self, user_id: str) -> list[AnalyticsSession]:
        return (
            self.db.query(AnalyticsSession)
            .filter_by(user_id=user_id)
            .order_by(AnalyticsSession.created_at.desc())
            .all()
        )

    # ── Analysis ──────────────────────────────────────────────────────────────

    def create_analysis(self, state: AnalyticsState) -> Analysis:
        analysis_id = str(uuid.uuid4())
        obj = Analysis(
            id=analysis_id,
            session_id=state.session_id,
            file_name=state.file_name,
            file_path=state.file_path,
            file_size_bytes=state.file_size_bytes,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def update_analysis(self, analysis_id: str, state: AnalyticsState) -> None:
        obj = self.db.query(Analysis).filter_by(id=analysis_id).first()
        if not obj:
            return
        if state.dataset_summary:
            obj.dataset_summary = state.dataset_summary.model_dump(mode="json")
        if state.profiling_result:
            obj.profiling_result = state.profiling_result.model_dump(mode="json")
        obj.business_domain = state.business_domain
        obj.domain_confidence = state.domain_confidence
        obj.domain_reasoning = state.domain_reasoning
        if getattr(state, "executive_report", None):
            obj.executive_report = state.executive_report
        # The state field is `visualization_recommendations`; the column is
        # `visualizations`. They are deliberately named differently, so read
        # the state attribute explicitly rather than by the column name.
        recommendations = getattr(state, "visualization_recommendations", None)
        if recommendations:
            obj.visualizations = [
                v.model_dump(mode="json") if hasattr(v, "model_dump") else v
                for v in recommendations
            ]
        self.db.flush()

    def get_analysis(self, analysis_id: str) -> Optional[Analysis]:
        return self.db.query(Analysis).filter_by(id=analysis_id).first()

    def get_session_analyses(self, session_id: str) -> list[Analysis]:
        return (
            self.db.query(Analysis)
            .filter_by(session_id=session_id)
            .order_by(Analysis.created_at.desc())
            .all()
        )

    def owns_analysis(self, analysis_id: str, user_id: str) -> bool:
        """True if `analysis_id` belongs to a session owned by `user_id`."""
        return (
            self.db.query(Analysis)
            .join(AnalyticsSession, Analysis.session_id == AnalyticsSession.id)
            .filter(Analysis.id == analysis_id, AnalyticsSession.user_id == user_id)
            .first()
            is not None
        )

    # ── KPIs ──────────────────────────────────────────────────────────────────

    def save_kpis(self, analysis_id: str, kpis: list[KPI]) -> None:
        self.db.query(KPIRecord).filter_by(analysis_id=analysis_id).delete()
        for kpi in kpis:
            record = KPIRecord(
                # The model's own id is only unique within one analysis — the
                # LLM reliably emits "kpi_01", "kpi_02", … so reusing it as the
                # table's primary key collides on the user's second analysis.
                # The original id is preserved in raw_data, which get_kpis()
                # rebuilds from, so callers still see the model's own id.
                id=_scoped_id(analysis_id, kpi.id),
                analysis_id=analysis_id,
                name=kpi.name,
                business_definition=kpi.business_definition,
                formula=kpi.formula,
                required_columns=kpi.required_columns,
                priority=kpi.priority,
                category=kpi.category,
                why_important=kpi.why_important,
                current_value=kpi.current_value,
                unit=kpi.unit,
                trend_direction=kpi.trend_direction,
                raw_data=kpi.model_dump(mode="json"),
            )
            self.db.add(record)
        self.db.flush()

    def get_kpis(self, analysis_id: str) -> list[KPI]:
        records = self.db.query(KPIRecord).filter_by(analysis_id=analysis_id).all()
        return [KPI(**r.raw_data) for r in records]

    # ── Insights ──────────────────────────────────────────────────────────────

    def save_insights(self, analysis_id: str, insights: list[Insight]) -> None:
        self.db.query(InsightRecord).filter_by(analysis_id=analysis_id).delete()
        for insight in insights:
            record = InsightRecord(
                # Scoped for the same reason as KPI ids — see save_kpis.
                id=_scoped_id(analysis_id, insight.id),
                analysis_id=analysis_id,
                title=insight.title,
                type=insight.type,
                priority=insight.priority,
                executive_summary=insight.executive_summary,
                detailed_analysis=insight.detailed_analysis,
                evidence=insight.evidence,
                recommendation=insight.recommendation,
                affected_kpis=insight.affected_kpis,
                business_impact=insight.business_impact,
                confidence=insight.confidence,
                raw_data=insight.model_dump(mode="json"),
            )
            self.db.add(record)
        self.db.flush()

    def get_insights(self, analysis_id: str) -> list[Insight]:
        records = self.db.query(InsightRecord).filter_by(analysis_id=analysis_id).all()
        return [Insight(**r.raw_data) for r in records]

    # ── Chat Messages ─────────────────────────────────────────────────────────

    def save_message(
        self, session_id: str, message: ChatMessage, analysis_id: Optional[str] = None
    ) -> None:
        record = ChatMessageModel(
            id=str(uuid.uuid4()),
            session_id=session_id,
            analysis_id=analysis_id,
            role=message.role,
            content=message.content,
            message_type=message.message_type,
            message_metadata=message.metadata,
        )
        self.db.add(record)
        self.db.flush()

    def get_chat_history(self, session_id: str, limit: int = 50) -> list[ChatMessage]:
        records = (
            self.db.query(ChatMessageModel)
            .filter_by(session_id=session_id)
            .order_by(ChatMessageModel.timestamp.asc())
            .limit(limit)
            .all()
        )
        return [
            ChatMessage(
                role=r.role,
                content=r.content,
                message_type=r.message_type,
                metadata=r.message_metadata,
                timestamp=r.timestamp.isoformat() if r.timestamp else None,
            )
            for r in records
        ]
