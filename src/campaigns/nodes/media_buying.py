"""Media buying node — budget allocation, audience targeting, and bid strategy."""

import json
import logging

from src.campaigns.llm_client import _parse_json_with_retry, call_llm
from src.campaigns.i18n import get_media_buying_prompts
from src.campaigns.strategy_tools import build_strategy_context

logger = logging.getLogger(__name__)


def media_buying_node(state: dict) -> dict:
    """
    Define the media buying strategy from campaign_plan.

    Uses Gemini for text generation. Picks locale-aware prompts (Arabic market
    defaults differ: Egyptian locations, different platform split rules).

    State reads:  campaign_plan, budget, goal, language
    State writes: media_output, llm_used, errors
    """
    plan = state.get("campaign_plan") or {}
    language = plan.get("language") or state.get("language", "en")

    system, user_template = get_media_buying_prompts(language)

    try:
        prompt = user_template.format(
            campaign_plan_json=json.dumps(plan, indent=2, ensure_ascii=False),
            budget=state["budget"],
            goal=state["goal"],
        )

        # Phase 3: inject audience_plan from the research squad so the LLM
        # has the geo-radius, platform split, and targeting rationale.
        audience_plan = state.get("audience_plan")
        if audience_plan:
            audience_ctx = (
                f"\n\nAudience research (from research squad):\n"
                f"{json.dumps(audience_plan, indent=2, ensure_ascii=False)}\n"
                f"Use the geo and platform_split from the audience plan above. "
                f"Do NOT apply demographic narrowing — broad delivery only (HOUSING).\n"
            )
            prompt = audience_ctx + prompt

        # Align targeting with the Strategist's persona when available. (merge_node
        # also overrides the final audience with the persona as the source of truth.)
        strategy_context = build_strategy_context(state.get("strategy_output"), language)
        if strategy_context:
            prompt = f"{strategy_context}\n\n{prompt}"

        raw, provider = call_llm(prompt, system, "media_buying", allow_fallback=True)
        media_output = _parse_json_with_retry(raw)

        # HOUSING compliance — hard override of any LLM targeting that violates
        # Meta's Special Ad Category rules for real estate (CHANGE 5).
        audience = dict(media_output.get("audience") or {})
        audience["age_min"] = 18
        audience["age_max"] = 65
        audience["genders"] = ["all"]
        audience.pop("income_tier", None)  # not allowed for HOUSING
        if not audience.get("locations"):
            audience["locations"] = ["EG"]
        media_output["audience"] = audience
        media_output["special_ad_category"] = "HOUSING"

        logger.info("media_buying_node complete via %s (lang=%s)", provider, language)
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
