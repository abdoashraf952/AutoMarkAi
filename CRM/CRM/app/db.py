"""
app/db.py — AutoMark AI CRM Agent (ORCAST)

Shared asyncpg connection pool used by app/memory and app/rag.
A single module-level pool avoids circular imports between the two.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import asyncpg
import structlog
from pgvector.asyncpg import register_vector

from config import settings

logger = structlog.get_logger(__name__)

_pool: Optional[asyncpg.Pool] = None

_INIT_SQL_PATH = Path(__file__).resolve().parent.parent / "scripts" / "init_db.sql"


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register the pgvector type codec on every pooled connection.
    Silently skipped if the `vector` extension hasn't been created yet
    (e.g. on the very first call to init_db())."""
    try:
        await register_vector(conn)
    except Exception:
        pass


async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
            init=_init_connection,
        )
        logger.info("db.pool.created")
    return _pool


async def close_pool() -> None:
    """Gracefully close all connections. Call on FastAPI shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("db.pool.closed")


async def init_db() -> None:
    """Execute scripts/init_db.sql to create the schema if it doesn't exist."""
    sql = _INIT_SQL_PATH.read_text(encoding="utf-8")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(sql)

    # Recreate the pool so every connection picks up the pgvector type that
    # CREATE EXTENSION may have just registered for the first time.
    await close_pool()
    await get_pool()

    logger.info("db.schema.initialised")
