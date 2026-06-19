"""
main.py — AutoMark AI CRM Agent (ORCAST)
FastAPI application entry point.

Platforms : Facebook Messenger, Facebook Page Comments, Vapi Voice
LLM       : Google Gemini, orchestrated via a LangGraph StateGraph (ORCAST)
Memory    : PostgreSQL + pgvector (rolling-summarization memory + hybrid RAG)
CRM       : HubSpot
Tracing   : LangSmith
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings


# ─────────────────────────────────────────────────────────────────────────────
# Structured logging
# ─────────────────────────────────────────────────────────────────────────────

def configure_logging() -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer = structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer()
    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.LOG_LEVEL)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


configure_logging()
logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info(
        "automark_crm.starting",
        model=settings.GEMINI_MODEL,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        debug=settings.DEBUG,
    )

    # ── PostgreSQL + pgvector ────────────────────────────────────────────────
    try:
        from app.db import init_db

        await init_db()
        logger.info("startup.postgres_ok")
    except Exception as exc:
        logger.error("startup.postgres_error", error=str(exc))
        sys.exit(1)

    # ── ORCAST graph (pre-warm / validate compilation) ──────────────────────
    try:
        from app.graph.orchestrator import compiled_graph  # noqa: F401

        logger.info("startup.orcast_graph_compiled")
    except Exception as exc:
        logger.error("startup.orcast_graph_error", error=str(exc))
        sys.exit(1)

    logger.info("automark_crm.ready")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    from app.db import close_pool

    await close_pool()
    logger.info("automark_crm.shutdown")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AutoMark AI — ORCAST CRM Agent",
    description=(
        "LangGraph + Gemini CRM agent (ORCAST). "
        "Handles Messenger, Facebook Page Comments, and Vapi voice calls."
    ),
    version="3.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
from app.api.messenger import router as messenger_router
from app.api.facebook_comments import router as facebook_router
from app.api.vapi import router as vapi_router

app.include_router(messenger_router, tags=["Messenger"])
app.include_router(facebook_router, tags=["Facebook Page Comments"])
app.include_router(vapi_router, tags=["Vapi"])


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root() -> dict:
    return {"service": "AutoMark AI ORCAST CRM Agent", "version": "3.0.0", "status": "running"}


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {"status": "healthy", "version": "3.0.0"}


@app.get("/health/deep", tags=["Health"])
async def deep_health_check() -> dict:
    import httpx

    results: dict = {"status": "healthy", "checks": {}}

    # PostgreSQL + pgvector
    try:
        from app.db import get_pool
        from app.rag import vector_store

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        results["checks"]["postgres"] = {"status": "ok", "knowledge_base_chunks": await vector_store.count()}
    except Exception as exc:
        results["checks"]["postgres"] = {"status": "error", "error": str(exc)}
        results["status"] = "degraded"

    # HubSpot
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.HUBSPOT_BASE_URL}/crm/v3/objects/contacts?limit=1",
                headers={"Authorization": f"Bearer {settings.HUBSPOT_ACCESS_TOKEN}"},
            )
        results["checks"]["hubspot"] = {
            "status": "ok" if resp.status_code == 200 else "error",
            "http_status": resp.status_code,
        }
    except Exception as exc:
        results["checks"]["hubspot"] = {"status": "error", "error": str(exc)}
        results["status"] = "degraded"

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Admin endpoints (DEBUG only)
# ─────────────────────────────────────────────────────────────────────────────

if settings.DEBUG:

    @app.post("/admin/ingest", tags=["Admin"])
    async def trigger_ingestion(reset: bool = False) -> dict:
        from pathlib import Path

        from app.rag.ingest import DocumentIngester

        ingester = DocumentIngester()
        return await ingester.ingest_directory(Path(settings.KNOWLEDGE_BASE_PATH), reset=reset)

    @app.get("/admin/memory/{user_id}", tags=["Admin"])
    async def get_user_memory(user_id: str) -> dict:
        from app.memory.postgres_memory import postgres_memory

        return await postgres_memory.load(user_id)

    @app.delete("/admin/memory/{user_id}", tags=["Admin"])
    async def clear_user_memory(user_id: str) -> dict:
        from app.memory.postgres_memory import postgres_memory

        await postgres_memory.clear(user_id)
        return {"cleared": True, "user_id": user_id}

    @app.post("/admin/summarize/{user_id}", tags=["Admin"])
    async def trigger_summarize(user_id: str) -> dict:
        from app.memory.postgres_memory import postgres_memory

        summary = await postgres_memory.summarize(user_id)
        return {"user_id": user_id, "summary": summary}

    @app.post("/admin/simulate", tags=["Admin"])
    async def simulate_message(user_id: str, source: str = "messenger", content: str = "Hello") -> dict:
        """Simulate an inbound message without a real webhook — for local testing."""
        from app.graph.orchestrator import run_graph
        from app.services.gemini_service import UnifiedMessage

        message = UnifiedMessage(
            user_id=user_id,
            source=source,
            input_type="text",
            content=content,
            metadata={"simulated": True},
        )
        response = await run_graph(message)
        return {
            "user_id": user_id,
            "input": content,
            "response": response.message,
            "tools_called": response.tools_called,
            "lead_updated": response.lead_updated,
            "escalated": response.escalated,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        workers=1,
    )
