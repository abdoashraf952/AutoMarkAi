"""Media buying node — budget allocation, audience targeting, and bid strategy."""

import json
import logging

from llm_client import _parse_json_with_retry, call_llm
from prompts.media_buying import SYSTEM, USER_TEMPLATE

logger = logging.getLogger(__name__)


def media_buying_node(state: dict) -> dict:
    """
    Define the media buying strategy from campaign_plan.

    Uses Gemini with Groq fallback on rate limit / service errors.
    """
    try:
        prompt = USER_TEMPLATE.format(
            campaign_plan_json=json.dumps(state["campaign_plan"], indent=2),
            budget=state["budget"],
            goal=state["goal"],
        )
        raw, provider = call_llm(prompt, SYSTEM, "media_buying", allow_fallback=True)
        media_output = _parse_json_with_retry(raw)
        logger.info("media_buying_node complete via %s", provider)
        return {
            "media_output": media_output,
            "llm_used": {"media_buying": provider},
            "errors": [],
        }
    except Exception as e:
        logger.error("media_buying_node failed: %s", e)
        return {
            "media_output": {},
            "errors": [f"media_buying_node failed: {e}"],
        }
