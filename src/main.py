"""
src/main.py — AutoMark AI

Single FastAPI application for all three modules:

    CRM        — Messenger / Facebook Comments / Vapi webhooks, ORCAST agent
    Campaigns  — Meta ad pipeline with human-in-the-loop approvals
    Analytics  — dataset profiling, KPI discovery, insights, reporting

They share one PostgreSQL database (src/shared/db.py), one schema init, and one
JWT identity (src/shared/auth.py).

URL layout
----------
    /messenger/webhook, /facebook/webhook, /vapi/webhook
        CRM webhooks — deliberately left un-prefixed, because these URLs are
        registered in the Meta and Vapi dashboards and must not change.
    /api/auth/*         register, login
    /api/crm/*          CRM admin + database browsing
    /api/campaigns/*    campaign sessions, HITL, publish
    /api/analytics/*    dataset analysis, KPIs, insights, chat
    /health, /health/deep, /docs
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import settings

APP_VERSION = "4.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# Structured logging
# ─────────────────────────────────────────────────────────────────────────────

def configure_logging() -> None:
    # Log lines throughout this project contain box-drawing characters, em
    # dashes, and arrows. On Windows stdout defaults to cp1252, which cannot
    # encode them — the log call then raises UnicodeEncodeError and the event
    # is lost (and, inside a try/except, misreported as the operation failing).
    # Force UTF-8 so a log line can never take down the code that emitted it.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]
    renderer = (
        structlog.dev.ConsoleRenderer(sort_keys=False)
        if settings.LOG_FORMAT == "console"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.LOG_LEVEL)
        ),
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
        "automark.starting",
        version=APP_VERSION,
        model=settings.GEMINI_MODEL,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        debug=settings.DEBUG,
    )

    # ── One database, one init ───────────────────────────────────────────────
    try:
        from src.shared.db import init_all

        await init_all()
        logger.info("startup.database_ok")
    except Exception as exc:
        logger.error("startup.database_error", error=str(exc))
        sys.exit(1)

    # ── CRM: pre-warm / validate the ORCAST graph ────────────────────────────
    try:
        from src.crm.graph.orchestrator import compiled_graph  # noqa: F401

        logger.info("startup.crm_graph_compiled")
    except Exception as exc:
        logger.error("startup.crm_graph_error", error=str(exc))
        sys.exit(1)

    # ── Campaigns: lifecycle scheduler (non-fatal) ───────────────────────────
    try:
        from src.campaigns.api import start_scheduler

        await start_scheduler()
        logger.info("startup.campaign_scheduler_ok")
    except Exception as exc:
        logger.warning("startup.campaign_scheduler_failed", error=str(exc))

    # ── CRM: HubSpot connectivity check (non-fatal) ──────────────────────────
    try:
        from src.crm.services.hubspot_service import hubspot_service

        hs = await hubspot_service.check_scopes()
        if hs["ok"]:
            logger.info("startup.hubspot_ok")
        else:
            logger.warning(
                "startup.hubspot_misconfigured",
                status=hs["status"],
                detail=hs["detail"],
                action=(
                    "HubSpot CRM features will be skipped until this is fixed. "
                    "The agent will still answer questions and escalate via email."
                ),
            )
    except Exception as exc:
        logger.warning("startup.hubspot_check_failed", error=str(exc))

    logger.info("automark.ready")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    try:
        from src.campaigns.api import stop_scheduler

        await stop_scheduler()
    except Exception as exc:
        logger.warning("shutdown.campaign_scheduler_error", error=str(exc))

    from src.shared.db import dispose_all

    await dispose_all()
    logger.info("automark.shutdown")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AutoMark AI",
    description=(
        "Unified CRM, campaign-generation, and analytics platform. "
        "LangGraph + Gemini agents over one PostgreSQL + pgvector database."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Auth — app-wide identity
# ─────────────────────────────────────────────────────────────────────────────

auth_router = APIRouter(prefix="/api/auth", tags=["Auth"])


class AuthBody(BaseModel):
    email: str
    password: str


@auth_router.post("/register", summary="Register a new account")
async def register(body: AuthBody) -> dict:
    from src.shared.auth import create_token, create_user

    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if "@" not in body.email:
        raise HTTPException(400, "Invalid email address")

    user = await create_user(body.email, body.password)
    token = create_token(user["id"], user["email"])
    return {"token": token, "user_id": user["id"], "email": user["email"]}


@auth_router.post("/login", summary="Login with email + password")
async def login(body: AuthBody) -> dict:
    from src.shared.auth import authenticate, create_token

    user = await authenticate(body.email, body.password)
    token = create_token(user["id"], user["email"])
    return {"token": token, "user_id": user["id"], "email": user["email"]}


# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

from src.analytics.api import router as analytics_router
from src.campaigns.api import router as campaigns_router
from src.crm.api.admin import router as crm_admin_router
from src.crm.api.facebook_comments import router as facebook_router
from src.crm.api.messenger import router as messenger_router
from src.crm.api.vapi import router as vapi_router

app.include_router(auth_router)

# CRM webhooks stay at the root — these URLs are registered with Meta and Vapi.
app.include_router(messenger_router, tags=["CRM · Messenger"])
app.include_router(facebook_router, tags=["CRM · Facebook Comments"])
app.include_router(vapi_router, tags=["CRM · Vapi"])
app.include_router(crm_admin_router, prefix="/api/crm")

app.include_router(campaigns_router, prefix="/api/campaigns")
app.include_router(analytics_router, prefix="/api/analytics")


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root() -> dict:
    return {
        "service": "AutoMark AI",
        "version": APP_VERSION,
        "status": "running",
        "modules": ["crm", "campaigns", "analytics"],
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {"status": "healthy", "version": APP_VERSION}


@app.get("/health/deep", tags=["Health"])
async def deep_health_check() -> dict:
    import httpx

    results: dict = {"status": "healthy", "version": APP_VERSION, "checks": {}}

    # PostgreSQL + pgvector
    try:
        from src.shared.db import healthcheck

        results["checks"]["postgres"] = await healthcheck()
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
# CRM admin utilities
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/crm/hubspot/check", tags=["CRM · Admin"])
async def hubspot_check() -> dict:
    """Test HubSpot connectivity and scope configuration.

    Use this whenever you see hubspot_service.permission_error in the logs.
    """
    from src.crm.services.hubspot_service import hubspot_service

    result = await hubspot_service.check_scopes()
    if not result["ok"]:
        result["fix_steps"] = [
            "1. Log in to HubSpot (app.hubspot.com)",
            "2. Go to Settings → Integrations → Private Apps",
            "3. Click your AutoMark app",
            "4. Click the 'Scopes' tab",
            "5. Enable ALL of the scopes listed in 'missing_scopes'",
            "6. Click 'Save changes' — no restart needed",
        ]
    return result


if settings.DEBUG:

    @app.post("/api/crm/ingest", tags=["CRM · Admin"])
    async def trigger_ingestion(reset: bool = False) -> dict:
        from pathlib import Path

        from src.crm.rag.ingest import DocumentIngester

        ingester = DocumentIngester()
        return await ingester.ingest_directory(
            Path(settings.KNOWLEDGE_BASE_PATH), reset=reset
        )

    @app.get("/api/crm/memory/{user_id}", tags=["CRM · Admin"])
    async def get_user_memory(user_id: str) -> dict:
        from src.crm.memory.postgres_memory import postgres_memory

        return await postgres_memory.load(user_id)

    @app.delete("/api/crm/memory/{user_id}", tags=["CRM · Admin"])
    async def clear_user_memory(user_id: str) -> dict:
        from src.crm.memory.postgres_memory import postgres_memory

        await postgres_memory.clear(user_id)
        return {"cleared": True, "user_id": user_id}

    @app.post("/api/crm/summarize/{user_id}", tags=["CRM · Admin"])
    async def trigger_summarize(user_id: str) -> dict:
        from src.crm.memory.postgres_memory import postgres_memory

        summary = await postgres_memory.summarize(user_id)
        return {"user_id": user_id, "summary": summary}

    @app.post("/api/crm/simulate", tags=["CRM · Admin"])
    async def simulate_message(
        user_id: str, source: str = "messenger", content: str = "Hello"
    ) -> dict:
        """Simulate an inbound message without a real webhook — for local testing."""
        from src.crm.graph.orchestrator import run_graph
        from src.crm.services.gemini_service import UnifiedMessage

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
        "src.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        workers=1,
    )
