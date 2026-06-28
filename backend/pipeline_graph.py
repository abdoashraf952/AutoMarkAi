"""Full campaign pipeline graph — real estate interview, research, review, compliance.

Phase 0  — supervisor routing functions extracted to nodes/supervisor.py.
Phase 2  — compliance_node added after merge (mandatory HOUSING gate).
Phase 3  — research squad (audience, competitor, trend) inserted between
            discovery and orchestrator.
Phase 4  — operate lifecycle nodes (diagnose, decision, act) reachable when
            campaign_phase == "operate".
Phase 5  — summarizer_node added after discovery to build rolling_summary.
"""

import logging
import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

_logger = logging.getLogger(__name__)


def _build_checkpointer():
    """
    Return the best available checkpointer:
      1. PostgresSaver  if POSTGRES_URL is set and langgraph-checkpoint-postgres installed
      2. SqliteSaver    as a file-based persistent fallback
      3. MemorySaver    in-memory (lost on restart)
    """
    pg_url = os.getenv("POSTGRES_URL", "")
    if pg_url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            saver = PostgresSaver.from_conn_string(pg_url)
            saver.setup()  # create tables if they don't exist
            _logger.info("Checkpointer: PostgresSaver (POSTGRES_URL set)")
            return saver
        except Exception as e:
            _logger.warning("PostgresSaver failed (%s) — falling back to SqliteSaver", e)

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        db_path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".automark_checkpoints.sqlite"
        )
        saver = SqliteSaver.from_conn_string(db_path)
        _logger.info("Checkpointer: SqliteSaver → %s", db_path)
        return saver
    except Exception as e:
        _logger.warning("SqliteSaver failed (%s) — falling back to MemorySaver", e)

    _logger.info("Checkpointer: MemorySaver (in-memory, lost on restart)")
    return MemorySaver()

from AutoMarkAi.backend.nodes.compliance import compliance_node
from AutoMarkAi.backend.nodes.creative import creative_node
from AutoMarkAi.backend.nodes.lifecycle import (
    act_node,
    decision_node,
    diagnose_node,
)
from AutoMarkAi.backend.nodes.media_buying import media_buying_node
from AutoMarkAi.backend.nodes.memory_node import summarizer_node
from AutoMarkAi.backend.nodes.merge import merge_node
from AutoMarkAi.backend.nodes.orchestrator import orchestrator_node
from AutoMarkAi.backend.nodes.question_generator import (
    question_ask_node,
    question_gen_node,
    route_after_gen,
    target_ask_node,
    target_gen_node,
)
from AutoMarkAi.backend.nodes.research import (
    audience_node,
    competitor_node,
    trend_node,
)
from AutoMarkAi.backend.nodes.review import (
    photo_select_node,
    text_review_node,
)
from AutoMarkAi.backend.nodes.strategy import strategy_node
from AutoMarkAi.backend.nodes.supervisor import (
    route_after_orchestrator,
    route_after_text_review,
    route_to_subagents,
    route_operate,
)
from AutoMarkAi.backend.state import CampaignState


