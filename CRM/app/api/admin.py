"""
app/api/admin.py — AutoMark AI CRM Agent (ORCAST)

Database access endpoints for the admin dashboard.

All endpoints live under /admin/db/ and return JSON.
Protect with a reverse proxy or firewall in production.
"""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query

from app.db import get_pool

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/db", tags=["Database"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch(query: str, *args) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def _fetchone(query: str, *args) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def _fetchval(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats", summary="Database overview — row counts for all tables")
async def db_stats() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        stats = {}
        for table in ("conversations", "leads", "escalations", "document_chunks"):
            stats[table] = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")

        # Lead temperature breakdown
        temp_rows = await conn.fetch(
            "SELECT lead_temperature, COUNT(*) as n FROM leads "
            "WHERE lead_temperature IS NOT NULL GROUP BY lead_temperature ORDER BY n DESC"
        )
        stats["leads_by_temperature"] = {r["lead_temperature"]: r["n"] for r in temp_rows}

        # Escalation status breakdown
        esc_rows = await conn.fetch(
            "SELECT status, COUNT(*) as n FROM escalations GROUP BY status"
        )
        stats["escalations_by_status"] = {r["status"]: r["n"] for r in esc_rows}

        # Source breakdown
        src_rows = await conn.fetch(
            "SELECT source, COUNT(*) as n FROM conversations GROUP BY source ORDER BY n DESC"
        )
        stats["conversations_by_source"] = {r["source"]: r["n"] for r in src_rows}

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
    conditions = []
    params: list = []

    if temperature:
        params.append(temperature)
        conditions.append(f"lead_temperature = ${len(params)}")
    if min_score is not None:
        params.append(min_score)
        conditions.append(f"lead_score >= ${len(params)}")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params += [limit, offset]

    rows = await _fetch(
        f"SELECT * FROM leads {where} ORDER BY lead_score DESC NULLS LAST "
        f"LIMIT ${len(params)-1} OFFSET ${len(params)}",
        *params,
    )
    total = await _fetchval(f"SELECT COUNT(*) FROM leads {where}", *params[:-2])
    return {"total": total, "limit": limit, "offset": offset, "data": rows}


