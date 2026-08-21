"""
shared/crm_models.py — SQLAlchemy ORM definitions for the CRM tables.

These are READ-ONLY mirror models used by the Analytics project to query
the CRM tables (conversations, leads, escalations) that live in the shared
`automark` PostgreSQL database.

The CRM itself writes these tables via asyncpg + raw SQL (init_db.sql).
The Analytics reads them via SQLAlchemy for data analysis.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, Integer,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class CRMBase(DeclarativeBase):
    """Separate declarative base so CRM models don't mix with Analytics models."""
    pass


class Conversation(CRMBase):
    """Rolling-summary conversation memory — one row per user."""
    __tablename__ = "conversations"

    user_id             = Column(String,   primary_key=True)
    source              = Column(String,   nullable=False, default="unknown")
    status              = Column(String,   nullable=False, default="active")
    summary             = Column(Text)
    messages            = Column(JSONB,    nullable=False, default=list)
    message_count       = Column(Integer,  nullable=False, default=0)
    summarization_cycles= Column(Integer,  nullable=False, default=0)
    summary_updated_at  = Column(DateTime(timezone=True))
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now())


class Lead(CRMBase):
    """Lead qualification data collected progressively by the CRM agent."""
    __tablename__ = "leads"

    user_id            = Column(String,  primary_key=True)
    name               = Column(String)
    email              = Column(String)
    phone              = Column(String)
    company            = Column(String)
    budget             = Column(String)
    authority          = Column(String)
    engagement_level   = Column(Integer)
    interest_level     = Column(Integer)
    pain_points        = Column(JSONB,   nullable=False, default=list)
    lead_score         = Column(Integer)
    lead_temperature   = Column(String)
    hubspot_contact_id = Column(String)
    hubspot_deal_id    = Column(String)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())
    updated_at         = Column(DateTime(timezone=True), server_default=func.now())


class Escalation(CRMBase):
    """Human-handoff records created when the AI escalates a conversation."""
    __tablename__ = "escalations"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id         = Column(String,  nullable=False)
    reason          = Column(Text,    nullable=False)
    priority        = Column(String,  nullable=False, default="medium")
    status          = Column(String,  nullable=False, default="open")
    hubspot_note_id = Column(String)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), server_default=func.now())


# Convenience export
CRM_TABLES = {
    "leads":         Lead,
    "conversations": Conversation,
    "escalations":   Escalation,
}
