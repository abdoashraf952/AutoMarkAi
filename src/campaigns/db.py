"""
src/campaigns/db.py — AutoMark AI (unified)

Campaign persistence on the shared SQLAlchemy async engine.

Schema lives in src/shared/models.py and is created by shared.db.init_all() —
this module no longer owns any DDL. User accounts moved to src/shared/auth.py,
since identity is now app-wide rather than campaign-local.

All functions are async; the API layer awaits them directly instead of the old
asyncio.to_thread() wrapping that the psycopg2 implementation required.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update

from src.shared.db import async_session
from src.shared.models import Campaign

logger = logging.getLogger(__name__)


# ── Serialisation ────────────────────────────────────────────────────────────

_LIST_COLUMNS = (
    "id",
    "thread_id",
    "compound_name",
    "status",
    "budget",
    "language",
    "meta_campaign_id",
    "meta_adset_id",
    "meta_creative_id",
    "meta_ad_id",
    "meta_post_id",
    "created_at",
    "published_at",
)


def _row(obj: Campaign | None, *, include_bundle: bool = False) -> dict:
    """Convert a Campaign row to a JSON-safe dict."""
    if obj is None:
        return {}
    fields = list(_LIST_COLUMNS) + (["campaign_bundle"] if include_bundle else [])
    out: dict[str, Any] = {}
    for name in fields:
        value = getattr(obj, name)
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        out[name] = value
    return out


def _strip_images(campaign_bundle: dict | None) -> dict:
    """Drop base64 images before persisting — they can run to many megabytes."""
    bundle = dict(campaign_bundle) if campaign_bundle else {}
    creative = dict(bundle.get("creative") or {})
    creative.pop("generated_images", None)
    bundle["creative"] = creative
    return bundle


# ── Campaigns ────────────────────────────────────────────────────────────────

async def create_campaign_draft(user_id: str, thread_id: str) -> dict:
    """Insert a 'draft' campaign row when the session is created.

    Idempotent on thread_id — re-creating an existing session is a no-op.
    """
    async with async_session() as session:
        existing = await session.scalar(
            select(Campaign).where(Campaign.thread_id == thread_id)
        )
        if existing is not None:
            return _row(existing)

        campaign = Campaign(user_id=user_id, thread_id=thread_id)
        session.add(campaign)
        await session.flush()
        await session.refresh(campaign)
        return _row(campaign)


async def update_campaign_start(thread_id: str, budget: float, language: str) -> None:
    """Store budget + language once /start is called."""
    async with async_session() as session:
        await session.execute(
            update(Campaign)
            .where(Campaign.thread_id == thread_id)
            .values(budget=budget, language=language)
        )


async def update_campaign_publish(
    thread_id: str,
    compound_name: str,
    meta_campaign_id: str,
    meta_adset_id: str,
    meta_creative_id: str,
    meta_ad_id: str,
    meta_post_id: str,
    campaign_bundle: dict,
) -> None:
    """Update a campaign row with Meta publish results."""
    async with async_session() as session:
        await session.execute(
            update(Campaign)
            .where(Campaign.thread_id == thread_id)
            .values(
                compound_name=compound_name,
                status="published",
                meta_campaign_id=meta_campaign_id or None,
                meta_adset_id=meta_adset_id or None,
                meta_creative_id=meta_creative_id or None,
                meta_ad_id=meta_ad_id or None,
                meta_post_id=meta_post_id or None,
                campaign_bundle=_strip_images(campaign_bundle),
                published_at=func.now(),
            )
        )


async def list_campaigns(user_id: str) -> list[dict]:
    """Return all campaigns for a user, newest first (without the bundle)."""
    async with async_session() as session:
        result = await session.execute(
            select(Campaign)
            .where(Campaign.user_id == user_id)
            .order_by(Campaign.created_at.desc())
        )
        return [_row(c) for c in result.scalars()]


async def get_campaign(campaign_id: str, user_id: str) -> dict | None:
    """Return a single campaign including its bundle (ownership-checked)."""
    async with async_session() as session:
        campaign = await session.scalar(
            select(Campaign).where(
                Campaign.id == campaign_id, Campaign.user_id == user_id
            )
        )
    return _row(campaign, include_bundle=True) if campaign else None
