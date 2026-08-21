"""
src/shared/models.py — AutoMark AI (unified)

Every table in the AutoMark database, across all three modules, declared on a
single SQLAlchemy `Base`. This is what makes "one database, one init" possible:
`shared.db.init_all()` creates the pgvector extension and then emits this whole
metadata in one pass.

Table groups
------------
identity   : users                                  (app-wide login)
crm        : conversations, leads, escalations, document_chunks
campaigns  : campaigns
analytics  : sessions, analyses, kpis, insights, chat_messages

Column semantics are carried over verbatim from the three original schemas
(CRM/scripts/init_db.sql, campaigns' inline DDL, analytics' ORM models) so no
data migration is required beyond pointing every module at one URL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, relationship

from src.config import settings


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ═════════════════════════════════════════════════════════════════════════════
# Identity — shared by every module
# ═════════════════════════════════════════════════════════════════════════════

class User(Base):
    """Application account. Originally campaign-only; now the app-wide identity."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email = Column(Text, nullable=False, unique=True)
    pw_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    campaigns = relationship("Campaign", back_populates="user", cascade="all, delete-orphan")
    analytics_sessions = relationship(
        "AnalyticsSession", back_populates="user", cascade="all, delete-orphan"
    )


# ═════════════════════════════════════════════════════════════════════════════
# CRM
# ═════════════════════════════════════════════════════════════════════════════

class Conversation(Base):
    """Rolling-summary conversation memory — one row per end user."""

    __tablename__ = "conversations"

    user_id = Column(Text, primary_key=True)
    source = Column(Text, nullable=False, server_default="unknown")
    status = Column(Text, nullable=False, server_default="active")
    summary = Column(Text)
    messages = Column(JSONB, nullable=False, server_default="[]")
    message_count = Column(Integer, nullable=False, server_default="0")
    summarization_cycles = Column(Integer, nullable=False, server_default="0")
    summary_updated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    lead = relationship(
        "Lead", back_populates="conversation", uselist=False, cascade="all, delete-orphan"
    )
    escalations = relationship(
        "Escalation", back_populates="conversation", cascade="all, delete-orphan"
    )


class Lead(Base):
    """Progressively-collected lead qualification data."""

    __tablename__ = "leads"

    user_id = Column(
        Text,
        ForeignKey("conversations.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    name = Column(Text)
    email = Column(Text)
    phone = Column(Text)
    budget = Column(Text)
    authority = Column(Text)
    engagement_level = Column(Integer)
    interest_level = Column(Integer)
    pain_points = Column(JSONB, nullable=False, server_default="[]")
    lead_score = Column(Integer)
    lead_temperature = Column(Text)
    hubspot_contact_id = Column(Text)
    hubspot_deal_id = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    conversation = relationship("Conversation", back_populates="lead")


class Escalation(Base):
    """Human-handoff record."""

    __tablename__ = "escalations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        Text,
        ForeignKey("conversations.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason = Column(Text, nullable=False)
    priority = Column(Text, nullable=False, server_default="medium")
    status = Column(Text, nullable=False, server_default="open")
    hubspot_note_id = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    conversation = relationship("Conversation", back_populates="escalations")


class DocumentChunk(Base):
    """Hybrid RAG store — dense pgvector embedding + sparse full-text vector.

    `ts_content` is a stored generated column and `embedding` carries an HNSW
    cosine index, exactly as in the original init_db.sql. Both are declared here
    so create_all() reproduces the hand-written DDL bit for bit.
    """

    __tablename__ = "document_chunks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    doc_id = Column(Text, nullable=False)
    source_file = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False, server_default="0")
    embedding = Column(Vector(settings.EMBEDDING_DIM))
    ts_content = Column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
    )
    doc_metadata = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("uq_document_chunks_doc_chunk", "doc_id", "chunk_index", unique=True),
        Index(
            "idx_document_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "idx_document_chunks_ts_content",
            "ts_content",
            postgresql_using="gin",
        ),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Campaigns
# ═════════════════════════════════════════════════════════════════════════════

class Campaign(Base):
    """One row per campaign session; updated at start and at publish."""

    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id = Column(Text, nullable=False, unique=True)
    compound_name = Column(Text)
    status = Column(Text, nullable=False, server_default="draft")
    budget = Column(Float)
    language = Column(Text)
    meta_campaign_id = Column(Text)
    meta_adset_id = Column(Text)
    meta_creative_id = Column(Text)
    meta_ad_id = Column(Text)
    meta_post_id = Column(Text)
    campaign_bundle = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    published_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="campaigns")


