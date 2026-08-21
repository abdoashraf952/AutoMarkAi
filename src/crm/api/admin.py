"""
src/crm/api/admin.py — AutoMark AI (unified)

Database access endpoints for the admin dashboard, backed by the shared
SQLAlchemy async engine.

All endpoints live under /api/crm/admin/db/ and return JSON.
Protect with a reverse proxy or firewall in production.
"""

from __future__ import annotations

from typing import Any, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import delete, func, select

from src.shared.db import async_session
from src.shared.models import Conversation, DocumentChunk, Escalation, Lead

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/db", tags=["Database"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_dict(obj: Any) -> dict:
    """Serialise an ORM instance to a plain dict (public columns only)."""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


async def _paginate(stmt, count_stmt, limit: int, offset: int, rows_as_dict) -> dict:
    async with async_session() as session:
        total = await session.scalar(count_stmt)
        result = await session.execute(stmt.limit(limit).offset(offset))
        data = rows_as_dict(result)
    return {"total": int(total or 0), "limit": limit, "offset": offset, "data": data}


# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats", summary="Database overview — row counts for all tables")
async def db_stats() -> dict:
    stats: dict[str, Any] = {}
    async with async_session() as session:
        for name, model in (
            ("conversations", Conversation),
            ("leads", Lead),
            ("escalations", Escalation),
            ("document_chunks", DocumentChunk),
        ):
            stats[name] = int(
                await session.scalar(select(func.count()).select_from(model)) or 0
            )

        # Lead temperature breakdown
        temp_rows = await session.execute(
            select(Lead.lead_temperature, func.count().label("n"))
            .where(Lead.lead_temperature.isnot(None))
            .group_by(Lead.lead_temperature)
            .order_by(func.count().desc())
        )
        stats["leads_by_temperature"] = {r[0]: r[1] for r in temp_rows}

        # Escalation status breakdown
        esc_rows = await session.execute(
            select(Escalation.status, func.count()).group_by(Escalation.status)
        )
        stats["escalations_by_status"] = {r[0]: r[1] for r in esc_rows}

        # Source breakdown
        src_rows = await session.execute(
            select(Conversation.source, func.count().label("n"))
            .group_by(Conversation.source)
            .order_by(func.count().desc())
        )
        stats["conversations_by_source"] = {r[0]: r[1] for r in src_rows}

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Leads
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/leads", summary="List all leads")
async def list_leads(
    temperature: Optional[str] = Query(None, description="Filter: cold | warm | hot | qualified"),
    min_score:   Optional[int] = Query(None, description="Minimum lead score (0–100)"),
    limit:       int           = Query(50,   ge=1, le=500),
    offset:      int           = Query(0,    ge=0),
) -> dict:
    filters = []
    if temperature:
        filters.append(Lead.lead_temperature == temperature)
    if min_score is not None:
        filters.append(Lead.lead_score >= min_score)

    stmt = select(Lead).where(*filters).order_by(Lead.lead_score.desc().nullslast())
    count_stmt = select(func.count()).select_from(Lead).where(*filters)

    return await _paginate(
        stmt, count_stmt, limit, offset,
        lambda res: [_to_dict(r) for r in res.scalars()],
    )


@router.get("/leads/{user_id}", summary="Get a single lead by user_id")
async def get_lead(user_id: str) -> dict:
    async with async_session() as session:
        row = await session.scalar(select(Lead).where(Lead.user_id == user_id))
    if not row:
        raise HTTPException(status_code=404, detail=f"Lead '{user_id}' not found")
    return _to_dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# Conversations
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/conversations", summary="List all conversations")
async def list_conversations(
    status: Optional[str] = Query(None, description="Filter: active | escalated"),
    source: Optional[str] = Query(None, description="Filter: messenger | facebook_comments | vapi"),
    limit:  int           = Query(50,  ge=1, le=500),
    offset: int           = Query(0,   ge=0),
) -> dict:
    filters = []
    if status:
        filters.append(Conversation.status == status)
    if source:
        filters.append(Conversation.source == source)

    stmt = (
        select(
            Conversation.user_id,
            Conversation.source,
            Conversation.status,
            Conversation.message_count,
            Conversation.summarization_cycles,
            Conversation.summary,
            Conversation.updated_at,
            Conversation.created_at,
        )
        .where(*filters)
        .order_by(Conversation.updated_at.desc().nullslast())
    )
    count_stmt = select(func.count()).select_from(Conversation).where(*filters)

    return await _paginate(
        stmt, count_stmt, limit, offset,
        lambda res: [dict(r) for r in res.mappings()],
    )


