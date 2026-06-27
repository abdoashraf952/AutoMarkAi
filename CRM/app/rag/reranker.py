"""
app/rag/reranker.py — AutoMark AI CRM Agent (ORCAST)

LangChain BaseDocumentCompressor that re-ranks retrieved Documents.

Two backends (RERANKER_BACKEND in .env):
    gemini        (default) — Gemini ranks chunk indices via a JSON-array
                              prompt. No extra dependencies.
    cross-encoder — sentence-transformers CrossEncoder, lazy-loaded.

Composes natively with LangChain's ContextualCompressionRetriever.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

import structlog
from langchain_core.callbacks import Callbacks
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor

from config import settings

logger = structlog.get_logger(__name__)

_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_cross_encoder: Any = None


class GeminiReranker(BaseDocumentCompressor):
    """
    Re-rank Documents against the query, returning the top_k most relevant.
    Backend is chosen by settings.RERANKER_BACKEND ('gemini' | 'cross-encoder').

    Compatible with LangChain's ContextualCompressionRetriever:
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=gemini_reranker,
            base_retriever=hybrid_retriever,
        )
    """

    top_k: int = 5

    class Config:
        arbitrary_types_allowed = True

    async def acompress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        docs = list(documents)
        if not docs or len(docs) <= self.top_k:
            return docs
        if settings.RERANKER_BACKEND == "cross-encoder":
            return await _rerank_cross_encoder(query, docs, self.top_k)
        return await _rerank_gemini(query, docs, self.top_k)

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        import asyncio
        return asyncio.run(self.acompress_documents(documents, query, callbacks))


# ─────────────────────────────────────────────────────────────────────────────
# Gemini reranking backend
# ─────────────────────────────────────────────────────────────────────────────

async def _rerank_gemini(query: str, docs: list[Document], top_k: int) -> list[Document]:
    from app.services.gemini_service import gemini_service

    numbered = "\n\n".join(f"[{i}] {doc.page_content[:500]}" for i, doc in enumerate(docs))
    prompt = (
        "Rank the following numbered passages by relevance to the QUERY. "
        f"Return ONLY a JSON array of passage numbers, best-first, max {top_k} items.\n\n"
        f"QUERY: {query}\n\nPASSAGES:\n{numbered}\n\nJSON array:"
    )

    try:
        response = await gemini_service.generate_text(prompt, temperature=0.0)
        cleaned = response.strip().strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
        indices = json.loads(cleaned)
        ranked = [docs[i] for i in indices if isinstance(i, int) and 0 <= i < len(docs)]
        if ranked:
            return ranked[:top_k]
    except Exception as exc:
        logger.warning("reranker.gemini.error", error=str(exc))

    return docs[:top_k]


# ─────────────────────────────────────────────────────────────────────────────
# Cross-encoder backend (lazy-loaded)
# ─────────────────────────────────────────────────────────────────────────────

async def _rerank_cross_encoder(query: str, docs: list[Document], top_k: int) -> list[Document]:
    global _cross_encoder
    try:
        if _cross_encoder is None:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder(_CROSS_ENCODER_MODEL)

        pairs = [(query, doc.page_content) for doc in docs]
        scores = _cross_encoder.predict(pairs)
        ranked = [d for _, d in sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)]
        return ranked[:top_k]
    except Exception as exc:
        logger.warning("reranker.cross_encoder.error", error=str(exc))
        return docs[:top_k]


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

gemini_reranker = GeminiReranker(top_k=settings.RAG_TOP_K)