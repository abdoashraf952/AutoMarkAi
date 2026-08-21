"""
src/shared/db.py — AutoMark AI (unified)

One database, one init. Every module in the project reads and writes the same
PostgreSQL database through this module.

Two engines are exposed against that one database because the modules differ in
concurrency model, not in storage:

    async_engine  — asyncpg driver, used by the CRM agent (FastAPI webhooks,
                    RAG retrieval, conversation memory).
    sync_engine   — psycopg2 driver, used by the campaign pipeline and the
                    analytics agents, which run synchronously (LangGraph nodes
                    and pandas both block).

`init_all()` is the single schema entry point: it creates the pgvector
extension and then emits every table in shared.models in one pass.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from src.config import settings
from src.shared.models import Base

logger = logging.getLogger(__name__)

# Engines are built lazily so that importing this module never opens a socket —
# tests and CLI tools can import the app without a running database.
_async_engine: AsyncEngine | None = None
_sync_engine: Engine | None = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None
_SyncSessionLocal: sessionmaker[Session] | None = None


# ── Engine accessors ─────────────────────────────────────────────────────────

def get_async_engine() -> AsyncEngine:
    global _async_engine, _AsyncSessionLocal
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.async_database_url,
            echo=settings.DB_ECHO,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        _AsyncSessionLocal = async_sessionmaker(
            bind=_async_engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("db: async engine created")
    return _async_engine


def get_sync_engine() -> Engine:
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.sync_database_url,
            echo=settings.DB_ECHO,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        _SyncSessionLocal = sessionmaker(
            bind=_sync_engine, autocommit=False, autoflush=False
        )
        logger.info("db: sync engine created")
    return _sync_engine


# ── Session helpers ──────────────────────────────────────────────────────────

@asynccontextmanager
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session that commits on success and rolls back on error."""
    get_async_engine()
    assert _AsyncSessionLocal is not None
    session = _AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@contextmanager
def sync_session() -> Generator[Session, None, None]:
    """Sync session that commits on success and rolls back on error."""
    get_sync_engine()
    assert _SyncSessionLocal is not None
    session = _SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Backwards-compatible alias for the analytics module, which imported `get_db`.
get_db = sync_session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an AsyncSession."""
    async with async_session() as session:
        yield session


# ── Schema initialisation ────────────────────────────────────────────────────

async def init_all() -> None:
    """Create the pgvector extension and every table declared in shared.models.

    Safe to call repeatedly — everything is IF NOT EXISTS. This is the only
    place in the project that creates schema.
    """
    engine = get_async_engine()
    async with engine.begin() as conn:
        # pgvector must exist before the document_chunks VECTOR column is
        # created, and before its HNSW index can be built.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("db: schema ready (crm + campaigns + analytics)")


def init_all_sync() -> None:
    """Blocking variant of init_all() for CLI tools and Streamlit."""
    engine = get_sync_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=conn)
    logger.info("db: schema ready (crm + campaigns + analytics)")


async def dispose_all() -> None:
    """Close both engines. Call on application shutdown."""
    global _async_engine, _sync_engine, _AsyncSessionLocal, _SyncSessionLocal
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _AsyncSessionLocal = None
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
        _SyncSessionLocal = None
    logger.info("db: engines disposed")


async def healthcheck() -> dict:
    """Ping the database and report row counts used by /health/deep."""
    engine = get_async_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        chunks = await conn.scalar(text("SELECT COUNT(*) FROM document_chunks"))
    return {"status": "ok", "knowledge_base_chunks": int(chunks or 0)}
