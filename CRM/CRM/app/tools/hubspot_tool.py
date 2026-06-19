"""
app/tools/hubspot_tool.py — AutoMark AI CRM Agent (ORCAST)

Thin dispatcher over app.services.hubspot_service for the `crm_operation`
tool exposed to the ORCAST agent. create_contact dedupes by email/phone via
find_or_create_contact.
"""

from __future__ import annotations

from typing import Any

import structlog
from langsmith import traceable

from app.services.hubspot_service import hubspot_service

logger = structlog.get_logger(__name__)


@traceable(name="crm_operation")
async def crm_operation(operation: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    Perform a CRM operation on HubSpot.

    operation : create_contact | update_contact | search_contact |
                get_contact | create_deal | update_deal
    data      : operation-specific payload
    """
    log = logger.bind(operation=operation)
    log.info("hubspot_tool.run")

    try:
        if operation == "create_contact":
            return await hubspot_service.find_or_create_contact(data)
        elif operation == "update_contact":
            return await hubspot_service.update_contact(data)
        elif operation == "search_contact":
            return await hubspot_service.search_contact(data)
        elif operation == "get_contact":
            return await hubspot_service.get_contact(data)
        elif operation == "create_deal":
            return await hubspot_service.create_deal(data)
        elif operation == "update_deal":
            return await hubspot_service.update_deal(data)
        else:
            logger.warning("hubspot_tool.unknown_operation", operation=operation)
            return {"success": False, "error": f"Unknown operation: {operation}"}
    except Exception as exc:
        log.error("hubspot_tool.error", error=str(exc), exc_info=True)
        return {"success": False, "error": str(exc)}
