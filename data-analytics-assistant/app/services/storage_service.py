"""Storage service: persists analysis results to PostgreSQL."""
from __future__ import annotations

from typing import Optional

from app.database.connection import get_db
from app.database.repository import AnalyticsRepository
from app.schemas import AnalyticsState, KPI, Insight, ChatMessage


class StorageService:
    """High-level service for persisting and retrieving analytics artifacts."""

    def ensure_session(self, session_id: str) -> None:
        with get_db() as db:
            repo = AnalyticsRepository(db)
            repo.get_or_create_session(session_id)

    def create_analysis(self, state: AnalyticsState) -> str:
        with get_db() as db:
            repo = AnalyticsRepository(db)
            repo.get_or_create_session(state.session_id)
            analysis = repo.create_analysis(state)
            return analysis.id

    def update_analysis(self, analysis_id: str, state: AnalyticsState) -> None:
        with get_db() as db:
            repo = AnalyticsRepository(db)
            repo.update_analysis(analysis_id, state)

    def save_kpis(self, analysis_id: str, kpis: list[KPI]) -> None:
        with get_db() as db:
            repo = AnalyticsRepository(db)
            repo.save_kpis(analysis_id, kpis)

    def save_insights(self, analysis_id: str, insights: list[Insight]) -> None:
        with get_db() as db:
            repo = AnalyticsRepository(db)
            repo.save_insights(analysis_id, insights)

    def save_message(self, session_id: str, message: ChatMessage, analysis_id: Optional[str] = None) -> None:
        with get_db() as db:
            repo = AnalyticsRepository(db)
            repo.save_message(session_id, message, analysis_id)

    def get_chat_history(self, session_id: str, limit: int = 50) -> list[ChatMessage]:
        with get_db() as db:
            repo = AnalyticsRepository(db)
            return repo.get_chat_history(session_id, limit)

    def get_session_analyses(self, session_id: str):
        with get_db() as db:
            repo = AnalyticsRepository(db)
            return repo.get_session_analyses(session_id)
