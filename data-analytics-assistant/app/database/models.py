"""SQLAlchemy ORM models for the analytics database."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, JSON, func
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_agent = Column(String(512), nullable=True)

    analyses = relationship("Analysis", back_populates="session", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # File metadata
    file_name = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Dataset summary (JSON)
    dataset_summary = Column(JSON, nullable=True)
    profiling_result = Column(JSON, nullable=True)

    # Business context
    business_domain = Column(String(128), nullable=True)
    domain_confidence = Column(Float, nullable=True)
    domain_reasoning = Column(Text, nullable=True)

    # Relationships
    session = relationship("Session", back_populates="analyses")
    kpis = relationship("KPIRecord", back_populates="analysis", cascade="all, delete-orphan")
    insights = relationship("InsightRecord", back_populates="analysis", cascade="all, delete-orphan")
    dashboard_spec = relationship("DashboardSpecRecord", back_populates="analysis", uselist=False, cascade="all, delete-orphan")


class KPIRecord(Base):
    __tablename__ = "kpis"

    id = Column(String(36), primary_key=True)
    analysis_id = Column(String(36), ForeignKey("analyses.id"), nullable=False)
    name = Column(String(256), nullable=False)
    business_definition = Column(Text)
    formula = Column(Text, nullable=True)
    required_columns = Column(JSON)
    priority = Column(String(32))
    category = Column(String(128))
    why_important = Column(Text)
    current_value = Column(String(256), nullable=True)
    unit = Column(String(64), nullable=True)
    trend_direction = Column(String(32), nullable=True)
    raw_data = Column(JSON)

    analysis = relationship("Analysis", back_populates="kpis")


class InsightRecord(Base):
    __tablename__ = "insights"

    id = Column(String(36), primary_key=True)
    analysis_id = Column(String(36), ForeignKey("analyses.id"), nullable=False)
    title = Column(String(512))
    type = Column(String(64))
    priority = Column(String(32))
    executive_summary = Column(Text)
    detailed_analysis = Column(Text)
    evidence = Column(JSON)
    recommendation = Column(Text)
    affected_kpis = Column(JSON)
    business_impact = Column(Text, nullable=True)
    confidence = Column(String(32))
    raw_data = Column(JSON)

    analysis = relationship("Analysis", back_populates="insights")


class DashboardSpecRecord(Base):
    __tablename__ = "dashboard_specs"

    id = Column(String(36), primary_key=True)
    analysis_id = Column(String(36), ForeignKey("analyses.id"), nullable=False)
    title = Column(String(512))
    description = Column(Text)
    target_audience = Column(String(256))
    spec_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    analysis = relationship("Analysis", back_populates="dashboard_spec")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    analysis_id = Column(String(36), nullable=True)
    role = Column(String(16))  # "user" | "assistant"
    content = Column(Text)
    message_type = Column(String(64), default="text")
    message_metadata = Column(JSON, nullable=True)  # renamed from 'metadata' (reserved by SQLAlchemy)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="chat_messages")
