"""
app/tools/messaging_tool.py — AutoMark AI CRM Agent (ORCAST)

`send_reply` delivers an ORCAST text response back to the channel the
inbound message came from:

- messenger        — text reply via app.api.messenger.send_message. If the
                      inbound turn was voice (input_type == "voice"), first
                      synthesize speech via gemini_service.synthesize_speech
                      and send it as an audio attachment via
                      send_voice_reply; falls back to text if synthesis or
                      delivery fails.
- facebook_comments — reply posted to the comment thread via
                      app.api.facebook_comments.reply_to_comment.
- vapi              — pure text passthrough. Vapi reads the response
                      directly from the webhook's HTTP body, so no outbound
                      API call is made here.
"""

from __future__ import annotations

import structlog
from langsmith import traceable
from tenacity import retry, retry_if_result, stop_after_attempt, wait_exponential

from app.services.gemini_service import UnifiedMessage, gemini_service

logger = structlog.get_logger(__name__)


def _retry_on_failure():
    return retry(
        retry=retry_if_result(lambda result: not result.get("success", False)),
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
    from app.api.messenger import messenger_adapter

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


@_retry_on_failure()
async def _send_facebook_comment_reply(message: UnifiedMessage, text: str) -> dict:
    from app.api.facebook_comments import facebook_comments_adapter

    comment_id = message.metadata.get("comment_id", "")
    if not comment_id:
        logger.warning("messaging_tool.missing_comment_id", user_id=message.user_id)
        return {"success": False, "error": "Missing comment_id"}

    result = await facebook_comments_adapter.reply_to_comment(comment_id, text)
    logger.info("messaging_tool.fb_comment_reply_sent", user_id=message.user_id, success=result.get("success"))
    return result
