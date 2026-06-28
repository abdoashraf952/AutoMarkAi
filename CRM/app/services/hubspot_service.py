"""
app/services/hubspot_service.py — AutoMark AI CRM Agent (ORCAST)

HubSpot CRM REST API v3 client (Private App Access Token), async via httpx
with tenacity retries on transient failures.

Supported operations:
    create_contact, update_contact, search_contact, get_contact,
    find_or_create_contact, create_deal, update_deal, create_note
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog
from tenacity import retry, retry_if_exception, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import settings

logger = structlog.get_logger(__name__)

CONTACTS_URL = f"{settings.HUBSPOT_BASE_URL}/crm/v3/objects/contacts"
CONTACTS_SEARCH_URL = f"{CONTACTS_URL}/search"
DEALS_URL = f"{settings.HUBSPOT_BASE_URL}/crm/v3/objects/deals"
NOTES_URL = f"{settings.HUBSPOT_BASE_URL}/crm/v3/objects/notes"

CONTACT_PROPERTIES = "email,firstname,lastname,phone,company,hs_lead_status,lifecyclestage"

def _is_retryable_http(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {429, 500, 502, 503, 504}


_RETRYABLE = retry_if_exception_type(httpx.TransportError) | retry_if_exception(_is_retryable_http)


def _retryable_request():
    return retry(
        retry=_RETRYABLE,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )


class HubSpotService:

    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.HUBSPOT_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    # ── Low-level HTTP helper ────────────────────────────────────────────────

    @_retryable_request()
    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(method, url, headers=self._headers, **kwargs)
            if resp.status_code == 403:
                raise httpx.HTTPStatusError(
                    f"HubSpot 403 — token missing required scopes. "
                    f"Go to HubSpot → Settings → Integrations → Private Apps → your app → Scopes "
                    f"and enable: crm.objects.contacts.read, crm.objects.contacts.write, "
                    f"crm.objects.deals.read, crm.objects.deals.write, crm.objects.notes.write",
                    request=resp.request,
                    response=resp,
                )
            resp.raise_for_status()
            return resp

    def _hs_error(self, operation: str, exc: Exception) -> dict:
        msg = str(exc)[:300]
        if "403" in msg or "missing required scopes" in msg:
            logger.warning(
                "hubspot_service.permission_error",
                operation=operation,
                fix="HubSpot Private App → Scopes: enable crm.objects.contacts.read/write, "
                    "crm.objects.deals.read/write, crm.objects.notes.write",
            )
        else:
            logger.error("hubspot_service.error", operation=operation, error=msg)
        return {"success": False, "error": msg, "operation": operation}

    # ── Contact operations ───────────────────────────────────────────────────

    async def create_contact(self, data: dict) -> dict:
        """data keys: email, firstname, lastname, phone, company,
        hs_lead_status, lifecyclestage, notes"""
        try:
            properties = self._build_contact_properties(data)
            resp = await self._request("POST", CONTACTS_URL, json={"properties": properties})
            result = resp.json()
            contact_id = result.get("id")
            logger.info("hubspot_service.contact_created", contact_id=contact_id)

            if data.get("notes") and contact_id:
                await self.create_note(contact_id, "CONTACT", data["notes"])

            return {
                "success": True,
                "operation": "create_contact",
                "contact_id": contact_id,
                "properties": result.get("properties", {}),
            }
        except Exception as exc:
            return self._hs_error("create_contact", exc)

    async def update_contact(self, data: dict) -> dict:
        """data keys: contact_id (or email to look up) + property fields"""
        try:
            contact_id = data.get("contact_id")
            if not contact_id and data.get("email"):
                search_result = await self.search_contact({"email": data["email"]})
                if search_result.get("contact_id"):
                    contact_id = search_result["contact_id"]

            if not contact_id:
                return {"success": False, "error": "contact_id required for update"}

            properties = self._build_contact_properties(data)
            await self._request("PATCH", f"{CONTACTS_URL}/{contact_id}", json={"properties": properties})
            logger.info("hubspot_service.contact_updated", contact_id=contact_id)
            return {"success": True, "operation": "update_contact", "contact_id": contact_id}
        except Exception as exc:
            return self._hs_error("update_contact", exc)

    async def search_contact(self, data: dict) -> dict:
        """data keys: email | phone"""
        try:
            filters = []
            if data.get("email"):
                filters.append({"propertyName": "email", "operator": "EQ", "value": data["email"]})
            elif data.get("phone"):
                filters.append({"propertyName": "phone", "operator": "EQ", "value": data["phone"]})

            if not filters:
                return {"success": False, "error": "email or phone required for search"}

            payload = {
                "filterGroups": [{"filters": filters}],
                "properties": CONTACT_PROPERTIES.split(","),
                "limit": 1,
            }
            resp = await self._request("POST", CONTACTS_SEARCH_URL, json=payload)
            results = resp.json().get("results", [])

            if not results:
                return {"success": True, "found": False, "contact_id": None}

            contact = results[0]
            return {
                "success": True,
                "found": True,
                "contact_id": contact.get("id"),
                "properties": contact.get("properties", {}),
            }
        except Exception as exc:
            return self._hs_error("search_contact", exc)

    async def get_contact(self, data: dict) -> dict:
        """data keys: contact_id"""
        try:
            contact_id = data.get("contact_id")
            if not contact_id:
                return {"success": False, "error": "contact_id required"}
            resp = await self._request(
                "GET", f"{CONTACTS_URL}/{contact_id}", params={"properties": CONTACT_PROPERTIES}
            )
            result = resp.json()
            return {"success": True, "contact_id": result.get("id"), "properties": result.get("properties", {})}
        except Exception as exc:
            return self._hs_error("get_contact", exc)

    async def find_or_create_contact(self, data: dict) -> dict:
        """Dedupe by email (preferred) or phone, creating a new contact only
        if no match is found. Falls through to create if search is unavailable."""
        lookup: dict = {}
        if data.get("email"):
            lookup["email"] = data["email"]
        elif data.get("phone"):
            lookup["phone"] = data["phone"]

        if lookup:
            try:
                search_result = await self.search_contact(lookup)
                if search_result.get("found") and search_result.get("contact_id"):
                    contact_id = search_result["contact_id"]
                    update_data = {**data, "contact_id": contact_id}
                    await self.update_contact(update_data)
                    return {
                        "success": True,
                        "operation": "find_or_create_contact",
                        "contact_id": contact_id,
                        "created": False,
                    }
            except Exception as exc:
                logger.warning("hubspot_service.search_skipped", reason=str(exc)[:120])

        result = await self.create_contact(data)
        result["operation"] = "find_or_create_contact"
        result["created"] = True
        return result

    # ── Deal operations ──────────────────────────────────────────────────────

    async def create_deal(self, data: dict) -> dict:
        """data keys: dealname, contact_id (optional), amount (optional),
        dealstage, pipeline, description"""
        properties: dict[str, Any] = {
            "dealname": data.get("dealname", "New Deal"),
            "dealstage": data.get("dealstage", "appointmentscheduled"),
            "pipeline": data.get("pipeline", "default"),
        }
        if data.get("amount"):
            properties["amount"] = str(data["amount"])
        if data.get("description"):
            properties["description"] = data["description"]

        payload: dict[str, Any] = {"properties": properties}

        contact_id = data.get("contact_id")
        if contact_id:
            payload["associations"] = [
                {
                    "to": {"id": contact_id},
                    "types": [
                        {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}
                    ],
                }
            ]

        resp = await self._request("POST", DEALS_URL, json=payload)
        result = resp.json()
        deal_id = result.get("id")
        logger.info("hubspot_service.deal_created", deal_id=deal_id, contact_id=contact_id)
        return {
            "success": True,
            "operation": "create_deal",
            "deal_id": deal_id,
            "contact_id": contact_id,
        }

    async def update_deal(self, data: dict) -> dict:
        """data keys: deal_id (required), dealstage (optional), amount (optional)"""
        deal_id = data.get("deal_id")
        if not deal_id:
            return {"success": False, "error": "deal_id required for update"}

        properties: dict[str, Any] = {}
        if data.get("dealstage"):
            properties["dealstage"] = data["dealstage"]
        if data.get("amount"):
            properties["amount"] = str(data["amount"])

        await self._request("PATCH", f"{DEALS_URL}/{deal_id}", json={"properties": properties})
        logger.info("hubspot_service.deal_updated", deal_id=deal_id)
        return {"success": True, "operation": "update_deal", "deal_id": deal_id}

    # ── Notes / Engagements ──────────────────────────────────────────────────

    async def create_note(self, object_id: str, object_type: str, body: str) -> Optional[str]:
        """Create a note engagement associated with a contact ("CONTACT") or
        deal ("DEAL"). Returns the note ID, or None on failure."""
        association_type_id = 202 if object_type == "CONTACT" else 214
        ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        payload = {
            "properties": {"hs_timestamp": ts, "hs_note_body": body},
            "associations": [
                {
                    "to": {"id": object_id},
                    "types": [
                        {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": association_type_id}
                    ],
                }
            ],
        }
        try:
            resp = await self._request("POST", NOTES_URL, json=payload)
            note_id = resp.json().get("id")
            logger.debug("hubspot_service.note_created", object_id=object_id, note_id=note_id)
            return note_id
        except Exception as exc:
            logger.warning("hubspot_service.note_error", object_id=object_id, error=str(exc))
            return None

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_contact_properties(data: dict) -> dict:
        mapping = ("email", "firstname", "lastname", "phone", "company", "hs_lead_status", "lifecyclestage")
        return {key: str(data[key]) for key in mapping if data.get(key)}


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

hubspot_service = HubSpotService()