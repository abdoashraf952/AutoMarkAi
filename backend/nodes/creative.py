"""Creative node — generates ad copies, headlines, and CTA.

CHANGE 2: NO AI image generation or enhancement. Real estate ads must use the
agency's actual unit photos. This node only writes copy text and attaches the
user's uploaded photos (read from state["image_paths"]) as the ad creatives.
"""

import base64
import json
import logging

from AutoMarkAi.backend.llm_client import _parse_json_with_retry, call_llm
from AutoMarkAi.backend.i18n import get_creative_prompts
from AutoMarkAi.backend.strategy_tools import build_strategy_context

logger = logging.getLogger(__name__)


def creative_node(state: dict) -> dict:
    """
    Generate ad creative copy from campaign_plan and attach the real unit photos.

    State reads:  campaign_plan, budget, goal, image_paths, feedback, language
    State writes: creative_output, llm_used, errors
    """
    plan = state.get("campaign_plan") or {}
    language = plan.get("language") or state.get("language", "en")
    marketing_type = plan.get("marketing_type") or state.get("marketing_type", "real_estate")

    system, user_template = get_creative_prompts(language, marketing_type)

    try:
        # Inject text feedback if this is a redo pass
        creative_feedback = (state.get("feedback") or {}).get("creative", "")
        if creative_feedback:
            if language == "ar":
                feedback_context = (
                    f"\n\nملاحظة المستخدم على النسخة السابقة: {creative_feedback}\n"
                    "عدّل النصوص والعناوين بناءً على الملاحظة دي.\n"
                )
            else:
                feedback_context = (
                    f"\n\nUser feedback on previous version: {creative_feedback}\n"
                    "Please revise the copies, headlines, and CTA accordingly.\n"
                )
        else:
            feedback_context = ""

        prompt = user_template.format(
            campaign_plan_json=json.dumps(plan, indent=2, ensure_ascii=False),
            budget=state["budget"],
            goal=state["goal"],
            feedback_context=feedback_context,
        )

        strategy_context = build_strategy_context(state.get("strategy_output"), language)
        if strategy_context:
            prompt = f"{strategy_context}\n\n{prompt}"

        raw, provider = call_llm(prompt, system, "creative", allow_fallback=True)
        creative_output = _parse_json_with_retry(raw)
        # No AI visuals for real estate — strip any visual_prompt the model added.
        creative_output.pop("visual_prompt", None)

        # On a copy-only redo pass, keep the already-attached photos.
        prev_images = (state.get("creative_output") or {}).get("generated_images") or []
        img_errors: list[str] = []
        if creative_feedback and prev_images:
            generated_images = list(prev_images)
            logger.info("creative_node: redo pass — reusing %d photo(s)", len(generated_images))
        else:
            generated_images = []
            for path in state.get("image_paths") or []:
                try:
                    with open(path, "rb") as fh:
                        generated_images.append(base64.b64encode(fh.read()).decode("utf-8"))
                except OSError as e:
                    img_errors.append(f"image_read_failed: {e}")
            logger.info("creative_node: attached %d unit photo(s)", len(generated_images))

        creative_output["generated_images"] = generated_images

        logger.info("creative_node complete via %s (lang=%s)", provider, language)
        return {
            "creative_output": creative_output,
            "llm_used": {"creative": provider},
            "errors": img_errors,
        }
    except Exception as e:
        logger.error("creative_node failed: %s", e)
        return {
            "creative_output": {},
            "errors": [f"creative_node failed: {e}"],
        }
