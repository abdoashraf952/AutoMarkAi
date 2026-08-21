"""
app/rag/ingest.py — AutoMark AI CRM Agent (ORCAST)

Document ingestion pipeline for the hybrid RAG knowledge base.
All loaders are LangChain-native. Gemini Vision is used only as a
fallback for scanned PDFs and for image description (no LangChain equivalent).

Supported formats: PDF, DOCX, TXT, MD, JSON (FAQ), images (PNG/JPG).

Pipeline: Load → Split (RecursiveCharacterTextSplitter) → Embed →
          Upsert into document_chunks (pgvector).

Run directly:
    python -m app.rag.ingest --source ./knowledge_base [--reset]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import structlog
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredImageLoader,
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import settings
from src.crm.rag import vector_store
from src.crm.rag.embeddings import embed_batch
from src.crm.services.gemini_service import gemini_service

logger = structlog.get_logger(__name__)

# ── Chunking constants ────────────────────────────────────────────────────────
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200
MIN_CHUNK_LENGTH = 50

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".json", ".png", ".jpg", ".jpeg"}
_IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks. Returns [] for empty or too-short text."""
    if not text or len(text) < MIN_CHUNK_LENGTH:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
    )
    return splitter.split_text(text)


# ─────────────────────────────────────────────────────────────────────────────
# LangChain-native loaders
# ─────────────────────────────────────────────────────────────────────────────

async def _load_pdf(path: Path) -> list[Document]:
    """PyPDFLoader with Gemini Vision fallback for scanned PDFs."""
    try:
        loader = PyPDFLoader(str(path))
        docs = await asyncio.to_thread(loader.load)
        for i, doc in enumerate(docs):
            doc.metadata.setdefault("page", i + 1)
        return docs
    except Exception as exc:
        logger.warning("ingest.pdf.loader_failed", file=str(path), error=str(exc))
        try:
            text = await gemini_service.extract_pdf_text(path.read_bytes())
            return [Document(page_content=text, metadata={"source": str(path)})]
        except Exception as exc2:
            logger.error("ingest.pdf.fallback_failed", file=str(path), error=str(exc2))
            return []


async def _load_docx(path: Path) -> list[Document]:
    try:
        loader = Docx2txtLoader(str(path))
        return await asyncio.to_thread(loader.load)
    except Exception as exc:
        logger.error("ingest.docx.error", file=str(path), error=str(exc))
        return []


async def _load_text(path: Path) -> list[Document]:
    try:
        loader = TextLoader(str(path), encoding="utf-8")
        return await asyncio.to_thread(loader.load)
    except Exception as exc:
        logger.error("ingest.text.error", file=str(path), error=str(exc))
        return []


