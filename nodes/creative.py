"""Creative node — generates ad copies, headlines, CTA, visual prompt, and ad images."""

import json
import logging
import os

from llm_client import _parse_json_with_retry, call_llm, generate_ad_images
from prompts.creative import SYSTEM, USER_TEMPLATE

logger = logging.getLogger(__name__)

# Read configurable image count from environment
NUM_GENERATED_IMAGES = int(os.getenv("NUM_GENERATED_IMAGES", "1"))


def creative_node(state: dict) -> dict:
    """
    Generate ad creative assets from campaign_plan.

    After LLM text generation, calls Imagen to generate ad images from
    visual_prompt. Number of images is configurable via NUM_GENERATED_IMAGES
    env var (default: 1). Stores them as base64 strings in
    creative_output["generated_images"].

    If state["feedback"]["creative"] is set (redo pass), appends the feedback
    to the LLM prompt so the model revises its output.

    Uses Gemini with Groq fallback on rate limit / service errors.
    """
    try:
        # Inject text feedback if this is a redo pass
        extra = ""
        creative_feedback = (state.get("feedback") or {}).get("creative", "")
        if creative_feedback:
            extra = (
                f"\n\nUser feedback on previous version: {creative_feedback}\n"
                "Please revise the copies, headlines, and CTA accordingly."
            )

        prompt = USER_TEMPLATE.format(
            campaign_plan_json=json.dumps(state["campaign_plan"], indent=2),
            budget=state["budget"],
            goal=state["goal"],
        ) + extra

        raw, provider = call_llm(prompt, SYSTEM, "creative", allow_fallback=True)
        creative_output = _parse_json_with_retry(raw)

        # Generate ad images from visual_prompt (count from env)
        visual_prompt = creative_output.get("visual_prompt", "")
        generated_images: list[str] = []
        img_errors: list[str] = []
        if visual_prompt:
            try:
                generated_images = generate_ad_images(visual_prompt, n=NUM_GENERATED_IMAGES)
                logger.info("creative_node generated %d images", len(generated_images))
            except RuntimeError as e:
                logger.warning("creative_node: image generation failed: %s", e)
                img_errors.append(f"image_generation_failed: {e}")

        creative_output["generated_images"] = generated_images

        logger.info("creative_node complete via %s", provider)
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
