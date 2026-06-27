"""Supervisor — central routing and campaign phase management (Phase 0).

Centralises the routing functions that were previously inline in
pipeline_graph.py.  In later phases this is where squad gating,
guardrail enforcement, and the operate-loop decision log live.

The supervisor is a *router*, not a worker: it never calls an LLM or
touches an external API — it reads the shared campaign state and returns
the name of the next node to run.
"""

import logging

from langgraph.types import Send

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Campaign-phase constants (Phase 0: only discovery + build used)     #
# ------------------------------------------------------------------ #
PHASE_DISCOVERY = "discovery"
PHASE_BUILD = "build"
PHASE_OPERATE = "operate"   # Phase 4+


# ------------------------------------------------------------------ #
# Build-path routing (extracted from pipeline_graph.py)              #
# ------------------------------------------------------------------ #

def route_after_orchestrator(state: dict) -> str:
    """After orchestrator: run strategy if we have a plan, else short-circuit."""
    if not state.get("campaign_plan"):
        return "merge_node"
    return "strategy_node"


def route_to_subagents(state: dict):
    """Fan-out to creative and media-buying after the Strategist."""
    if not state.get("campaign_plan"):
        return "merge_node"
    return [
        Send("creative_node", dict(state)),
        Send("media_buying_node", dict(state)),
    ]


def route_after_text_review(state: dict) -> str:
    """Loop back to creative_node if copy was rejected; else proceed to merge."""
    if state.get("review_stage") == "redo_creative":
        return "creative_node"
    return "merge_node"


# ------------------------------------------------------------------ #
# Top-level supervisor router (Phase 0: thin wrapper)                #
# ------------------------------------------------------------------ #

def supervisor_route(state: dict) -> str:
    """
    Central routing function.

    Phase 0: mirrors the existing linear topology — acts as a
    deterministic dispatcher based on campaign_phase so the graph has
    one well-known entry point for phase transitions.

    Phase 2+: will gate squads through compliance guardrails, manage
    the operate-loop cadences, and write to the decision log before
    any Meta write.
    """
    phase = state.get("campaign_phase", PHASE_DISCOVERY)
    logger.debug("supervisor_route: campaign_phase=%s", phase)

    if phase == PHASE_DISCOVERY:
        # Handoff to the build path once questions are done is handled
        # by route_after_gen inside the discovery sub-loop.
        return "target_gen_node"

    if phase == PHASE_BUILD:
        # Post-interview: go straight to orchestrator.
        return "orchestrator_node"

    # PHASE_OPERATE and future phases handled here in Phase 4+.
    logger.warning("supervisor_route: unhandled phase '%s', falling back to merge", phase)
    return "merge_node"
