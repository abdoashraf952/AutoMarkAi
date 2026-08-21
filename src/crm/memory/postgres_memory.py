"""
src/crm/memory/postgres_memory.py — AutoMark AI (unified)

Rolling-summarization conversation memory, backed by the shared SQLAlchemy
async engine (src/shared/db.py).

Tables (see src/shared/models.py):
    conversations — user_id PK, source, status, summary, messages JSONB,
                    message_count, summarization_cycles, summary_updated_at
    leads         — progressively-collected lead qualification data
    escalations   — human-handoff records

Summarization strategy:
    - Every inbound/outbound turn is appended to `messages` (JSONB array).
    - When `message_count` exceeds SUMMARIZATION_MESSAGE_THRESHOLD, or a new
      session starts after a long gap, `summarize()` merges the buffered
      messages into the rolling `summary` via Gemini and clears the buffer.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import cast, func, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert

from src.config import settings
from src.shared.db import async_session
from src.shared.models import Conversation, Escalation, Lead

logger = structlog.get_logger(__name__)

SESSION_GAP_HOURS = 6


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime:
    """Treat naive timestamps as UTC so gap arithmetic never raises."""
    if dt is None:
        return _utcnow()
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class PostgresMemory:
    """All memory operations for a single user. Each method opens its own
    session — safe for concurrent FastAPI requests."""

    # ── Load ──────────────────────────────────────────────────────────────

    async def load(self, user_id: str, source: str = "unknown") -> dict:
        """
        Load conversation memory for a user, creating a blank record for
        first-time users. If a new session has started after a long gap and
        there are unsummarized messages, summarize them first.
        """
        async with async_session() as session:
            await session.execute(
                insert(Conversation)
                .values(user_id=user_id, source=source)
                .on_conflict_do_nothing(index_elements=[Conversation.user_id])
            )
            row = await session.scalar(
                select(Conversation).where(Conversation.user_id == user_id)
            )

        messages: list[dict] = list(row.messages or [])

        # Session-boundary trigger: long gap since last activity + unsummarized messages
        gap = _utcnow() - _as_aware(row.updated_at)
        if messages and gap > timedelta(hours=SESSION_GAP_HOURS):
            await self.summarize(user_id)
            async with async_session() as session:
                row = await session.scalar(
                    select(Conversation).where(Conversation.user_id == user_id)
                )
            messages = list(row.messages or [])

        recent_messages = messages[-settings.MAX_CONVERSATION_HISTORY:]
        lead = await self.get_lead(user_id)

        logger.debug("memory.loaded", user_id=user_id, messages=len(recent_messages))

        return {
            "user_id": user_id,
            "source": row.source,
            "status": row.status,
            "summary": row.summary,
            "recent_messages": recent_messages,
            "message_count": row.message_count,
            "lead": lead,
        }

    # ── Messages ──────────────────────────────────────────────────────────

    async def append_message(
        self,
        user_id: str,
        role: str,
        content: str,
        source: Optional[str] = None,
    ) -> None:
        """Append a turn to the rolling message buffer and update the
        conversation's active channel. Triggers summarization if the
        buffer grows past SUMMARIZATION_MESSAGE_THRESHOLD."""
        entry = {
            "role": role,
            "content": content,
            "source": source,
            "timestamp": _utcnow().isoformat(),
        }

        values: dict[str, Any] = {
            # JSONB concat — appends without reading the array back first.
            # Bind the Python list itself and let the JSONB type serialise it;
            # passing a pre-dumped string would be encoded a second time and
            # land in the column as a JSON string rather than an object.
            "messages": Conversation.messages.op("||")(cast([entry], JSONB)),
            "message_count": Conversation.message_count + 1,
            "updated_at": func.now(),
        }
        if source is not None:
            values["source"] = source

        async with async_session() as session:
            message_count = await session.scalar(
                update(Conversation)
                .where(Conversation.user_id == user_id)
                .values(**values)
                .returning(Conversation.message_count)
            )

        logger.debug("memory.message.appended", user_id=user_id, role=role)

        if message_count and message_count > settings.SUMMARIZATION_MESSAGE_THRESHOLD:
            await self.summarize(user_id)

    # ── Lead data ─────────────────────────────────────────────────────────

    async def get_lead(self, user_id: str) -> dict:
        async with async_session() as session:
            row = await session.scalar(select(Lead).where(Lead.user_id == user_id))
        if row is None:
            return {}

        lead = {
            "user_id": row.user_id,
            "name": row.name,
            "email": row.email,
            "phone": row.phone,
            "budget": row.budget,
            "authority": row.authority,
            "engagement_level": row.engagement_level,
            "interest_level": row.interest_level,
            "pain_points": list(row.pain_points or []),
            "lead_score": row.lead_score,
            "lead_temperature": row.lead_temperature,
            "hubspot_contact_id": row.hubspot_contact_id,
            "hubspot_deal_id": row.hubspot_deal_id,
        }
        return {k: v for k, v in lead.items() if v is not None}

    async def update_lead(self, user_id: str, updates: dict) -> None:
        """Upsert partial lead data into the leads table."""
        allowed = {c.name for c in Lead.__table__.columns} - {
            "user_id",
            "created_at",
            "updated_at",
        }
        clean = {k: v for k, v in updates.items() if v is not None and k in allowed}
        if not clean:
            return

        stmt = insert(Lead).values(user_id=user_id, **clean)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Lead.user_id],
            set_={**{k: stmt.excluded[k] for k in clean}, "updated_at": func.now()},
        )

        async with async_session() as session:
            await session.execute(stmt)

        logger.debug("memory.lead.updated", user_id=user_id, fields=list(clean))

    # ── Status ────────────────────────────────────────────────────────────

    async def update_status(self, user_id: str, status: str) -> None:
        async with async_session() as session:
            await session.execute(
                update(Conversation)
                .where(Conversation.user_id == user_id)
                .values(status=status, updated_at=func.now())
            )
        logger.info("memory.status.updated", user_id=user_id, status=status)

    # ── Escalations ───────────────────────────────────────────────────────

    async def create_escalation(
        self,
        user_id: str,
        reason: str,
        priority: str = "medium",
        hubspot_note_id: Optional[str] = None,
    ) -> int:
        async with async_session() as session:
            escalation = Escalation(
                user_id=user_id,
                reason=reason,
                priority=priority,
                hubspot_note_id=hubspot_note_id,
            )
            session.add(escalation)
            await session.flush()
            escalation_id = escalation.id
            await session.execute(
                update(Conversation)
                .where(Conversation.user_id == user_id)
                .values(status="escalated", updated_at=func.now())
            )
        logger.info("memory.escalation.created", user_id=user_id, escalation_id=escalation_id)
        return escalation_id

    # ── Summarization ─────────────────────────────────────────────────────

    async def summarize(self, user_id: str) -> Optional[str]:
        """Merge the buffered messages into the rolling summary via Gemini,
        then clear the buffer."""
        async with async_session() as session:
            row = (
                await session.execute(
                    select(Conversation.summary, Conversation.messages).where(
                        Conversation.user_id == user_id
                    )
                )
            ).first()

        if row is None:
            return None

        existing_summary, raw_messages = row
        messages = list(raw_messages or [])
        if not messages:
            return existing_summary

        from src.crm.services.gemini_service import gemini_service

        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        prompt = (
            "You maintain a rolling summary of a customer-support conversation. "
            "Merge the EXISTING SUMMARY with the NEW MESSAGES into a single, "
            "concise, updated summary. Preserve important facts: who the user "
            "is, what they want, decisions made, and any commitments. "
            "Keep it under 200 words.\n\n"
            f"EXISTING SUMMARY:\n{existing_summary or '(none)'}\n\n"
            f"NEW MESSAGES:\n{transcript}\n\n"
            "UPDATED SUMMARY:"
        )

        try:
            new_summary = (await gemini_service.generate_text(prompt, temperature=0.2)).strip()
        except Exception as exc:
            logger.error("memory.summarize.error", user_id=user_id, error=str(exc))
            return existing_summary

        async with async_session() as session:
            await session.execute(
                update(Conversation)
                .where(Conversation.user_id == user_id)
                .values(
                    summary=new_summary,
                    messages=[],
                    message_count=0,
                    summarization_cycles=Conversation.summarization_cycles + 1,
                    summary_updated_at=func.now(),
                    updated_at=func.now(),
                )
            )

        logger.info("memory.summarized", user_id=user_id)
        return new_summary

    # ── Context block ─────────────────────────────────────────────────────

    async def build_context_block(self, user_id: str) -> str:
        """Build a human-readable context block for the system prompt."""
        memory = await self.load(user_id)

        lines: list[str] = ["[Conversation History Summary]"]
        lines.append(memory["summary"] or "No prior summary.")

        lines.append("\n[Recent Messages]")
        if memory["recent_messages"]:
            for m in memory["recent_messages"]:
                lines.append(f"{m['role']}: {m['content']}")
        else:
            lines.append("No recent messages.")

        lines.append("\n[Lead Profile]")
        lines.append(json.dumps(memory["lead"], default=str))

        return "\n".join(lines)

    # ── Clear (testing / admin) ──────────────────────────────────────────

    async def clear(self, user_id: str) -> None:
        async with async_session() as session:
            row = await session.scalar(
                select(Conversation).where(Conversation.user_id == user_id)
            )
            if row is not None:
                await session.delete(row)
        logger.info("memory.cleared", user_id=user_id)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

postgres_memory = PostgresMemory()
