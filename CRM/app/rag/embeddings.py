"""
app/rag/embeddings.py — AutoMark AI CRM Agent (ORCAST)

LangChain-compatible Embeddings backed by the google-generativeai SDK.

Uses the SDK (not raw httpx) so the API key and endpoint are handled
consistently with the rest of the Gemini calls in this project.

Forces outputDimensionality=768 to match the VECTOR(768) pgvector schema
while keeping task-type distinction (RETRIEVAL_DOCUMENT vs RETRIEVAL_QUERY).

Exports:
    gemini_embeddings — LangChain Embeddings singleton (document task type)
    embed_text        — async: single document chunk -> vector[768]
    embed_query       — async: search query -> vector[768]
    embed_batch       — async: many documents -> list[vector[768]]
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import List

import structlog
from langchain_core.embeddings import Embeddings

from config import settings

logger = structlog.get_logger(__name__)

_EMBED_DIM  = settings.EMBEDDING_DIM        # 768 — matches VECTOR(768) in DB
_MODEL      = settings.GEMINI_EMBEDDING_MODEL
_MAX_WORKERS = 4
_executor   = concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="embed")


# ─────────────────────────────────────────────────────────────────────────────
# Blocking SDK call (runs in thread pool to avoid blocking the event loop)
# ─────────────────────────────────────────────────────────────────────────────

def _sync_embed(text: str, task_type: str) -> list[float]:
    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)
    result = genai.embed_content(
        model=_MODEL,
        content=text,
        task_type=task_type,
        output_dimensionality=_EMBED_DIM,
    )
    return result["embedding"]


async def _call(text: str, task_type: str) -> list[float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_embed, text, task_type)


# ─────────────────────────────────────────────────────────────────────────────
# LangChain Embeddings subclass
# ─────────────────────────────────────────────────────────────────────────────

class GeminiEmbeddings(Embeddings):
    """
    LangChain Embeddings backed by google-generativeai SDK.
    Produces _EMBED_DIM-dimensional vectors (768 by default).
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
# Async public helpers
# ─────────────────────────────────────────────────────────────────────────────

async def embed_text(text: str) -> list[float]:
    """Embed a single document chunk."""
    return await _call(text, task_type="RETRIEVAL_DOCUMENT")


async def embed_query(text: str) -> list[float]:
    """Embed a search query."""
    return await _call(text, task_type="RETRIEVAL_QUERY")


async def embed_batch(texts: list[str], max_concurrency: int = 8) -> list[list[float]]:
    """Embed many texts in parallel, capped at max_concurrency."""
    if not texts:
        return []
    sem = asyncio.Semaphore(max_concurrency)

    async def _one(t: str) -> list[float]:
        async with sem:
            return await _call(t, task_type="RETRIEVAL_DOCUMENT")

    return list(await asyncio.gather(*(_one(t) for t in texts)))


# ─────────────────────────────────────────────────────────────────────────────
# Module singleton
# ─────────────────────────────────────────────────────────────────────────────

gemini_embeddings = GeminiEmbeddings()