# ═════════════════════════════════════════════════════════════════════════════
# Analytics
# ═════════════════════════════════════════════════════════════════════════════

class AnalyticsSession(Base):
    """An analytics working session. `user_id` is nullable so pre-auth rows survive."""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, default=_utcnow, server_default=func.now())
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    user_agent = Column(String(512), nullable=True)

    user = relationship("User", back_populates="analytics_sessions")
    analyses = relationship("Analysis", back_populates="session", cascade="all, delete-orphan")
    chat_messages = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True)
    session_id = Column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime, default=_utcnow)

    # File metadata
    file_name = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Dataset summary
    dataset_summary = Column(JSONB, nullable=True)
    profiling_result = Column(JSONB, nullable=True)

    # Business context
    business_domain = Column(String(128), nullable=True)
    domain_confidence = Column(Float, nullable=True)
    domain_reasoning = Column(Text, nullable=True)

    # Generated artefacts
    executive_report = Column(Text, nullable=True)
    visualizations = Column(JSONB, nullable=True)

    session = relationship("AnalyticsSession", back_populates="analyses")
    kpis = relationship("KPIRecord", back_populates="analysis", cascade="all, delete-orphan")
    insights = relationship(
        "InsightRecord", back_populates="analysis", cascade="all, delete-orphan"
    )


class KPIRecord(Base):
    __tablename__ = "kpis"

    id = Column(String(36), primary_key=True)
    analysis_id = Column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(256), nullable=False)
    business_definition = Column(Text)
    formula = Column(Text, nullable=True)
    required_columns = Column(JSONB)
    priority = Column(String(32))
    category = Column(String(128))
    why_important = Column(Text)
    current_value = Column(String(256), nullable=True)
    unit = Column(String(64), nullable=True)
    trend_direction = Column(String(32), nullable=True)
    raw_data = Column(JSONB)

    analysis = relationship("Analysis", back_populates="kpis")


class InsightRecord(Base):
    __tablename__ = "insights"

    id = Column(String(36), primary_key=True)
    analysis_id = Column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(512))
    type = Column(String(64))
    priority = Column(String(32))
    executive_summary = Column(Text)
    detailed_analysis = Column(Text)
    evidence = Column(JSONB)
    recommendation = Column(Text)
    affected_kpis = Column(JSONB)
    business_impact = Column(Text, nullable=True)
    confidence = Column(String(32))
    raw_data = Column(JSONB)

    analysis = relationship("Analysis", back_populates="insights")


class SessionSnapshot(Base):
    """A serialised AnalyticsState snapshot, keyed by session + label.

    Bridges LangGraph invocations and Streamlit re-renders. Declared here
    rather than in analytics/memory/checkpoint.py so that init_all() always
    creates it — a model only reaches create_all() if its module happened to
    be imported first, which for a checkpoint store it often is not.
    """

    __tablename__ = "session_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), nullable=False, index=True)
    snapshot_key = Column(String(256), nullable=False)   # e.g. "latest_analysis"
    state_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    notes = Column(Text, nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True)
    session_id = Column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id = Column(String(36), nullable=True)
    role = Column(String(16))  # "user" | "assistant"
    content = Column(Text)
    message_type = Column(String(64), default="text")
    # 'metadata' is reserved by SQLAlchemy's Declarative API.
    message_metadata = Column(JSONB, nullable=True)
    timestamp = Column(DateTime, default=_utcnow)

    session = relationship("AnalyticsSession", back_populates="chat_messages")


__all__ = [
    "Base",
    "User",
    "Conversation",
    "Lead",
    "Escalation",
    "DocumentChunk",
    "Campaign",
    "AnalyticsSession",
    "Analysis",
    "KPIRecord",
    "InsightRecord",
    "ChatMessage",
]
