"""
app/api/facebook_comments.py — AutoMark AI CRM Agent (ORCAST)

Facebook Page Comments adapter + webhook router.

Receives new top-level comments via Meta Webhooks, normalises them, and
posts AI-generated replies back to the comment thread. Ignores the page's
own comments to avoid reply loops.
"""

from __future__ import annotations

import structlog
from typing import Any, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response

from config import settings
from app.graph.orchestrator import run_graph
from app.services.gemini_service import UnifiedMessage

logger = structlog.get_logger(__name__)

router = APIRouter()

GRAPH_BASE = "https://graph.facebook.com/v19.0"
FB_HEADERS = {
    "Authorization": f"Bearer {settings.FB_COMMENTS_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


class FacebookCommentsAdapter:

    # ── Inbound ──────────────────────────────────────────────────────────

    def extract_comment_events(self, payload: dict) -> list[dict]:
        """
        Extract new top-level comment events from a Facebook webhook payload.
        Filters: field=feed, item=comment, verb=add.
        Ignores the page's own comments (sender_id == page_id).
        """
        entries = payload.get("entry", [])
        page_id = str(entries[0].get("id", "")) if entries else ""

        events = []
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if (
                    change.get("field") == "feed"
                    and value.get("item") == "comment"
                    and value.get("verb") == "add"
                ):
                    sender_id = str(value.get("from", {}).get("id", ""))
                    if page_id and sender_id == page_id:
                        logger.debug("fb_comments.ignored_own_comment")
                        continue
                    events.append(value)
        return events

    def normalise(self, event: dict) -> Optional[UnifiedMessage]:
        comment_text = event.get("message", "").strip()
        if not comment_text:
            return None

        user_id = event.get("from", {}).get("id", "")
        user_name = event.get("from", {}).get("name", "")
        comment_id = event.get("comment_id", event.get("id", ""))
        post_id = event.get("post_id", "")

        metadata: dict[str, Any] = {
            "comment_id": comment_id,
            "post_id": post_id,
            "user_name": user_name,
        }

        logger.info("fb_comments.normalised", user_id=user_id, comment_id=comment_id)

        return UnifiedMessage(
            user_id=user_id,
            source="facebook_comments",
            input_type="text",
            content=comment_text,
            metadata=metadata,
        )

    # ── Outbound ─────────────────────────────────────────────────────────

    async def reply_to_comment(self, comment_id: str, text: str) -> dict:
        """Post a reply to a specific Facebook comment."""
        url = f"{GRAPH_BASE}/{comment_id}/comments"
        payload = {"message": text[:8000]}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=FB_HEADERS)
                resp.raise_for_status()
            body = resp.json()
            reply_id = body.get("id", "")
            logger.info("fb_comments.reply_sent", comment_id=comment_id, reply_id=reply_id)
            return {"success": True, "reply_id": reply_id}
        except httpx.HTTPStatusError as exc:
            logger.error("fb_comments.reply_error", status=exc.response.status_code)
            return {"success": False, "error": exc.response.text[:200]}
        except Exception as exc:
            logger.error("fb_comments.reply_error", error=str(exc))
            return {"success": False, "error": str(exc)}


facebook_comments_adapter = FacebookCommentsAdapter()


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
        log.error("fb_comments.process_error", error=str(exc), exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# Webhook endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/facebook/webhook")
async def fb_comments_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> Response:
    if hub_mode == "subscribe" and hub_verify_token == settings.FB_COMMENTS_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/facebook/webhook")
async def fb_comments_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    """
    Receive Facebook Page comment events. Replies are posted directly to the
    comment thread via app.tools.messaging_tool.send_reply.
    """
    payload = await request.json()
    events = facebook_comments_adapter.extract_comment_events(payload)

    for event in events:
        try:
            norm = facebook_comments_adapter.normalise(event)
            if norm:
                background_tasks.add_task(_process_and_respond, norm)
        except Exception as exc:
            logger.error("fb_comments_webhook.error", error=str(exc))

    return {"status": "ok"}
