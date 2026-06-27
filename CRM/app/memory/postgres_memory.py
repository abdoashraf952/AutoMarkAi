"""
app/memory/postgres_memory.py — AutoMark AI CRM Agent (ORCAST)

Rolling-summarization conversation memory backed by PostgreSQL.

Tables (see scripts/init_db.sql):
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

from app.db import get_pool
from config import settings

logger = structlog.get_logger(__name__)

SESSION_GAP_HOURS = 6


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


class PostgresMemory:
    """All memory operations for a single user. Each method acquires its own
    connection from the shared pool — safe for concurrent FastAPI requests."""

    # ── Load ──────────────────────────────────────────────────────────────

    async def load(self, user_id: str, source: str = "unknown") -> dict:
        """
        Load conversation memory for a user, creating a blank record for
        first-time users. If a new session has started after a long gap and
        there are unsummarized messages, summarize them first.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (user_id, source)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id,
                source,
            )
            row = await conn.fetchrow(
                "SELECT * FROM conversations WHERE user_id = $1",
                user_id,
            )

        messages: list[dict] = _loads(row["messages"], [])

        # Session-boundary trigger: long gap since last activity + unsummarized messages
        gap = _utcnow() - row["updated_at"]
        if messages and gap > timedelta(hours=SESSION_GAP_HOURS):
            await self.summarize(user_id)
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM conversations WHERE user_id = $1",
                    user_id,
                )
            messages = _loads(row["messages"], [])

        recent_messages = messages[-settings.MAX_CONVERSATION_HISTORY:]
        lead = await self.get_lead(user_id)

        logger.debug("memory.loaded", user_id=user_id, messages=len(recent_messages))

        return {
            "user_id": user_id,
            "source": row["source"],
            "status": row["status"],
            "summary": row["summary"],
            "recent_messages": recent_messages,
            "message_count": row["message_count"],
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

        pool = await get_pool()
        async with pool.acquire() as conn:
            update_sql = """
                UPDATE conversations
                SET messages      = messages || $1::jsonb,
                    message_count = message_count + 1,
                    updated_at    = NOW()
            """
            params: list[Any] = [json.dumps(entry)]
            if source is not None:
                update_sql += ", source = $2"
                params.append(source)
                update_sql += " WHERE user_id = $3"
                params.append(user_id)
            else:
                update_sql += " WHERE user_id = $2"
                params.append(user_id)

            row = await conn.fetchrow(
                update_sql + " RETURNING message_count",
                *params,
            )

        logger.debug("memory.message.appended", user_id=user_id, role=role)

        if row and row["message_count"] > settings.SUMMARIZATION_MESSAGE_THRESHOLD:
            await self.summarize(user_id)

    # ── Lead data ─────────────────────────────────────────────────────────

    async def get_lead(self, user_id: str) -> dict:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM leads WHERE user_id = $1",
                user_id,
            )
        if row is None:
            return {}
        lead = dict(row)
        lead["pain_points"] = _loads(lead.get("pain_points"), [])
        lead.pop("created_at", None)
        lead.pop("updated_at", None)
        return {k: v for k, v in lead.items() if v is not None}

    async def update_lead(self, user_id: str, updates: dict) -> None:
        """Upsert partial lead data into the leads table."""
        clean = {k: v for k, v in updates.items() if v is not None}
        if not clean:
            return

        columns = list(clean.keys())
        values: list[Any] = []
        for col in columns:
            val = clean[col]
            if col == "pain_points":
                val = json.dumps(val)
            values.append(val)

        insert_cols = ["user_id"] + columns
        placeholders = ", ".join(f"${i + 1}" for i in range(len(insert_cols)))
        update_assignments = ", ".join(
            f"{col} = EXCLUDED.{col}" for col in columns
        )

        sql = f"""
            INSERT INTO leads ({", ".join(insert_cols)})
            VALUES ({placeholders})
            ON CONFLICT (user_id) DO UPDATE
            SET {update_assignments}, updated_at = NOW()
        """

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(sql, user_id, *values)

        logger.debug("memory.lead.updated", user_id=user_id, fields=columns)

    # ── Status ────────────────────────────────────────────────────────────

    async def update_status(self, user_id: str, status: str) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversations
                SET status = $1, updated_at = NOW()
                WHERE user_id = $2
                """,
                status,
                user_id,
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
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO escalations (user_id, reason, priority, hubspot_note_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_id,
                reason,
                priority,
                hubspot_note_id,
            )
            await conn.execute(
                """
                UPDATE conversations
                SET status = 'escalated', updated_at = NOW()
                WHERE user_id = $1
                """,
                user_id,
            )
        logger.info("memory.escalation.created", user_id=user_id, escalation_id=row["id"])
        return row["id"]

    # ── Summarization ─────────────────────────────────────────────────────

    async def summarize(self, user_id: str) -> Optional[str]:
        """Merge the buffered messages into the rolling summary via Gemini,
        then clear the buffer."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT summary, messages FROM conversations WHERE user_id = $1",
                user_id,
            )

        if row is None:
            return None

        messages = _loads(row["messages"], [])
        if not messages:
            return row["summary"]

        from app.services.gemini_service import gemini_service

        transcript = "\n".join(
            f"{m['role']}: {m['content']}" for m in messages
        )
        prompt = (
            "You maintain a rolling summary of a customer-support conversation. "
            "Merge the EXISTING SUMMARY with the NEW MESSAGES into a single, "
            "concise, updated summary. Preserve important facts: who the user "
            "is, what they want, decisions made, and any commitments. "
            "Keep it under 200 words.\n\n"
            f"EXISTING SUMMARY:\n{row['summary'] or '(none)'}\n\n"
            f"NEW MESSAGES:\n{transcript}\n\n"
            "UPDATED SUMMARY:"
        )

        try:
            new_summary = await gemini_service.generate_text(prompt, temperature=0.2)
            new_summary = new_summary.strip()
        except Exception as exc:
            logger.error("memory.summarize.error", user_id=user_id, error=str(exc))
            return row["summary"]

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversations
                SET summary              = $1,
                    messages              = '[]'::jsonb,
                    message_count         = 0,
                    summarization_cycles  = summarization_cycles + 1,
                    summary_updated_at    = NOW(),
                    updated_at            = NOW()
                WHERE user_id = $2
                """,
                new_summary,
                user_id,
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
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM conversations WHERE user_id = $1", user_id)
        logger.info("memory.cleared", user_id=user_id)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

postgres_memory = PostgresMemory()
