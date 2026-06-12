"""Review node — human-in-the-loop approval for generated images and ad copy."""

import logging
import os

from langgraph.types import interrupt

from llm_client import generate_ad_images

logger = logging.getLogger(__name__)

# Read configurable regeneration limit from environment
MAX_REGENERATIONS_ALLOWED = int(os.getenv("MAX_REGENERATIONS_ALLOWED", "2"))


def review_node(state: dict) -> dict:
    """
    Two-phase human review using LangGraph interrupt().

    Phase 1 — Image review (loops until approved or max regenerations exceeded):
        Interrupt payload: {"stage": "image_review", "images": [...],
                            "regen_count": int, "max_regens": int}
        Resume payload:    {"approved": [bool, ...], "feedback": {int|str: str}}

        If user rejects and regen_count < MAX_REGENERATIONS_ALLOWED:
            Regenerate rejected images, increment counter, loop.
        If user rejects and regen_count >= MAX_REGENERATIONS_ALLOWED:
            Interrupt with stage "max_regenerations_exceeded" showing all
            previously generated images. User picks one or is told to wait 5h.
            Resume payload: {"chosen_index": int}

    Phase 2 — Text review (single interrupt):
        Interrupt payload: {"stage": "text_review",
                            "copies": [...], "headlines": [...], "cta": str}
        Resume payload:    {"approved": bool, "feedback": str}
        If rejected → returns review_stage="redo_creative" so the graph loops
                       back to creative_node with the feedback in state.
        If approved → returns review_stage="done" so merge_node runs.

    State reads:  creative_output (generated_images, visual_prompt, copies, headlines, cta)
    State writes: creative_output (updated images), feedback, review_stage
    """
    creative = dict(state.get("creative_output") or {})
    images: list[str] = list(creative.get("generated_images") or [])
    visual_prompt: str = creative.get("visual_prompt", "")

    # Track all images ever generated so user can pick from history
    image_history: list[str] = list(images)  # flat list of every image generated
    regen_count = 0

    # ------------------------------------------------------------------ #
    # Phase 1: Image review — loop until approved or max regens exceeded   #
    # ------------------------------------------------------------------ #
    while True:
        result = interrupt({
            "stage": "image_review",
            "images": images,
            "regen_count": regen_count,
            "max_regens": MAX_REGENERATIONS_ALLOWED,
        })

        approved_list: list[bool] = result.get("approved", [True] * len(images))
        img_feedback: dict = result.get("feedback", {})

        if all(approved_list):
            break

        # Check if we've hit the regeneration limit
        if regen_count >= MAX_REGENERATIONS_ALLOWED:
            # Send all previously generated images for the user to pick from
            pick_result = interrupt({
                "stage": "max_regenerations_exceeded",
                "image_history": image_history,
                "message": (
                    f"Maximum regenerations ({MAX_REGENERATIONS_ALLOWED}) exceeded. "
                    "You can choose one of the previously generated images below, "
                    "or try again after 5 hours."
                ),
            })
            chosen_index = pick_result.get("chosen_index", 0)
            # Clamp to valid range
            chosen_index = max(0, min(chosen_index, len(image_history) - 1))
            images = [image_history[chosen_index]]
            break

        # Regenerate rejected images, one at a time
        for idx, approved in enumerate(approved_list):
            if not approved:
                # Accept both int and str keys from the frontend
                fb = img_feedback.get(idx, img_feedback.get(str(idx), ""))
                regen_prompt = visual_prompt
                if fb:
                    regen_prompt = f"{visual_prompt}. Additional instruction: {fb}"
                try:
                    new_images = generate_ad_images(regen_prompt, n=1)
                    if new_images and idx < len(images):
                        images[idx] = new_images[0]
                        # Add to history for later fallback selection
                        image_history.append(new_images[0])
                        logger.info("review_node: regenerated image %d", idx)
                except RuntimeError as e:
                    logger.warning("review_node: regen failed for image %d: %s", idx, e)
                    # Keep the old image — user can reject and retry

        regen_count += 1

    # Commit approved (and any regenerated) images back to creative_output
    creative["generated_images"] = images

    # ------------------------------------------------------------------ #
    # Phase 2: Text review — single interrupt                              #
    # ------------------------------------------------------------------ #
    text_result = interrupt({
        "stage": "text_review",
        "copies": creative.get("copies", []),
        "headlines": creative.get("headlines", []),
        "cta": creative.get("cta", ""),
    })

    text_approved: bool = text_result.get("approved", False)
    text_feedback: str = text_result.get("feedback", "")

    if text_approved:
        return {
            "creative_output": creative,
            "review_stage": "done",
            "feedback": {},
        }
    else:
        return {
            "creative_output": creative,
            "review_stage": "redo_creative",
            "feedback": {"creative": text_feedback},
        }
