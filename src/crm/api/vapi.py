"""
app/api/vapi.py — AutoMark AI CRM Agent (ORCAST)

Vapi Voice AI adapter + webhook router.

Flow:
  1. Customer calls a phone number connected to Vapi.
  2. Vapi transcribes speech and sends a `conversation-update` webhook.
  3. We run the transcript through the ORCAST graph and return
     {"result": "<text>"}.
  4. Vapi converts the text to speech and plays it to the caller.

Text in / text out only — no backend TTS is performed on this path.

Event types handled:
  • assistant-request     — return assistant config
  • conversation-update    — main message hook (synchronous response required)
  • end-of-call-report     — call summary after hang-up
  • function-call          — if Vapi function calling is configured
"""

from __future__ import annotations

import hmac
import json
import structlog
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request

from src.config import settings
from src.crm.graph.orchestrator import run_graph
from src.crm.services.gemini_service import UnifiedMessage

logger = structlog.get_logger(__name__)

router = APIRouter()


class VapiAdapter:

    # ── Signature verification ─────────────────────────────────────────────

    def verify_signature(self, secret_header: str) -> bool:
        """
        Vapi sends the webhook secret as a plain X-Vapi-Secret header.
        Compare it directly against VAPI_WEBHOOK_SECRET using a constant-time
        digest to avoid timing attacks.
        """
        secret = settings.VAPI_WEBHOOK_SECRET
        if not secret:
            logger.warning("vapi.signature_check_skipped")
            return True
        try:
            valid = hmac.compare_digest(secret_header.strip(), secret.strip())
            if not valid:
                logger.warning("vapi.invalid_signature")
            return valid
        except Exception as exc:
            logger.error("vapi.signature_error", error=str(exc))
            return False

    # ── Event routing ────────────────────────────────────────────────────────

    def extract_event(self, payload: dict) -> dict:
        event_type = payload.get("message", {}).get("type", "unknown")
        call = payload.get("message", {}).get("call", {})
        call_id = call.get("id", "")
        customer = call.get("customer", {})
        user_id = customer.get("number", call_id) or call_id

        result = {"type": event_type, "call_id": call_id, "user_id": user_id, "raw": payload}

        if event_type == "conversation-update":
            messages = payload.get("message", {}).get("artifact", {}).get("messages", [])
            user_messages = [m for m in messages if m.get("role") == "user"]
            result["user_text"] = user_messages[-1].get("message", "") if user_messages else ""

        elif event_type == "assistant-request":
            result["phone_number"] = customer.get("number", "")

        elif event_type == "end-of-call-report":
            result["transcript"] = payload.get("message", {}).get("artifact", {}).get("transcript", "")
            result["summary"] = payload.get("message", {}).get("summary", "")
            result["duration_seconds"] = call.get("duration", 0)

        elif event_type == "function-call":
            result["function_name"] = payload.get("message", {}).get("functionCall", {}).get("name", "")
            result["function_params"] = payload.get("message", {}).get("functionCall", {}).get("parameters", {})

        return result

    def normalise_conversation_update(self, event: dict) -> Optional[UnifiedMessage]:
        user_text = event.get("user_text", "").strip()
        if not user_text:
            logger.info("vapi.empty_transcription", call_id=event.get("call_id"))
            return None

        user_id = event.get("user_id", event.get("call_id", "vapi_unknown"))
        call_id = event.get("call_id", "")
        metadata: dict[str, Any] = {"call_id": call_id}

        logger.info("vapi.normalised", call_id=call_id, preview=user_text[:60])

        return UnifiedMessage(
            user_id=user_id,
            source="vapi",
            input_type="text",
            content=user_text,
            metadata=metadata,
        )

    # ── Response formatting ──────────────────────────────────────────────────

    @staticmethod
    def format_response(text: str) -> dict:
        """Wrap the ORCAST graph's text in Vapi's expected response format."""
        return {"result": text}

    @staticmethod
    def format_assistant_config() -> dict:
        return {
            "assistant": {
                "firstMessage": "Hello! This is AutoMark AI. How can I help you today?",
                "model": {"provider": "custom-llm", "url": ""},
                "voice": {"provider": "11labs", "voiceId": "EXAVITQu4vr4xnSDxMaL"},
                "endCallMessage": "Thank you for calling. Have a great day!",
                "recordingEnabled": True,
                "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "en"},
            }
        }

    @staticmethod
    def acknowledge_end_of_call(event: dict) -> dict:
        logger.info("vapi.call_ended", call_id=event.get("call_id"), duration=event.get("duration_seconds"))
        return {"status": "received"}


vapi_adapter = VapiAdapter()


# ─────────────────────────────────────────────────────────────────────────────
# Webhook endpoint (synchronous — Vapi reads the JSON response body directly)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/vapi/webhook")
@router.post("/webhook/vapi")
async def vapi_webhook(request: Request) -> dict:
    raw_bytes = await request.body()
    secret_header = request.headers.get("x-vapi-secret", "")

    if not vapi_adapter.verify_signature(secret_header):
        raise HTTPException(status_code=403, detail="Invalid Vapi signature")

    payload = json.loads(raw_bytes)
    event = vapi_adapter.extract_event(payload)
    event_type = event.get("type")
    logger.info("vapi_webhook.received", event_type=event_type)

    if event_type == "assistant-request":
        return vapi_adapter.format_assistant_config()

    elif event_type == "conversation-update":
        norm = vapi_adapter.normalise_conversation_update(event)
        if not norm:
            return vapi_adapter.format_response("I didn't catch that. Could you repeat?")
        try:
            agent_response = await run_graph(norm)
            return vapi_adapter.format_response(agent_response.message)
        except Exception as exc:
            logger.error("vapi_webhook.error", error=str(exc), exc_info=True)
            return vapi_adapter.format_response(
                "I'm having a technical issue. Please try again in a moment."
            )

    elif event_type == "end-of-call-report":
        return vapi_adapter.acknowledge_end_of_call(event)

    elif event_type == "function-call":
        fn_name = event.get("function_name", "")
        logger.info("vapi.function_call", function=fn_name)
        return {"result": f"Function {fn_name} acknowledged."}

    else:
        logger.info("vapi_webhook.unhandled", event_type=event_type)
        return {"status": "ok"}