@router.delete(
    "/conversations/{user_id}",
    summary="Delete a conversation and all related data (lead, escalations)",
)
async def delete_conversation(user_id: str) -> dict:
    async with async_session() as session:
        convo = await session.scalar(
            select(Conversation).where(Conversation.user_id == user_id)
        )
        if not convo:
            raise HTTPException(
                status_code=404, detail=f"Conversation '{user_id}' not found"
            )

        deleted_escs = (
            await session.execute(delete(Escalation).where(Escalation.user_id == user_id))
        ).rowcount or 0
        deleted_leads = (
            await session.execute(delete(Lead).where(Lead.user_id == user_id))
        ).rowcount or 0
        await session.execute(
            delete(Conversation).where(Conversation.user_id == user_id)
        )

    logger.warning(
        "admin.conversation_deleted",
        user_id=user_id,
        leads_deleted=deleted_leads,
        escalations_deleted=deleted_escs,
    )
    return {
        "deleted": True,
        "user_id": user_id,
        "leads_deleted": deleted_leads,
        "escalations_deleted": deleted_escs,
    }


@router.get(
    "/conversations/{user_id}",
    summary="Get full conversation — summary + recent messages",
)
async def get_conversation(user_id: str) -> dict:
    async with async_session() as session:
        convo = await session.scalar(
            select(Conversation).where(Conversation.user_id == user_id)
        )
        if not convo:
            raise HTTPException(
                status_code=404, detail=f"Conversation '{user_id}' not found"
            )
        row = _to_dict(convo)

        lead = await session.scalar(select(Lead).where(Lead.user_id == user_id))
        row["lead"] = _to_dict(lead) if lead else None

        escs = await session.execute(
            select(Escalation)
            .where(Escalation.user_id == user_id)
            .order_by(Escalation.created_at.desc())
        )
        row["escalations"] = [_to_dict(e) for e in escs.scalars()]

    return row


# ─────────────────────────────────────────────────────────────────────────────
# Escalations
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/escalations", summary="List all escalations")
async def list_escalations(
    status:   Optional[str] = Query(None, description="Filter: open | closed"),
    priority: Optional[str] = Query(None, description="Filter: low | medium | high | urgent"),
    limit:    int            = Query(50,  ge=1, le=500),
    offset:   int            = Query(0,   ge=0),
) -> dict:
    filters = []
    if status:
        filters.append(Escalation.status == status)
    if priority:
        filters.append(Escalation.priority == priority)

    stmt = (
        select(
            Escalation,
            Lead.name,
            Lead.email,
            Lead.phone,
            Lead.lead_score,
            Lead.lead_temperature,
        )
        .outerjoin(Lead, Escalation.user_id == Lead.user_id)
        .where(*filters)
        .order_by(Escalation.created_at.desc())
    )
    count_stmt = select(func.count()).select_from(Escalation).where(*filters)

    def _rows(res):
        out = []
        for esc, name, email, phone, score, temperature in res:
            row = _to_dict(esc)
            row.update(
                name=name,
                email=email,
                phone=phone,
                lead_score=score,
                lead_temperature=temperature,
            )
            out.append(row)
        return out

    return await _paginate(stmt, count_stmt, limit, offset, _rows)


@router.patch("/escalations/{escalation_id}/close", summary="Close an escalation")
async def close_escalation(escalation_id: int) -> dict:
    async with async_session() as session:
        esc = await session.scalar(
            select(Escalation).where(Escalation.id == escalation_id)
        )
        if not esc:
            raise HTTPException(
                status_code=404, detail=f"Escalation #{escalation_id} not found"
            )
        esc.status = "closed"
        esc.updated_at = func.now()
        await session.flush()
        await session.refresh(esc)
        payload = _to_dict(esc)

    logger.info("admin.escalation_closed", escalation_id=escalation_id)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# RAG — Document chunks
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/chunks", summary="List knowledge-base chunks (RAG store)")
async def list_chunks(
    source_file: Optional[str] = Query(None, description="Filter by filename"),
    limit:       int            = Query(20,  ge=1, le=200),
    offset:      int            = Query(0,   ge=0),
) -> dict:
    filters = []
    if source_file:
        filters.append(DocumentChunk.source_file.ilike(f"%{source_file}%"))

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.doc_id,
            DocumentChunk.source_file,
            DocumentChunk.chunk_index,
            DocumentChunk.token_count,
            func.left(DocumentChunk.content, 200).label("content_preview"),
            DocumentChunk.doc_metadata.label("metadata"),
            DocumentChunk.created_at,
        )
        .where(*filters)
        .order_by(DocumentChunk.source_file, DocumentChunk.chunk_index)
    )
    count_stmt = select(func.count()).select_from(DocumentChunk).where(*filters)

    page = await _paginate(
        stmt, count_stmt, limit, offset,
        lambda res: [dict(r) for r in res.mappings()],
    )

    async with async_session() as session:
        files = await session.execute(
            select(DocumentChunk.source_file, func.count().label("chunks"))
            .group_by(DocumentChunk.source_file)
            .order_by(DocumentChunk.source_file)
        )
        page["files"] = {r[0]: r[1] for r in files}

    return page


@router.delete("/chunks", summary="Delete all RAG chunks (re-ingest required after)")
async def delete_all_chunks() -> dict:
    async with async_session() as session:
        result = await session.execute(delete(DocumentChunk))
    deleted = result.rowcount or 0
    logger.warning("admin.chunks_deleted_all", count=deleted)
    return {
        "deleted": deleted,
        "message": "Run python -m src.crm.rag.ingest --source ./src/crm/knowledge_base to re-ingest",
    }
