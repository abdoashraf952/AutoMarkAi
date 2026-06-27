"""
CRM/main.py — AutoMark AI CRM Agent (ORCAST)

FastAPI application entry point. Registers all webhook routers and manages
the asyncpg connection pool + LangGraph compilation lifecycle.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the repo root (parent of CRM/) is on sys.path so `config.py` is importable.
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from app.db import close_pool, init_db
from app.graph.orchestrator import compiled_graph  # import triggers graph compilation
from app.api import messenger, facebook_comments, vapi

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("crm.startup.begin")
    await init_db()
    logger.info("crm.startup.complete", graph_nodes=len(compiled_graph.nodes))
    yield
    logger.info("crm.shutdown.begin")
    await close_pool()
    logger.info("crm.shutdown.complete")


app = FastAPI(
    title="AutoMark AI CRM Agent (ORCAST)",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(messenger.router, tags=["messenger"])
app.include_router(facebook_comments.router, tags=["facebook"])
app.include_router(vapi.router, tags=["vapi"])


@app.get("/")
async def root():
    return {"service": "AutoMark AI CRM Agent (ORCAST)", "version": "3.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)
