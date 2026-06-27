"""
app/api/messenger.py — AutoMark AI CRM Agent (ORCAST)

Facebook Messenger adapter + webhook router.

Inbound text/quick-replies pass straight through. Audio attachments are
transcribed and image attachments described via gemini_service, so the
ORCAST graph only ever sees plain text. Outbound replies are sent via
send_message; send_voice_reply (Messenger-only) is used by
app.tools.messaging_tool to deliver synthesized speech for voice-in turns.
"""

from __future__ import annotations

import json
import structlog
from typing import Any, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response

from config import settings
from app.graph.orchestrator import run_graph
from app.services.gemini_service import UnifiedMessage, gemini_service

logger = structlog.get_logger(__name__)

router = APIRouter()

GRAPH_BASE = "https://graph.facebook.com/v19.0"
SEND_API_URL = f"{GRAPH_BASE}/me/messages"

def _messenger_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.MESSENGER_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


class MessengerAdapter:

    # ── Inbound ──────────────────────────────────────────────────────────

    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        valid = {settings.MESSENGER_VERIFY_TOKEN, settings.FB_COMMENTS_VERIFY_TOKEN} - {""}
        if mode == "subscribe" and token in valid:
            logger.info("messenger.webhook_verified", app="messenger" if token == settings.MESSENGER_VERIFY_TOKEN else "fb_comments")
            return challenge
        logger.warning("messenger.webhook_verify_failed")
        return None

    def extract_messages(self, payload: dict) -> list[dict]:
        events = []
        for entry in payload.get("entry", []):
            for messaging in entry.get("messaging", []):
                events.append(messaging)
        return events

    async def normalise(self, raw_event: dict) -> Optional[UnifiedMessage]:
        sender = raw_event.get("sender", {})
        user_id = sender.get("id", "")
        message = raw_event.get("message", {})

        if not message:
            return None

        metadata: dict[str, Any] = {
            "platform_message_id": message.get("mid", ""),
            "page_id": raw_event.get("recipient", {}).get("id", ""),
        }

        content = ""
        input_type = "unknown"

        if message.get("quick_reply"):
            content = message["quick_reply"].get("payload", "")
            input_type = "text"

        elif message.get("text"):
            content = message["text"]
            input_type = "text"

        elif message.get("attachments"):
            attachment = message["attachments"][0]
            att_type = attachment.get("type", "unknown")
            att_url = attachment.get("payload", {}).get("url", "")

            if att_type == "audio" and att_url:
                audio_bytes, mime_type = await self._download(att_url)
                content = await gemini_service.transcribe_audio(audio_bytes, mime_type) if audio_bytes else ""
                content = content or "[Voice message — transcription unavailable]"
                input_type = "voice"

            elif att_type == "image" and att_url:
                image_bytes, mime_type = await self._download(att_url)
                content = await gemini_service.describe_image(image_bytes, mime_type) if image_bytes else ""
                content = content or "[Image received]"
                input_type = "image"

            elif att_type == "file":
                content = f"[File received: {att_url}]"
                input_type = "document"

            else:
                content = f"[{att_type} attachment received]"
                input_type = "unknown"

        if not content.strip():
            return None

        return UnifiedMessage(
            user_id=user_id,
            source="messenger",
            input_type=input_type,
            content=content.strip(),
            metadata=metadata,
        )

    async def _download(self, url: str) -> tuple[bytes, str]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {settings.MESSENGER_ACCESS_TOKEN}"})
                resp.raise_for_status()
                mime_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
                return resp.content, mime_type
        except Exception as exc:
            logger.error("messenger.download_error", error=str(exc))
            return b"", ""

    # ── Outbound ─────────────────────────────────────────────────────────

    async def send_message(self, recipient_id: str, text: str) -> dict:
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text[:2000]},
            "messaging_type": "RESPONSE",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(SEND_API_URL, json=payload, headers=_messenger_headers())
                resp.raise_for_status()
            body = resp.json()
            logger.info("messenger.message_sent", recipient=recipient_id)
            return {"success": True, "message_id": body.get("message_id")}
        except httpx.HTTPStatusError as exc:
            logger.error("messenger.send_error", status=exc.response.status_code, body=exc.response.text[:500])
            return {"success": False, "error": exc.response.text[:200]}
        except Exception as exc:
            logger.error("messenger.send_error", error=str(exc))
            return {"success": False, "error": str(exc)}

    async def send_voice_reply(self, recipient_id: str, audio_bytes: bytes, mime_type: str = "audio/mpeg") -> dict:
        """Send a voice reply as a Messenger audio attachment (binary upload)."""
        data = {
            "recipient": json.dumps({"id": recipient_id}),
            "message": json.dumps({"attachment": {"type": "audio", "payload": {"is_reusable": False}}}),
        }
        files = {"filedata": ("voice_reply.mp3", audio_bytes, mime_type)}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    SEND_API_URL,
                    data=data,
                    files=files,
                    headers={"Authorization": f"Bearer {settings.MESSENGER_ACCESS_TOKEN}"},
                )
                resp.raise_for_status()
            body = resp.json()
            logger.info("messenger.voice_reply_sent", recipient=recipient_id)
            return {"success": True, "message_id": body.get("message_id")}
        except httpx.HTTPStatusError as exc:
            logger.error("messenger.voice_reply_error", status=exc.response.status_code)
            return {"success": False, "error": exc.response.text[:200]}
        except Exception as exc:
            logger.error("messenger.voice_reply_error", error=str(exc))
            return {"success": False, "error": str(exc)}

    async def send_message_to_commenter(self, comment_id: str, text: str) -> dict:
        """
        Send a private Messenger DM to someone who commented on a Page post.
        Meta allows using {"comment_id": ...} as the recipient, which opens a
        private thread in the commenter's Messenger inbox.
        Requires pages_messaging permission on the Page access token.
        """
        payload = {
            "recipient": {"comment_id": comment_id},
            "message": {"text": text[:2000]},
            "messaging_type": "RESPONSE",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(SEND_API_URL, json=payload, headers=_messenger_headers())
                resp.raise_for_status()
            body = resp.json()
            logger.info("messenger.commenter_dm_sent", comment_id=comment_id)
            return {"success": True, "message_id": body.get("message_id")}
        except httpx.HTTPStatusError as exc:
            logger.error("messenger.commenter_dm_error", status=exc.response.status_code, body=exc.response.text[:300])
            return {"success": False, "error": exc.response.text[:200]}
        except Exception as exc:
            logger.error("messenger.commenter_dm_error", error=str(exc))
            return {"success": False, "error": str(exc)}

    async def send_typing_indicator(self, recipient_id: str) -> None:
        payload = {"recipient": {"id": recipient_id}, "sender_action": "typing_on"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(SEND_API_URL, json=payload, headers=_messenger_headers())
        except Exception:
            pass


messenger_adapter = MessengerAdapter()


# ─────────────────────────────────────────────────────────────────────────────
# Background processing
# ─────────────────────────────────────────────────────────────────────────────

async def _process_and_respond(message: UnifiedMessage) -> None:
    """Run the ORCAST graph. Delivery happens inside the graph's
    messaging_node, which calls app.tools.messaging_tool.send_reply."""
    log = logger.bind(user_id=message.user_id, source=message.source)
    try:
        await run_graph(message)
    except Exception as exc:
        log.error("messenger.process_error", error=str(exc), exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# Webhook endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/messenger/webhook")
async def messenger_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> Response:
    """Meta webhook verification handshake."""
    challenge = messenger_adapter.verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    if challenge is None:
        raise HTTPException(status_code=403, detail="Verification failed")
    return Response(content=challenge, media_type="text/plain")


@router.post("/messenger/webhook")
async def messenger_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    """
    Unified webhook for Messenger DMs and Page comment events.

    Meta sends both through the same app subscription, so we detect the
    event type from the payload structure and route accordingly:
      entry[*].messaging  → Messenger direct messages
      entry[*].changes    → Page feed events (comments)
    """
    from app.api.facebook_comments import facebook_comments_adapter, _process_and_respond as _fc_process

    payload = await request.json()

    for entry in payload.get("entry", []):
        # ── Messenger direct messages ────────────────────────────────────────
        for messaging in entry.get("messaging", []):
            try:
                sender_id = messaging.get("sender", {}).get("id", "")
                if sender_id:
                    background_tasks.add_task(messenger_adapter.send_typing_indicator, sender_id)
                norm = await messenger_adapter.normalise(messaging)
                if norm:
                    background_tasks.add_task(_process_and_respond, norm)
            except Exception as exc:
                logger.error("messenger_webhook.messaging_error", error=str(exc))

        # ── Page feed / comments ─────────────────────────────────────────────
        for change in entry.get("changes", []):
            try:
                value = change.get("value", {})
                if change.get("field") == "feed" and value.get("item") == "comment" and value.get("verb") == "add":
                    page_id = str(entry.get("id", ""))
                    sender_id = str(value.get("from", {}).get("id", ""))
                    if page_id and sender_id == page_id:
                        continue  # ignore the page's own comments
                    norm = facebook_comments_adapter.normalise(value)
                    if norm:
                        background_tasks.add_task(_fc_process, norm)
            except Exception as exc:
                logger.error("messenger_webhook.comment_error", error=str(exc))

    return {"status": "ok"}
