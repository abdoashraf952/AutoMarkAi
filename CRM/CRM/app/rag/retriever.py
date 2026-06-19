"""
app/rag/retriever.py — AutoMark AI CRM Agent (ORCAST)

LangChain BaseRetriever wrapping hybrid dense + sparse search fused via
Reciprocal Rank Fusion (RRF). Returns list[Document] so it composes natively
with LangChain's ContextualCompressionRetriever and LCEL chains.

Exports:
    HybridRetriever  — LangChain BaseRetriever subclass
    hybrid_retriever — module-level singleton
    retrieve()       — async helper → list[Document]
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

import structlog
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langsmith import traceable

from app.rag import vector_store
from app.rag.embeddings import embed_query
from config import settings

logger = structlog.get_logger(__name__)

DENSE_TOP_K = 20
SPARSE_TOP_K = 20
FUSED_TOP_K = 20
RRF_K = 60


# ─────────────────────────────────────────────────────────────────────────────
# RRF helper
# ─────────────────────────────────────────────────────────────────────────────

def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[int]:
    """
    Reciprocal Rank Fusion over multiple ranked ID lists.
    Returns fused list of IDs, best-first, deduplicated.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda cid: scores[cid], reverse=True)


def _chunk_to_document(chunk: dict[str, Any]) -> Document:
    return Document(
        page_content=chunk["content"],
        metadata={
            "id": chunk["id"],
            "doc_id": chunk.get("doc_id", ""),
            "source_file": chunk.get("source_file", ""),
            "chunk_index": chunk.get("chunk_index", 0),
            **chunk.get("metadata", {}),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# LangChain BaseRetriever
# ─────────────────────────────────────────────────────────────────────────────

class HybridRetriever(BaseRetriever):
    """
    Hybrid retriever: dense (pgvector cosine) + sparse (PostgreSQL full-text)
    fused via RRF. Implements LangChain BaseRetriever so it composes natively
    with ContextualCompressionRetriever and LCEL chains.

    Usage in an LCEL chain:
        chain = hybrid_retriever | format_docs | prompt | llm

    Usage with reranker:
        from langchain.retrievers import ContextualCompressionRetriever
        from app.rag.reranker import gemini_reranker

        compressed = ContextualCompressionRetriever(
            base_compressor=gemini_reranker,
            base_retriever=hybrid_retriever,
        )
    """

    top_k: int = FUSED_TOP_K

    class Config:
        arbitrary_types_allowed = True

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[Any] = None,
    ) -> List[Document]:
        if not query.strip():
            return []

        query_embedding = await embed_query(query)

        dense_results, sparse_results = await asyncio.gather(
            vector_store.dense_search(query_embedding, top_k=DENSE_TOP_K),
            vector_store.sparse_search(query, top_k=SPARSE_TOP_K),
        )

        chunks_by_id: dict[int, dict[str, Any]] = {}
        for chunk in dense_results + sparse_results:
            chunks_by_id.setdefault(chunk["id"], chunk)

        fused_ids = rrf_fuse(
            [[c["id"] for c in dense_results], [c["id"] for c in sparse_results]]
        )[: self.top_k]

        documents = [_chunk_to_document(chunks_by_id[cid]) for cid in fused_ids if cid in chunks_by_id]

        logger.info(
            "retriever.retrieve.done",
            query_preview=query[:60],
            dense=len(dense_results),
            sparse=len(sparse_results),
            fused=len(documents),
        )
        return documents

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None,
    ) -> List[Document]:
        return asyncio.run(self._aget_relevant_documents(query))


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

hybrid_retriever = HybridRetriever(top_k=FUSED_TOP_K)


# ─────────────────────────────────────────────────────────────────────────────
# Backwards-compatible async helper
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="rag_retrieve")
async def retrieve(query: str, top_k: int = FUSED_TOP_K) -> list[Document]:
    """Async shortcut: returns list[Document] ordered best-first."""
    return await HybridRetriever(top_k=top_k)._aget_relevant_documents(query)