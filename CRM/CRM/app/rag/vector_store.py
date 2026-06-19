"""
app/rag/vector_store.py — AutoMark AI CRM Agent (ORCAST)

pgvector-backed storage for document_chunks: dense (cosine) search,
sparse (full-text) search, and idempotent upsert.

The embedding column must match EMBEDDING_DIM in settings (default 768).
gemini-embedding-2 is truncated to 768 via output_dimensionality in embeddings.py.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from app.db import get_pool

logger = structlog.get_logger(__name__)


async def upsert_chunks(chunks: list[dict[str, Any]]) -> int:
    """
    Insert or update document chunks.

    Each chunk dict requires:
        doc_id, source_file, chunk_index, content,
        token_count, embedding (list[float], 768-d), metadata (dict).

    Idempotent: re-ingesting the same (doc_id, chunk_index) updates in place.
    """
    if not chunks:
        return 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for chunk in chunks:
                await conn.execute(
                    """
                    INSERT INTO document_chunks
                        (doc_id, source_file, chunk_index, content, token_count, embedding, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (doc_id, chunk_index) DO UPDATE
                    SET source_file = EXCLUDED.source_file,
                        content     = EXCLUDED.content,
                        token_count = EXCLUDED.token_count,
                        embedding   = EXCLUDED.embedding,
                        metadata    = EXCLUDED.metadata
                    """,
                    chunk["doc_id"],
                    chunk["source_file"],
                    chunk["chunk_index"],
                    chunk["content"],
                    chunk.get("token_count", 0),
                    chunk["embedding"],
                    json.dumps(chunk.get("metadata", {})),
                )

    logger.info("vector_store.upserted", chunks=len(chunks))
    return len(chunks)


async def dense_search(query_embedding: list[float], top_k: int = 20) -> list[dict[str, Any]]:
    """Cosine-similarity search via pgvector's <=> operator."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, doc_id, source_file, chunk_index, content, metadata,
                   1 - (embedding <=> $1) AS score
            FROM document_chunks
            ORDER BY embedding <=> $1
            LIMIT $2
            """,
            query_embedding,
            top_k,
        )
    return [_row_to_dict(r) for r in rows]


async def sparse_search(query: str, top_k: int = 20) -> list[dict[str, Any]]:
    """Full-text search via ts_rank_cd + plainto_tsquery."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, doc_id, source_file, chunk_index, content, metadata,
                   ts_rank_cd(ts_content, plainto_tsquery('english', $1)) AS score
            FROM document_chunks
            WHERE ts_content @@ plainto_tsquery('english', $1)
            ORDER BY score DESC
            LIMIT $2
            """,
            query,
            top_k,
        )
    return [_row_to_dict(r) for r in rows]


async def get_chunks_by_ids(ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, doc_id, source_file, chunk_index, content, metadata
            FROM document_chunks
            WHERE id = ANY($1::bigint[])
            """,
            ids,
        )
    return [_row_to_dict(r) for r in rows]


async def delete_by_doc_id(doc_id: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM document_chunks WHERE doc_id = $1", doc_id)
    deleted = int(result.split()[-1]) if result else 0
    logger.info("vector_store.deleted", doc_id=doc_id, rows=deleted)
    return deleted


async def count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM document_chunks")


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    if isinstance(d.get("metadata"), str):
        d["metadata"] = json.loads(d["metadata"])
    if d.get("score") is not None:
        d["score"] = float(d["score"])
    return d