async def _load_faq_json(path: Path) -> list[Document]:
    """Expected format: [{"question": "...", "answer": "..."}, ...]"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        parts = [
            f"Q: {item['question'].strip()}\nA: {item['answer'].strip()}"
            for item in data
            if item.get("question") and item.get("answer")
        ]
        if parts:
            return [Document(
                page_content="\n\n".join(parts),
                metadata={"source": str(path)},
            )]
        return []
    except Exception as exc:
        logger.error("ingest.json.error", file=str(path), error=str(exc))
        return []


async def _load_image(path: Path) -> list[Document]:
    """
    Try LangChain UnstructuredImageLoader first (OCR-based).
    Fall back to Gemini Vision description if Unstructured is unavailable.
    """
    try:
        loader = UnstructuredImageLoader(str(path))
        docs = await asyncio.to_thread(loader.load)
        if docs and any(d.page_content.strip() for d in docs):
            return docs
    except Exception:
        pass  # Unstructured not installed — use Gemini Vision fallback

    try:
        mime = _IMAGE_MIME.get(path.suffix.lower(), "image/jpeg")
        description = await gemini_service.describe_image(path.read_bytes(), mime)
        if description.strip():
            return [Document(
                page_content=description,
                metadata={"source": str(path), "file_type": "image"},
            )]
    except Exception as exc:
        logger.error("ingest.image.error", file=str(path), error=str(exc))
    return []


async def load_document(path: Path) -> tuple[list[Document], str]:
    """Dispatch to the correct loader. Returns (documents, file_type)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return await _load_pdf(path), "pdf"
    elif suffix in (".docx", ".doc"):
        return await _load_docx(path), "docx"
    elif suffix in (".txt", ".md"):
        return await _load_text(path), "txt"
    elif suffix == ".json":
        return await _load_faq_json(path), "faq"
    elif suffix in _IMAGE_MIME:
        return await _load_image(path), "image"
    else:
        logger.warning("ingest.unsupported_format", file=str(path))
        return [], "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _doc_id(file_path: Path) -> str:
    return hashlib.md5(str(file_path).encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Document Ingester
# ─────────────────────────────────────────────────────────────────────────────

class DocumentIngester:

    async def ingest_file(self, file_path: Path) -> int:
        """Ingest a single file. Returns the number of chunks stored."""
        logger.info("ingest.file.start", file=str(file_path))

        raw_docs, file_type = await load_document(file_path)
        if not raw_docs:
            logger.warning("ingest.file.empty", file=str(file_path))
            return 0

        chunks: list[Document] = _splitter.split_documents(raw_docs)
        chunks = [c for c in chunks if len(c.page_content.strip()) >= MIN_CHUNK_LENGTH]

        if not chunks:
            logger.warning("ingest.file.no_chunks", file=str(file_path))
            return 0

        texts = [c.page_content for c in chunks]
        embeddings = await embed_batch(texts)
        doc_id = _doc_id(file_path)

        records = [
            {
                "doc_id": doc_id,
                "source_file": file_path.name,
                "chunk_index": i,
                "content": chunk.page_content,
                "token_count": len(chunk.page_content) // 4,
                "embedding": embeddings[i],
                "metadata": {
                    "file_type": file_type,
                    "total_chunks": len(chunks),
                    **{k: v for k, v in chunk.metadata.items() if k != "source"},
                },
            }
            for i, chunk in enumerate(chunks)
        ]

        await vector_store.upsert_chunks(records)
        logger.info("ingest.file.done", file=str(file_path), chunks_stored=len(records))
        return len(records)

    async def ingest_directory(self, directory: Path, reset: bool = False) -> dict:
        """Ingest all supported documents in a directory (recursively)."""
        if not directory.exists():
            logger.error("ingest.directory.not_found", path=str(directory))
            return {"files_processed": 0, "chunks_stored": 0, "errors": 0}

        files = [
            p for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

        if reset:
            for f in files:
                await vector_store.delete_by_doc_id(_doc_id(f))
            logger.info("ingest.reset", files=len(files))

        total_chunks = 0
        errors = 0

        for file_path in files:
            try:
                total_chunks += await self.ingest_file(file_path)
            except Exception as exc:
                logger.error("ingest.file.error", file=str(file_path), error=str(exc), exc_info=True)
                errors += 1

        summary = {
            "files_processed": len(files),
            "chunks_stored": total_chunks,
            "errors": errors,
            "total_docs_in_store": await vector_store.count(),
        }
        logger.info("ingest.directory.done", **summary)
        return summary


# ── CLI entry point ───────────────────────────────────────────────────────────

async def _main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into the AutoMark AI knowledge base.")
    parser.add_argument("--source", type=str, default=settings.KNOWLEDGE_BASE_PATH)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    ingester = DocumentIngester()
    source = Path(args.source)

    if source.is_file():
        chunks = await ingester.ingest_file(source)
        print(f"Ingested {chunks} chunks from {source}")
    elif source.is_dir():
        result = await ingester.ingest_directory(source, reset=args.reset)
        print(f"Ingestion complete: {result}")
    else:
        print(f"Path not found: {source}")


if __name__ == "__main__":
    asyncio.run(_main())