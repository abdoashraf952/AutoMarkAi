"""Repository layer: all database CRUD operations."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import (
    Session as SessionModel,
    Analysis,
    KPIRecord,
    InsightRecord,
    ChatMessage as ChatMessageModel,
)
from app.schemas import (
    AnalyticsState, KPI, Insight, ChatMessage
)


class AnalyticsRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Sessions ──────────────────────────────────────────────────────────────

    def get_or_create_session(self, session_id: str) -> SessionModel:
        obj = self.db.query(SessionModel).filter_by(id=session_id).first()
        if not obj:
            obj = SessionModel(id=session_id)
            self.db.add(obj)
            self.db.flush()
        return obj

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
            obj.dataset_summary = state.dataset_summary.model_dump()
        if state.profiling_result:
            obj.profiling_result = state.profiling_result.model_dump()
        obj.business_domain = state.business_domain
        obj.domain_confidence = state.domain_confidence
        obj.domain_reasoning = state.domain_reasoning
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

    # ── KPIs ──────────────────────────────────────────────────────────────────

    def save_kpis(self, analysis_id: str, kpis: list[KPI]) -> None:
        # Delete existing
        self.db.query(KPIRecord).filter_by(analysis_id=analysis_id).delete()
        for kpi in kpis:
            record = KPIRecord(
                id=kpi.id,
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
                raw_data=kpi.model_dump(),
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
                id=insight.id,
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
                raw_data=insight.model_dump(),
            )
            self.db.add(record)
        self.db.flush()

    def get_insights(self, analysis_id: str) -> list[Insight]:
        records = self.db.query(InsightRecord).filter_by(analysis_id=analysis_id).all()
        return [Insight(**r.raw_data) for r in records]

    # ── Chat Messages ─────────────────────────────────────────────────────────

    def save_message(self, session_id: str, message: ChatMessage, analysis_id: Optional[str] = None) -> None:
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
                timestamp=r.timestamp.isoformat(),
            )
            for r in records
        ]
