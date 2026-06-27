"""
app/tools/rag_tool.py — AutoMark AI CRM Agent (ORCAST)

`search_knowledge_base` tool: hybrid retrieval → reranking → grounded answer.

Pipeline (LCEL):
    HybridRetriever → GeminiReranker → PromptTemplate | ChatGoogleGenerativeAI | StrOutputParser

The LCEL chain handles the final answer generation. Retrieval and reranking are
done first via the LangChain retriever / compressor interfaces so they can be
swapped independently.
"""

from __future__ import annotations

import structlog
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import traceable

from config import settings
from app.rag.embeddings import gemini_embeddings  # noqa: F401 — keeps import chain warm
from app.rag.retriever import hybrid_retriever
from app.rag.reranker import gemini_reranker

logger = structlog.get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LCEL answer-generation chain
# ─────────────────────────────────────────────────────────────────────────────

_ANSWER_TEMPLATE = """You are answering a customer question on behalf of a company.
Use ONLY the information provided in the context below.
Do NOT add information that is not in the context.
If the context does not contain enough information to answer the question,
respond ONLY with the exact phrase: "INSUFFICIENT_CONTEXT"

## Context:
{context}

## Customer Question:
{question}

## Answer:
"""

_prompt = PromptTemplate(
    input_variables=["context", "question"],
    template=_ANSWER_TEMPLATE,
)

_chain = None  # lazy — built on first call to avoid import-time side effects


def _get_chain():
    global _chain
    if _chain is None:
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0.1,
            google_api_key=settings.GEMINI_API_KEY,
        )
        _chain = _prompt | llm | StrOutputParser()
    return _chain

NO_INFO_RESPONSE = (
    "I don't have verified information on that right now. "
    "I'll make sure a team member follows up with you shortly."
)


# ─────────────────────────────────────────────────────────────────────────────
# Public tool function
# ─────────────────────────────────────────────────────────────────────────────

@traceable(name="search_knowledge_base")
async def search_knowledge_base(query: str) -> dict:
    """
    Retrieve relevant knowledge-base chunks and generate a grounded answer.

    Returns
    -------
    {"found": bool, "answer": str, "sources": list[str], "chunks_used": int}
    """
    log = logger.bind(query_preview=query[:80])
    log.info("rag_tool.run.start")

    if not query.strip():
        return {"found": False, "answer": NO_INFO_RESPONSE, "sources": [], "chunks_used": 0}

    # 1. Retrieve candidate documents via hybrid RRF
    docs = await hybrid_retriever.ainvoke(query)
    if not docs:
        log.info("rag_tool.no_results")
        return {"found": False, "answer": NO_INFO_RESPONSE, "sources": [], "chunks_used": 0}

    # 2. Rerank with Gemini compressor
    reranked = list(await gemini_reranker.acompress_documents(docs, query))

    # 3. Build context string from reranked Documents
    context_parts: list[str] = []
    sources: list[str] = []
    for doc in reranked:
        source_file = doc.metadata.get("source_file", "unknown")
        chunk_idx = doc.metadata.get("chunk_index", "?")
        context_parts.append(f"[Source: {source_file} | Chunk {chunk_idx}]\n{doc.page_content}")
        if source_file not in sources:
            sources.append(source_file)

    context = "\n\n---\n\n".join(context_parts)

    # 4. Generate grounded answer via LCEL chain
    answer = await _get_chain().ainvoke({"context": context, "question": query})

    if not answer or "INSUFFICIENT_CONTEXT" in answer:
        log.info("rag_tool.insufficient_context")
        return {"found": False, "answer": NO_INFO_RESPONSE, "sources": sources, "chunks_used": len(reranked)}

    log.info("rag_tool.run.done", chunks_used=len(reranked), sources=sources)
    return {"found": True, "answer": answer, "sources": sources, "chunks_used": len(reranked)}
