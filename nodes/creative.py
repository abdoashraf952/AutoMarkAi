"""Creative node — generates ad copies, headlines, CTA, visual prompt, and ad images."""

import base64
import json
import logging
import os

from llm_client import _parse_json_with_retry, call_llm, enhance_ad_image, generate_ad_images
from i18n import get_creative_prompts

logger = logging.getLogger(__name__)

NUM_GENERATED_IMAGES = int(os.getenv("NUM_GENERATED_IMAGES", "1"))


def creative_node(state: dict) -> dict:
    """
    Generate ad creative assets from campaign_plan.

    Picks prompts from the locale system (language + marketing_type).
    Appends user feedback on redo passes.
    Sources the ad image based on image_mode.

    State reads:  campaign_plan, budget, goal, image_mode, image_path, feedback, language, marketing_type
    State writes: creative_output, llm_used, errors
    """
    # Resolve language / marketing_type from plan or state (plan is authoritative after orchestrator)
    plan = state.get("campaign_plan") or {}
    language = plan.get("language") or state.get("language", "en")
    marketing_type = plan.get("marketing_type") or state.get("marketing_type", "product")

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

        raw, provider = call_llm(prompt, system, "creative", allow_fallback=True)
        creative_output = _parse_json_with_retry(raw)

        # Source ad image based on image_mode
        image_mode = state.get("image_mode", "use_original")
        image_path = state.get("image_path", "")
        visual_prompt = creative_output.get("visual_prompt", "")
        generated_images: list[str] = []
        img_errors: list[str] = []

        # On a text-only redo pass (user asked to change the copy), reuse the
        # previously approved image instead of regenerating a brand-new one.
        prev_images = (state.get("creative_output") or {}).get("generated_images") or []
        if creative_feedback and prev_images:
            generated_images = list(prev_images)
            logger.info(
                "creative_node: redo pass — reusing %d existing image(s), skipping image regeneration",
                len(generated_images),
            )
        elif image_mode == "use_original":
            if image_path:
                try:
                    with open(image_path, "rb") as fh:
                        generated_images = [base64.b64encode(fh.read()).decode("utf-8")]
                    logger.info("creative_node: using original uploaded photo")
                except OSError as e:
                    img_errors.append(f"original_image_read_failed: {e}")

        elif visual_prompt:
            if image_mode == "enhance_with_ai" and image_path:
                try:
                    generated_images = enhance_ad_image(image_path, visual_prompt, n=NUM_GENERATED_IMAGES)
                    logger.info("creative_node: enhanced %d images", len(generated_images))
                except RuntimeError as e:
                    logger.warning("creative_node: enhancement failed, falling back to generate: %s", e)
                    img_errors.append(f"image_enhancement_failed: {e}")
                    try:
                        generated_images = generate_ad_images(visual_prompt, n=NUM_GENERATED_IMAGES)
                    except RuntimeError as e2:
                        img_errors.append(f"image_generation_fallback_failed: {e2}")
            else:
                try:
                    generated_images = generate_ad_images(visual_prompt, n=NUM_GENERATED_IMAGES)
                    logger.info("creative_node generated %d images", len(generated_images))
                except RuntimeError as e:
                    logger.warning("creative_node: image generation failed: %s", e)
                    img_errors.append(f"image_generation_failed: {e}")

        creative_output["generated_images"] = generated_images

        logger.info("creative_node complete via %s (lang=%s type=%s)", provider, language, marketing_type)
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
