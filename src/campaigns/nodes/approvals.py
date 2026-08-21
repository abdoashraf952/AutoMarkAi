"""Approval Gateway — step-by-step optional approval (Phase 1).

Three modes (set via POST /session/{id}/mode or the /start approval_mode param):

  full_manual  — interrupt at every configured gate (default; reproduces the
                 original three-interrupt behaviour when mode is not specified)
  guided       — creative/plan gates auto-approve; money/launch/schedule gates
                 still interrupt the user
  autopilot    — only money-threshold and new-launch gates interrupt

Usage inside a graph node:

    from src.campaigns.nodes.approvals import request_approval

    result = request_approval(state, {
        "type": "creative",
        "description": "Review the generated ad copy",
        "payload": {"copies": [...], "headlines": [...]},
    })
    # result["decision"] == "approved" | "rejected"

request_approval() must be called from within a LangGraph node because it may
call interrupt() internally.  Keep side-effect-free work *outside* this call
so the checkpoint-safe pattern holds — the node can safely be resumed without
re-running any LLM/API calls before the gate.
"""

import logging

from langgraph.types import interrupt

logger = logging.getLogger(__name__)

# Gate types that are auto-approved in guided mode (not money/launch/schedule).
_GUIDED_AUTO = frozenset({"creative", "plan"})

# Gate types that are auto-approved in autopilot mode.
_AUTOPILOT_AUTO = frozenset({"creative", "plan", "schedule"})


def request_approval(state: dict, item: dict) -> dict:
    """
    Request human approval for an action or artifact.

    Parameters
    ----------
    state : dict
        Current graph state (reads ``approval_mode``).
    item : dict
        Description of what needs approval.  Required keys:
          type        — gate class: "creative" | "plan" | "money" | "launch" | "schedule"
          description — plain-language summary shown to the user
        Optional:
          payload     — the artifact to review (copy dict, plan dict, …)
          stage       — override the interrupt stage name (default "approval")

    Returns
    -------
    dict
        ``{"decision": "approved" | "rejected", "auto": bool, "type": str, …}``
    """
    mode = state.get("approval_mode", "full_manual")
    gate_type = item.get("type", "creative")

    auto_approve = (
        (mode == "guided" and gate_type in _GUIDED_AUTO)
        or (mode == "autopilot" and gate_type in _AUTOPILOT_AUTO)
    )

    if auto_approve:
        logger.info(
            "request_approval: auto-approved gate '%s' (approval_mode=%s)", gate_type, mode
        )
        return {"decision": "approved", "auto": True, "type": gate_type}

    logger.info(
        "request_approval: interrupting for gate '%s' (approval_mode=%s)", gate_type, mode
    )
    stage = item.get("stage", "approval")
    result = interrupt({"stage": stage, **item})
    if not isinstance(result, dict):
        return {"decision": "approved", "auto": False, "type": gate_type}
    return {**result, "auto": False, "type": gate_type}