@router.get("/leads/{user_id}", summary="Get a single lead by user_id")
async def get_lead(user_id: str) -> dict:
    row = await _fetchone("SELECT * FROM leads WHERE user_id = $1", user_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Lead '{user_id}' not found")
    return row


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
    conditions = []
    params: list = []

    if status:
        params.append(status)
        conditions.append(f"status = ${len(params)}")
    if source:
        params.append(source)
        conditions.append(f"source = ${len(params)}")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params += [limit, offset]

    rows = await _fetch(
        f"SELECT user_id, source, status, message_count, summarization_cycles, "
        f"summary, updated_at, created_at FROM conversations {where} "
        f"ORDER BY updated_at DESC NULLS LAST "
        f"LIMIT ${len(params)-1} OFFSET ${len(params)}",
        *params,
    )
    total = await _fetchval(f"SELECT COUNT(*) FROM conversations {where}", *params[:-2])
    return {"total": total, "limit": limit, "offset": offset, "data": rows}


@router.delete("/conversations/{user_id}", summary="Delete a conversation and all related data (lead, escalations)")
async def delete_conversation(user_id: str) -> dict:
    row = await _fetchone("SELECT user_id, source, status, message_count FROM conversations WHERE user_id = $1", user_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Conversation '{user_id}' not found")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # execute() returns "DELETE N" — parse the count from the tag
            tag_escs  = await conn.execute("DELETE FROM escalations WHERE user_id=$1", user_id)
            tag_leads = await conn.execute("DELETE FROM leads        WHERE user_id=$1", user_id)
            await conn.execute("DELETE FROM conversations WHERE user_id=$1", user_id)

    deleted_escs  = int(tag_escs.split()[-1])
    deleted_leads = int(tag_leads.split()[-1])

    logger.warning("admin.conversation_deleted", user_id=user_id,
                   leads_deleted=deleted_leads, escalations_deleted=deleted_escs)
    return {
        "deleted": True,
        "user_id": user_id,
        "leads_deleted": deleted_leads,
        "escalations_deleted": deleted_escs,
    }


@router.get("/conversations/{user_id}", summary="Get full conversation — summary + recent messages")
async def get_conversation(user_id: str) -> dict:
    row = await _fetchone("SELECT * FROM conversations WHERE user_id = $1", user_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Conversation '{user_id}' not found")

    # Also return the lead if one exists
    lead = await _fetchone("SELECT * FROM leads WHERE user_id = $1", user_id)
    row["lead"] = lead

    # And escalations
    pool = await get_pool()
    async with pool.acquire() as conn:
        escs = await conn.fetch(
            "SELECT * FROM escalations WHERE user_id = $1 ORDER BY created_at DESC", user_id
        )
        row["escalations"] = [dict(e) for e in escs]

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
    conditions = []
    params: list = []

    if status:
        params.append(status)
        conditions.append(f"e.status = ${len(params)}")
    if priority:
        params.append(priority)
        conditions.append(f"e.priority = ${len(params)}")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params += [limit, offset]

    rows = await _fetch(
        f"SELECT e.*, l.name, l.email, l.phone, l.lead_score, l.lead_temperature "
        f"FROM escalations e LEFT JOIN leads l ON e.user_id = l.user_id "
        f"{where} ORDER BY e.created_at DESC "
        f"LIMIT ${len(params)-1} OFFSET ${len(params)}",
        *params,
    )
    total = await _fetchval(f"SELECT COUNT(*) FROM escalations e {where}", *params[:-2])
    return {"total": total, "limit": limit, "offset": offset, "data": rows}


@router.patch("/escalations/{escalation_id}/close", summary="Close an escalation")
async def close_escalation(escalation_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE escalations SET status='closed', updated_at=NOW() "
            "WHERE id=$1 RETURNING *", escalation_id
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Escalation #{escalation_id} not found")
    logger.info("admin.escalation_closed", escalation_id=escalation_id)
    return dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# RAG — Document chunks
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/chunks", summary="List knowledge-base chunks (RAG store)")
async def list_chunks(
    source_file: Optional[str] = Query(None, description="Filter by filename"),
    limit:       int            = Query(20,  ge=1, le=200),
    offset:      int            = Query(0,   ge=0),
) -> dict:
    conditions = []
    params: list = []

    if source_file:
        params.append(f"%{source_file}%")
        conditions.append(f"source_file ILIKE ${len(params)}")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params += [limit, offset]

    rows = await _fetch(
        f"SELECT id, doc_id, source_file, chunk_index, token_count, "
        f"LEFT(content, 200) AS content_preview, metadata, created_at "
        f"FROM document_chunks {where} ORDER BY source_file, chunk_index "
        f"LIMIT ${len(params)-1} OFFSET ${len(params)}",
        *params,
    )
    total = await _fetchval(f"SELECT COUNT(*) FROM document_chunks {where}", *params[:-2])

    # File summary
    pool = await get_pool()
    async with pool.acquire() as conn:
        files = await conn.fetch(
            "SELECT source_file, COUNT(*) as chunks FROM document_chunks "
            "GROUP BY source_file ORDER BY source_file"
        )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "files": {r["source_file"]: r["chunks"] for r in files},
        "data": rows,
    }


@router.delete("/chunks", summary="Delete all RAG chunks (re-ingest required after)")
async def delete_all_chunks() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval("DELETE FROM document_chunks RETURNING COUNT(*)")
    logger.warning("admin.chunks_deleted_all", count=deleted)
    return {"deleted": deleted, "message": "Run python -m app.rag.ingest --source ./knowledge_base to re-ingest"}
