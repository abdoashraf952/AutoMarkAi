"""Review node — human-in-the-loop approval for generated images and ad copy."""

import logging

from langgraph.types import interrupt

from llm_client import generate_ad_images

logger = logging.getLogger(__name__)


def review_node(state: dict) -> dict:
    """
    Two-phase human review using LangGraph interrupt().

    Phase 1 — Image review (loops until all 3 images are approved):
        Interrupt payload: {"stage": "image_review", "images": [b64, b64, b64]}
        Resume payload:    {"approved": [bool, bool, bool], "feedback": {int|str: str}}
        Rejected images are regenerated individually with per-image feedback,
        then re-presented until the user approves all of them.

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

    # ------------------------------------------------------------------ #
    # Phase 1: Image review — loop until all images are approved           #
    # ------------------------------------------------------------------ #
    while True:
        result = interrupt({"stage": "image_review", "images": images})

        approved_list: list[bool] = result.get("approved", [True] * len(images))
        img_feedback: dict = result.get("feedback", {})

        if all(approved_list):
            break

        # Regenerate only rejected images, one at a time
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
                        logger.info("review_node: regenerated image %d", idx)
                except RuntimeError as e:
                    logger.warning("review_node: regen failed for image %d: %s", idx, e)
                    # Keep the old image — user can reject and retry

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
