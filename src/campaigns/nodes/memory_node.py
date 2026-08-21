"""Memory node — Phase 5 graph integration.

summarizer_node runs once after discovery (interview done) and generates
a rolling_summary of the session so far. It:
  1. Recalls existing client memory (if client_memory_ref is set).
  2. Calls the cheap-model summarizer.
  3. Stores rolling_summary in state (picked up by orchestrator prompt injection).

This node never interrupts — it runs transparently between discovery and
the research squad, adding 1–2 seconds LLM latency with a cheap model.
"""

import logging

from src.campaigns.memory.client_store import build_context_snippet, recall
from src.campaigns.memory.summarizer import make_rolling_summary

logger = logging.getLogger(__name__)


def summarizer_node(state: dict) -> dict:
    """
    Generate rolling_summary and inject client long-term memory context.

    State reads:  real_estate_data, campaign_plan, decisions_log,
                  client_memory_ref, language
    State writes: rolling_summary, client_memory_ref (if derived here)
    """
    # Derive client_memory_ref from compound name if not already set
    client_ref = state.get("client_memory_ref") or ""
    if not client_ref:
        re_data = state.get("real_estate_data") or {}
        compound = re_data.get("compound_name", "")
        if compound:
            client_ref = compound.strip()

    # Recall long-term memory (empty dict for new clients — no-op)
    client_memory = recall(client_ref) if client_ref else {}

    # Build a short context snippet for the orchestrator prompt
    language = state.get("language", "en")
    memory_snippet = build_context_snippet(client_memory, language)
    if memory_snippet:
        logger.info("summarizer_node: injecting client memory for '%s'", client_ref)

    # Generate rolling summary (cheap LLM, non-blocking on failure)
    existing_summary = state.get("rolling_summary", "")
    new_summary = make_rolling_summary(state)
    # Append to existing summary (keeps grow-then-fold pattern safe)
    rolling_summary = (
        f"{existing_summary}\n\n---\n\n{new_summary}" if existing_summary else new_summary
    )

    result = {
        "rolling_summary": rolling_summary,
        "errors": [],
    }
    if client_ref:
        result["client_memory_ref"] = client_ref

    return result
