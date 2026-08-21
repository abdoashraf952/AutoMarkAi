"""Strategist node — builds the customized marketing plan (persona + channels + timing).

Runs after the orchestrator and BEFORE the creative/media fan-out, so its persona
and messaging angles are available to those nodes. Audience targeting derived here
becomes the source of truth (merge_node overrides media_buying's audience with it).

Text generation runs on Gemini. Timezone
resolution and the Meta schedule format are produced by deterministic helpers in
`strategy_tools`, so the timing facts are reliable rather than hallucinated.
"""

import json
import logging
from datetime import date

from src.campaigns.llm_client import _parse_json_with_retry, call_llm
from src.campaigns.i18n import get_strategy_prompts
from src.campaigns.strategy_tools import (
    build_search_query,
    finalize_schedule,
    format_web_context,
    get_dayparting_reference,
    web_search,
    web_search_enabled,
)

logger = logging.getLogger(__name__)


def strategy_node(state: dict) -> dict:
    """
    Produce the marketing strategy from campaign_plan.

    State reads:  campaign_plan, goal, budget, language, marketing_type
    State writes: strategy_output, llm_used, errors
    """
    plan = state.get("campaign_plan") or {}
    language = plan.get("language") or state.get("language", "en")
    marketing_type = plan.get("marketing_type") or state.get("marketing_type", "product")

    system, user_template = get_strategy_prompts(language)

    try:
        # Optional live-trends web search (opt-in via ENABLE_WEB_SEARCH)
        web_context = ""
        if web_search_enabled():
            web_context = format_web_context(web_search(build_search_query(plan)), language)
        if not web_context:
            web_context = "(none)" if language != "ar" else "(لا يوجد)"

        prompt = user_template.format(
            campaign_plan_json=json.dumps(plan, indent=2, ensure_ascii=False),
            budget=state.get("budget", 0),
            goal=state.get("goal", ""),
            today=date.today().isoformat(),
            dayparting_reference=get_dayparting_reference(language),
            web_context=web_context,
        )

        raw, provider = call_llm(prompt, system, "strategy")
        strategy = _parse_json_with_retry(raw)

        # Deterministic post-processing: timezone + Meta schedule + best start_time
        strategy = finalize_schedule(strategy, plan, language)

        logger.info(
            "strategy_node complete via %s (lang=%s type=%s, web_search=%s)",
            provider, language, marketing_type, web_search_enabled(),
        )
        return {
            "strategy_output": strategy,
            "llm_used": {"strategy": provider},
            "errors": [],
        }
    except Exception as e:
        logger.error("strategy_node failed: %s", e)
        return {
            "strategy_output": {},
            "errors": [f"strategy_node failed: {e}"],
        }
