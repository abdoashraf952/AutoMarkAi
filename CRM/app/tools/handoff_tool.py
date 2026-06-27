"""
app/tools/handoff_tool.py — AutoMark AI CRM Agent (ORCAST)

`escalate_to_human` tool: escalates a conversation to a human agent.

Actions performed:
    1. Create a HubSpot note on the contact with the escalation reason
       (if a hubspot_contact_id is known).
    2. If the lead is "qualified" and has a deal, advance the deal stage.
    3. Persist the escalation record via app.memory.postgres_memory
       (also marks the conversation status as "escalated").
"""

from __future__ import annotations

from typing import Any, Optional

import structlog
from langsmith import traceable

from app.memory.postgres_memory import postgres_memory
from app.services.email_service import send_handoff_email
from app.services.hubspot_service import hubspot_service

logger = structlog.get_logger(__name__)

QUALIFIED_DEAL_STAGE = "qualifiedtobuy"


@traceable(name="escalate_to_human")
async def escalate_to_human(
    user_id: str,
    reason: str,
    priority: str = "medium",
    lead: Optional[dict[str, Any]] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Escalate the conversation to a human agent.

    Parameters
    ----------
    user_id  : conversation user identifier
    reason   : plain-text escalation reason (for the human agent)
    priority : low | medium | high | urgent
    lead     : current lead profile from memory (for context)
    notes    : optional additional notes
    """
    log = logger.bind(user_id=user_id, priority=priority)
    log.info("handoff_tool.escalating", reason=reason)

    lead = lead or {}
    note_id: Optional[str] = None

    if lead.get("hubspot_contact_id"):
        note_id = await hubspot_service.create_note(
            lead["hubspot_contact_id"], "CONTACT", _build_note_body(user_id, reason, priority, notes, lead)
        )

    if lead.get("lead_temperature") == "qualified" and lead.get("hubspot_deal_id"):
        await hubspot_service.update_deal(
            {"deal_id": lead["hubspot_deal_id"], "dealstage": QUALIFIED_DEAL_STAGE}
        )

    escalation_id = await postgres_memory.create_escalation(
        user_id=user_id, reason=reason, priority=priority, hubspot_note_id=note_id
    )

    await send_handoff_email(
        user_id=user_id,
        reason=reason,
        priority=priority,
        lead=lead,
        escalation_id=escalation_id,
        notes=notes,
    )

    log.info("handoff_tool.escalated", escalation_id=escalation_id, note_id=note_id)
    return {
        "escalated": True,
        "priority": priority,
        "reason": reason,
        "escalation_id": escalation_id,
        "hubspot_note_id": note_id,
        "message": (
            "Your conversation has been escalated to our team. "
            "A representative will contact you shortly."
        ),
    }


def _build_note_body(
    user_id: str,
    reason: str,
    priority: str,
    notes: Optional[str],
    lead: dict[str, Any],
) -> str:
    lines = [
        "HUMAN HANDOFF REQUEST",
        f"Priority: {priority.upper()}",
        f"User ID: {user_id}",
        f"Reason: {reason}",
    ]
    if notes:
        lines.append(f"Additional Notes: {notes}")
    if lead.get("lead_score") is not None:
        lines.append(f"Lead Score: {lead['lead_score']}/100 ({lead.get('lead_temperature')})")
    if lead.get("name"):
        lines.append(f"Name: {lead['name']}")
    if lead.get("email"):
        lines.append(f"Email: {lead['email']}")
    return "\n".join(lines)
