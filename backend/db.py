"""
Business records database layer — psycopg2 + PostgreSQL.

Tables (auto-created on startup via init_db()):
  users      — registered accounts (email + bcrypt hash)
  campaigns  — one row per campaign session; updated at start and publish

All DB operations are synchronous (psycopg2 is blocking).
Call them via asyncio.to_thread() from async FastAPI endpoints.

Requires POSTGRES_URL in environment:
  postgresql://user:password@localhost:5432/automark_db
"""

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None

# ── Schema ─────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT        NOT NULL UNIQUE,
    pw_hash     TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campaigns (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    thread_id         TEXT        NOT NULL UNIQUE,
    compound_name     TEXT,
    status            TEXT        NOT NULL DEFAULT 'draft',
    budget            FLOAT,
    language          TEXT,
    meta_campaign_id  TEXT,
    meta_adset_id     TEXT,
    meta_creative_id  TEXT,
    meta_ad_id        TEXT,
    meta_post_id      TEXT,
    campaign_bundle   JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at      TIMESTAMPTZ
);
"""


# ── Connection pool ────────────────────────────────────────────────────────────

def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        url = os.getenv("POSTGRES_URL", "").strip()
        if not url:
            raise RuntimeError(
                "POSTGRES_URL is not set. "
                "Add it to .env: postgresql://user:pass@localhost:5432/automark_db"
            )
        _pool = ThreadedConnectionPool(2, 20, dsn=url)
        logger.info("db: PostgreSQL connection pool initialised")
    return _pool


@contextmanager
def _conn():
    """Get a connection, auto-commit on exit, auto-rollback on error."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── Startup ────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables if they don't exist. Safe to call multiple times."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
        logger.info("db: schema ready (users + campaigns)")
    except Exception as exc:
        logger.error("db: init_db failed — %s", exc)
        raise


# ── Serialisation helpers ──────────────────────────────────────────────────────

def _row(row) -> dict:
    """Convert a RealDictRow to a plain dict, stringify UUIDs and datetimes."""
    if row is None:
        return {}
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, uuid.UUID):
            d[k] = str(v)
        elif isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


# ── Users ──────────────────────────────────────────────────────────────────────

def create_user(email: str, pw_hash: str) -> dict:
    """Insert a new user. Raises psycopg2.errors.UniqueViolation on duplicate email."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO users (email, pw_hash) VALUES (%s, %s) "
                "RETURNING id, email, created_at",
                (email.lower().strip(), pw_hash),
            )
            return _row(cur.fetchone())


def find_user_by_email(email: str) -> dict | None:
    """Return user row (id, email, pw_hash) or None."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, pw_hash FROM users WHERE email = %s",
                (email.lower().strip(),),
            )
            return _row(cur.fetchone()) or None


# ── Campaigns ──────────────────────────────────────────────────────────────────

def create_campaign_draft(user_id: str, thread_id: str) -> dict:
    """Insert a 'draft' campaign row when the session is created."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO campaigns (user_id, thread_id) "
                "VALUES (%s, %s) "
                "ON CONFLICT (thread_id) DO NOTHING "
                "RETURNING id, thread_id, status, created_at",
                (user_id, thread_id),
            )
            return _row(cur.fetchone()) or {}


def update_campaign_start(thread_id: str, budget: float, language: str) -> None:
    """Store budget + language once /start is called."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE campaigns SET budget = %s, language = %s WHERE thread_id = %s",
                (budget, language, thread_id),
            )


def update_campaign_publish(
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
    # Strip base64 images before persisting (can be many MB)
    bundle = dict(campaign_bundle) if campaign_bundle else {}
    creative = dict(bundle.get("creative") or {})
    creative.pop("generated_images", None)
    bundle["creative"] = creative

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE campaigns SET
                    compound_name    = %s,
                    status           = 'published',
                    meta_campaign_id = %s,
                    meta_adset_id    = %s,
                    meta_creative_id = %s,
                    meta_ad_id       = %s,
                    meta_post_id     = %s,
                    campaign_bundle  = %s,
                    published_at     = NOW()
                   WHERE thread_id = %s""",
                (
                    compound_name,
                    meta_campaign_id or None,
                    meta_adset_id    or None,
                    meta_creative_id or None,
                    meta_ad_id       or None,
                    meta_post_id     or None,
                    json.dumps(bundle, ensure_ascii=False),
                    thread_id,
                ),
            )


def list_campaigns(user_id: str) -> list[dict]:
    """Return all campaigns for a user, newest first."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, thread_id, compound_name, status, budget, language,
                          meta_campaign_id, meta_adset_id, meta_creative_id,
                          meta_ad_id, meta_post_id,
                          created_at, published_at
                   FROM campaigns
                   WHERE user_id = %s
                   ORDER BY created_at DESC""",
                (user_id,),
            )
            return [_row(r) for r in cur.fetchall()]


def get_campaign(campaign_id: str, user_id: str) -> dict | None:
    """Return a single campaign including its bundle (ownership-checked)."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, thread_id, compound_name, status, budget, language,
                          meta_campaign_id, meta_adset_id, meta_creative_id,
                          meta_ad_id, meta_post_id,
                          campaign_bundle,
                          created_at, published_at
                   FROM campaigns
                   WHERE id = %s AND user_id = %s""",
                (campaign_id, user_id),
            )
            return _row(cur.fetchone()) or None
