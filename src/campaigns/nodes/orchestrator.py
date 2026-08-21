"""Orchestrator node — vision analysis via Gemini, produces campaign_plan."""

import logging

from src.campaigns.llm_client import _parse_json_with_retry, analyze_visual
from src.campaigns.i18n import get_orchestrator_prompts
from src.campaigns.real_estate_utils import get_price_tier

logger = logging.getLogger(__name__)


def _build_qa_context(state: dict) -> str:
    """Render the real estate interview answers + follow-ups for the planner."""
    data = state.get("real_estate_data") or {}
    follow_ups = state.get("follow_up_log") or []
    if not data and not follow_ups:
        return ""
    lines = ["Real estate project details collected from the owner:\n"]
    for k, v in data.items():
        if v:
            lines.append(f"- {k.replace('_', ' ')}: {v}")
    for fu in follow_ups:
        if fu.get("a"):
            lines.append(f"- {fu.get('q')} → {fu.get('a')}")
    return "\n".join(lines) + "\n\n"


def orchestrator_node(state: dict) -> dict:
    """
    Analyze the unit photos and interview answers to produce campaign_plan.

    State reads:  image_paths, budget, goal, language, real_estate_data, follow_up_log
    State writes: campaign_plan, llm_used, errors
    """
    language = state.get("language", "en")
    marketing_type = state.get("marketing_type", "real_estate")

    system, user_template = get_orchestrator_prompts(language, marketing_type)

    try:
        prompt = user_template.format(
            budget=state["budget"],
            goal=state["goal"],
            qa_context=_build_qa_context(state),
        )

        image_paths = state.get("image_paths") or []
        raw = analyze_visual(image_paths[0] if image_paths else None, prompt, system)
        campaign_plan = _parse_json_with_retry(raw)

        # Inject language / marketing_type so downstream nodes can use them.
        campaign_plan["language"] = language
        campaign_plan["marketing_type"] = marketing_type
        campaign_plan["special_ad_category"] = "HOUSING"

        # Smart defaults from the price tier (CHANGE 8).
        starting_price = (state.get("real_estate_data") or {}).get("starting_price")
        tier = get_price_tier(starting_price)
        campaign_plan["price_tier"] = tier
        # Let the tier set the tone when the model didn't provide a strong one.
        campaign_plan.setdefault("tone", tier["tone"])

        logger.info("orchestrator_node produced campaign_plan (tier=%s)", tier["tier"])
        return {
            "campaign_plan": campaign_plan,
            "llm_used": {"orchestrator": "gemini"},
            "errors": [],
        }
    except Exception as e:
        logger.error("orchestrator_node failed: %s", e)
        return {
            "campaign_plan": {},
            "errors": [f"orchestrator_node failed: {e}"],
        }
