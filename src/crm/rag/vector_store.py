"""
src/crm/rag/vector_store.py — AutoMark AI (unified)

pgvector-backed storage for document_chunks: dense (cosine) search, sparse
(full-text) search, and idempotent upsert.

Backed by the shared SQLAlchemy async engine (src/shared/db.py). The ranking
semantics are unchanged from the original asyncpg implementation:
  dense  — 1 - cosine_distance, ordered ascending by distance
  sparse — ts_rank_cd over the stored ts_content column

The embedding column width must match EMBEDDING_DIM in settings (default 768);
gemini embeddings are truncated to that via output_dimensionality in
embeddings.py.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from src.shared.db import async_session
from src.shared.models import DocumentChunk

logger = structlog.get_logger(__name__)


async def upsert_chunks(chunks: list[dict[str, Any]]) -> int:
    """
    Insert or update document chunks.

    Each chunk dict requires:
        doc_id, source_file, chunk_index, content,
        token_count, embedding (list[float]), metadata (dict).

    Idempotent: re-ingesting the same (doc_id, chunk_index) updates in place.
    """
    if not chunks:
        return 0

    # Keys are ORM attribute names, not column names. The JSONB column is
    # called "metadata" in SQL but is mapped to `doc_metadata`, because
    # `DocumentChunk.metadata` is SQLAlchemy's own MetaData object.
    rows = [
        {
            "doc_id": c["doc_id"],
            "source_file": c["source_file"],
            "chunk_index": c["chunk_index"],
            "content": c["content"],
            "token_count": c.get("token_count", 0),
            "embedding": c["embedding"],
            "doc_metadata": c.get("metadata", {}),
        }
        for c in chunks
    ]

    stmt = insert(DocumentChunk).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DocumentChunk.doc_id, DocumentChunk.chunk_index],
        set_={
            "source_file": stmt.excluded.source_file,
            "content": stmt.excluded.content,
            "token_count": stmt.excluded.token_count,
            "embedding": stmt.excluded.embedding,
            # `set_` and `excluded` are both keyed by column key ("metadata"),
            # while .values() above is keyed by ORM attribute
            # ("doc_metadata"). Both name the same column.
            "metadata": stmt.excluded["metadata"],
        },
    )

    async with async_session() as session:
        await session.execute(stmt)

    logger.info("vector_store.upserted", chunks=len(chunks))
    return len(chunks)


async def dense_search(query_embedding: list[float], top_k: int = 20) -> list[dict[str, Any]]:
    """Cosine-similarity search via pgvector's <=> operator."""
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.doc_id,
            DocumentChunk.source_file,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            DocumentChunk.doc_metadata.label("metadata"),
            (1 - distance).label("score"),
        )
        .order_by(distance)
        .limit(top_k)
    )
    async with async_session() as session:
        result = await session.execute(stmt)
        return [_row_to_dict(r) for r in result.mappings()]


async def sparse_search(query: str, top_k: int = 20) -> list[dict[str, Any]]:
    """Full-text search via ts_rank_cd + plainto_tsquery."""
    tsquery = func.plainto_tsquery("english", query)
    score = func.ts_rank_cd(DocumentChunk.ts_content, tsquery)
    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.doc_id,
            DocumentChunk.source_file,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            DocumentChunk.doc_metadata.label("metadata"),
            score.label("score"),
        )
        .where(DocumentChunk.ts_content.op("@@")(tsquery))
        .order_by(score.desc())
        .limit(top_k)
    )
    async with async_session() as session:
        result = await session.execute(stmt)
        return [_row_to_dict(r) for r in result.mappings()]


async def get_chunks_by_ids(ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    stmt = select(
        DocumentChunk.id,
        DocumentChunk.doc_id,
        DocumentChunk.source_file,
        DocumentChunk.chunk_index,
        DocumentChunk.content,
        DocumentChunk.doc_metadata.label("metadata"),
    ).where(DocumentChunk.id.in_(ids))
    async with async_session() as session:
        result = await session.execute(stmt)
        return [_row_to_dict(r) for r in result.mappings()]


async def delete_by_doc_id(doc_id: str) -> int:
    async with async_session() as session:
        result = await session.execute(
            delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id)
        )
    deleted = result.rowcount or 0
    logger.info("vector_store.deleted", doc_id=doc_id, rows=deleted)
    return deleted


async def count() -> int:
    async with async_session() as session:
        return int(await session.scalar(select(func.count()).select_from(DocumentChunk)) or 0)


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    if d.get("metadata") is None:
        d["metadata"] = {}
    if d.get("score") is not None:
        d["score"] = float(d["score"])
    return d