def get_pipeline_graph():
    """
    Build and compile the full pipeline graph with a MemorySaver checkpointer.

    Topology:
        START
          → target_gen_node          [rank campaign targets]
          → target_ask_node          [interrupt: campaign_target  (skipped in guided/autopilot)]
          → question_gen_node        [fixed question / follow-up / done]
               → question_ask_node  [interrupt: questions] → loop → question_gen_node
               → summarizer_node    [Phase 5: rolling summary, no interrupt]
          → audience_node            [Phase 3: HOUSING-compliant audience plan]
          → competitor_node          [Phase 3: competitor findings (simulated)]
          → trend_node               [Phase 3: seasonal demand windows]
          → orchestrator_node        [vision + interview → campaign_plan]
          → strategy_node            [persona + channels + scheduling]
          → fan-out:
               creative_node        → photo_select_node [interrupt, skip autopilot]
                                    → text_review_node  [interrupt, skip autopilot]
               media_buying_node
          → merge_node               [assemble campaign_bundle]
          → compliance_node          [Phase 2: HOUSING gate — mandatory]
          → END

        Operate path (campaign_phase == "operate"):
          START → diagnose_node → decision_node → act_node → END
    """
    builder = StateGraph(CampaignState)

    # ── Discovery squad ────────────────────────────────────────────────
    builder.add_node("target_gen_node", target_gen_node)
    builder.add_node("target_ask_node", target_ask_node)
    builder.add_node("question_gen_node", question_gen_node)
    builder.add_node("question_ask_node", question_ask_node)
    builder.add_node("summarizer_node", summarizer_node)        # Phase 5

    # ── Research squad (Phase 3) ───────────────────────────────────────
    builder.add_node("audience_node", audience_node)
    builder.add_node("competitor_node", competitor_node)
    builder.add_node("trend_node", trend_node)

    # ── Plan + Creative + Buying squads ───────────────────────────────
    builder.add_node("orchestrator_node", orchestrator_node)
    builder.add_node("strategy_node", strategy_node)
    builder.add_node("creative_node", creative_node)
    builder.add_node("media_buying_node", media_buying_node)
    builder.add_node("photo_select_node", photo_select_node)
    builder.add_node("text_review_node", text_review_node)

    # ── Merge + Compliance (Phase 2) ──────────────────────────────────
    builder.add_node("merge_node", merge_node)
    builder.add_node("compliance_node", compliance_node)

    # ── Operate lifecycle (Phase 4) ───────────────────────────────────
    builder.add_node("diagnose_node", diagnose_node)
    builder.add_node("decision_node", decision_node)
    builder.add_node("act_node", act_node)

    # ── Entry: route by campaign_phase ────────────────────────────────
    # Operate re-entries bypass the full build path.
    builder.set_conditional_entry_point(
        route_operate,
        {
            "target_gen_node": "target_gen_node",
            "diagnose_node": "diagnose_node",
        },
    )

    # ── Discovery edges ───────────────────────────────────────────────
    builder.add_edge("target_gen_node", "target_ask_node")
    builder.add_edge("target_ask_node", "question_gen_node")

    # route_after_gen returns "question_ask_node" or "orchestrator_node";
    # we intercept "orchestrator_node" → summarizer first (Phase 5 additive).
    builder.add_conditional_edges(
        "question_gen_node",
        route_after_gen,
        {
            "question_ask_node": "question_ask_node",
            "orchestrator_node": "summarizer_node",   # Phase 5 hook
        },
    )
    builder.add_edge("question_ask_node", "question_gen_node")

    # ── Phase 5 → Phase 3 → Plan ─────────────────────────────────────
    builder.add_edge("summarizer_node", "audience_node")
    builder.add_edge("audience_node", "competitor_node")
    builder.add_edge("competitor_node", "trend_node")
    builder.add_edge("trend_node", "orchestrator_node")

    # ── Plan → Strategy → fan-out ─────────────────────────────────────
    builder.add_conditional_edges(
        "orchestrator_node",
        route_after_orchestrator,
        ["strategy_node", "merge_node"],
    )
    builder.add_conditional_edges(
        "strategy_node",
        route_to_subagents,
        ["creative_node", "media_buying_node", "merge_node"],
    )

    # ── Creative review path ──────────────────────────────────────────
    builder.add_edge("creative_node", "photo_select_node")
    builder.add_edge("photo_select_node", "text_review_node")
    builder.add_conditional_edges(
        "text_review_node",
        route_after_text_review,
        ["creative_node", "merge_node"],
    )
    builder.add_edge("media_buying_node", "merge_node")

    # ── Phase 2: Compliance gate after merge ──────────────────────────
    builder.add_edge("merge_node", "compliance_node")
    builder.add_edge("compliance_node", END)

    # ── Phase 4: Operate lifecycle ────────────────────────────────────
    builder.add_edge("diagnose_node", "decision_node")
    builder.add_conditional_edges(
        "decision_node",
        lambda s: "act_node" if s.get("_operate_action") else END,
        ["act_node", END],
    )
    builder.add_edge("act_node", END)

    return builder.compile(checkpointer=_build_checkpointer())
