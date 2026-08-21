"""
app/tools/messaging_tool.py — AutoMark AI CRM Agent (ORCAST)

`send_reply` delivers an ORCAST text response back to the originating channel:

- messenger         — text or TTS audio reply via Messenger Send API
- facebook_comments — two-step delivery:
                        1. SHORT public reply on the comment thread:
                           "Thanks! I've sent you a private message."
                        2. FULL AI response as a private Messenger DM
                           (uses comment_id as recipient — Meta routes as DM)
- vapi              — text passthrough (Vapi reads the HTTP response body)
"""

from __future__ import annotations

import structlog
from langsmith import traceable
from tenacity import retry, retry_if_result, stop_after_attempt, wait_exponential

from src.crm.services.gemini_service import UnifiedMessage, gemini_service

logger = structlog.get_logger(__name__)

_PUBLIC_COMMENT_REPLY = (
    "Thanks for your comment! I've sent you a private message to continue our conversation."
)


def _retry_on_failure():
    # Only retry on transient failures (network errors, 5xx).
    # 4xx errors (400, 401, 403) are permanent — retrying just floods logs.
    def _should_retry(result: dict) -> bool:
        if result.get("success"):
            return False
        error = result.get("error", "")
        # Don't retry permanent errors — token/auth/client issues won't change between retries
        permanent = any(s in error for s in (
            "400", "401", "403", "404",
            "OAuthException", "does not exist", "permission",
            "Invalid", "Unsupported", "expired",
        ))
        return not permanent

    return retry(
        retry=retry_if_result(_should_retry),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry_error_callback=lambda retry_state: retry_state.outcome.result(),
    )


@traceable(name="send_reply")
async def send_reply(message: UnifiedMessage, text: str) -> dict:
    """Deliver an ORCAST text response back to the originating channel."""
    log = logger.bind(user_id=message.user_id, source=message.source)
    log.info("messaging_tool.send_reply")

    if message.source == "messenger":
        return await _send_messenger_reply(message, text)
    elif message.source == "facebook_comments":
        return await _send_facebook_comment_reply(message, text)
    elif message.source == "vapi":
        return {"success": True}
    else:
        log.warning("messaging_tool.unknown_source")
        return {"success": False, "error": f"Unknown source: {message.source}"}


@_retry_on_failure()
async def _send_messenger_reply(message: UnifiedMessage, text: str) -> dict:
    from src.crm.api.messenger import messenger_adapter

    if message.input_type == "voice":
        tts = await gemini_service.synthesize_speech(text)
        if tts:
            audio_bytes, audio_mime = tts
            result = await messenger_adapter.send_voice_reply(message.user_id, audio_bytes, audio_mime)
            if result.get("success"):
                logger.info("messaging_tool.voice_reply_sent", user_id=message.user_id)
                return result
            logger.warning("messaging_tool.voice_reply_failed_fallback_text", user_id=message.user_id)

    result = await messenger_adapter.send_message(message.user_id, text)
    logger.info("messaging_tool.messenger_reply_sent", user_id=message.user_id, success=result.get("success"))
    return result


async def _send_facebook_comment_reply(message: UnifiedMessage, text: str) -> dict:
    from src.crm.api.facebook_comments import facebook_comments_adapter
    from src.crm.api.messenger import messenger_adapter

    comment_id = message.metadata.get("comment_id", "")
    if not comment_id:
        logger.warning("messaging_tool.missing_comment_id", user_id=message.user_id)
        return {"success": False, "error": "Missing comment_id"}

    # ── Step 1: brief PUBLIC reply on the comment thread ─────────────────────
    # Never expose the full AI response publicly — just acknowledge and redirect.
    result = await facebook_comments_adapter.reply_to_comment(comment_id, _PUBLIC_COMMENT_REPLY)
    logger.info("messaging_tool.fb_public_reply_sent", user_id=message.user_id, success=result.get("success"))

    # ── Step 2: full AI response as PRIVATE Messenger DM ─────────────────────
    # Meta routes {"recipient": {"comment_id": ...}} as a DM to the commenter.
    dm_result = await messenger_adapter.send_message_to_commenter(comment_id, text)
    if dm_result.get("success"):
        logger.info("messaging_tool.commenter_dm_sent", user_id=message.user_id)
    else:
        logger.warning(
            "messaging_tool.commenter_dm_failed",
            user_id=message.user_id,
            error=dm_result.get("error"),
        )

    return result
