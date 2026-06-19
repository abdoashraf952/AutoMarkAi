"""
app/rag/embeddings.py — AutoMark AI CRM Agent (ORCAST)

LangChain-compatible Embeddings backed by the Gemini REST API v1 (httpx).

Why httpx instead of GoogleGenerativeAIEmbeddings?
  - langchain-google-genai 2.0.7 does not forward output_dimensionality to
    the API, so the model returns 3072-d vectors by default.
  - pgvector HNSW only supports ≤ 2000 dimensions.
  - We force outputDimensionality=768 in every REST call to stay within the
    HNSW limit while keeping the full RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY
    task-type distinction.

The public GeminiEmbeddings class implements the LangChain Embeddings
interface, so it works everywhere a LangChain Embeddings object is expected.

Exports:
    gemini_embeddings — LangChain Embeddings singleton (document task type)
    embed_text        — async: single document chunk → vector[768]
    embed_query       — async: search query → vector[768]
    embed_batch       — async: many documents → list[vector[768]]
"""

from __future__ import annotations

import asyncio
from typing import List

import httpx
import structlog
from langchain_core.embeddings import Embeddings

from config import settings

logger = structlog.get_logger(__name__)

_BASE = "https://generativelanguage.googleapis.com/v1"
_MAX_CONCURRENCY = 8

_model_path = settings.GEMINI_EMBEDDING_MODEL
if not _model_path.startswith("models/"):
    _model_path = f"models/{_model_path}"

_EMBED_URL = f"{_BASE}/{_model_path}:embedContent"
_KEY_PARAM = {"key": settings.GEMINI_API_KEY}
_EMBED_DIM = settings.EMBEDDING_DIM  # 768 — matches VECTOR(768) in the DB schema


# ─────────────────────────────────────────────────────────────────────────────
# LangChain Embeddings subclass
# ─────────────────────────────────────────────────────────────────────────────

class GeminiEmbeddings(Embeddings):
    """
    LangChain Embeddings backed by Gemini text-embedding-004 via REST v1.
    Always produces _EMBED_DIM-dimensional vectors regardless of model default.
    """

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await embed_batch(texts)

    async def aembed_query(self, text: str) -> List[float]:
        return await embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return asyncio.run(self.aembed_documents(texts))

    def embed_query(self, text: str) -> List[float]:
        return asyncio.run(self.aembed_query(text))


# ─────────────────────────────────────────────────────────────────────────────
# Async helpers
# ─────────────────────────────────────────────────────────────────────────────

async def embed_text(text: str) -> list[float]:
    """Embed a single document chunk."""
    return await _call(text, task_type="RETRIEVAL_DOCUMENT")


async def embed_query(text: str) -> list[float]:
    """Embed a search query."""
    return await _call(text, task_type="RETRIEVAL_QUERY")


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed many texts in parallel, capped at _MAX_CONCURRENCY."""
    if not texts:
        return []
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)

    async def _one(t: str) -> list[float]:
        async with sem:
            return await _call(t, task_type="RETRIEVAL_DOCUMENT")

    return list(await asyncio.gather(*(_one(t) for t in texts)))


# ─────────────────────────────────────────────────────────────────────────────
# Private REST call
# ─────────────────────────────────────────────────────────────────────────────

async def _call(text: str, task_type: str) -> list[float]:
    payload = {
        "model": _model_path,
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
        "outputDimensionality": _EMBED_DIM,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_EMBED_URL, json=payload, params=_KEY_PARAM)
        resp.raise_for_status()
    return resp.json()["embedding"]["values"]


# ─────────────────────────────────────────────────────────────────────────────
# Module singleton
# ─────────────────────────────────────────────────────────────────────────────

gemini_embeddings = GeminiEmbeddings()
