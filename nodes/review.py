"""Review nodes — human-in-the-loop approval for generated images and ad copy.

These nodes used to live in a single `review_node` that ran a `while True` loop
with several `interrupt()` calls and image-generation side effects *between*
them. That is the classic LangGraph foot-gun: when the graph resumes from an
interrupt the whole node re-executes from the top, replaying every previous
`interrupt()` (which return their resolved values) **and re-running every side
effect in between** — i.e. every prior image regeneration fires again. That
silently re-bills the image API and produces brand-new (different) images, so
the "pick from previously generated" picker ended up showing freshly generated
images instead of the real history.

The fix splits the flow into four nodes wired through the graph:

    creative_node ─▶ image_review_node ─┬─(to_text)──▶ text_review_node
                                        ├─(to_regen)─▶ image_regen_node ─▶ (loop back)
                                        └─(to_pick)──▶ image_pick_node ──▶ text_review_node

Each image generation now happens inside `image_regen_node`, which contains no
interrupt — so it runs exactly once per super-step and its result is committed
to the checkpoint. Resuming an interrupt only re-runs the *interrupting* node
(which has no side effects), so a generation is never replayed.
"""

import base64
import logging
import os

from langgraph.types import interrupt

from llm_client import enhance_ad_image, generate_ad_images

logger = logging.getLogger(__name__)

# Read configurable regeneration limit from environment
MAX_REGENERATIONS_ALLOWED = int(os.getenv("MAX_REGENERATIONS_ALLOWED", "2"))


def _build_choices(image_path: str, image_history: list[str]) -> tuple[list[str], bool]:
    """Build the pick-from-history gallery: the user's ORIGINAL photo first
    (if available), followed by every previously generated image. No new
    images are ever generated here.

    Returns (choices, has_original).
    """
    choices: list[str] = list(image_history)
    original_b64: str | None = None
    if image_path:
        try:
            with open(image_path, "rb") as fh:
                original_b64 = base64.b64encode(fh.read()).decode("utf-8")
        except OSError as e:
            logger.warning("review: could not read original image for picker: %s", e)
    if original_b64:
        choices = [original_b64] + choices
    return choices, bool(original_b64)


# ------------------------------------------------------------------ #
# Phase 1a: Image review — interrupt only, no image generation        #
# ------------------------------------------------------------------ #
def image_review_node(state: dict) -> dict:
    """Show the current ad image and capture the user's decision.

    Contains a single `interrupt()` and **no** image-generation side effects,
    so it is safe to replay on resume. It only decides where to route next:

        - "to_text"  → approved (or use_original / text-only redo): go to copy review
        - "to_regen" → user rejected and regenerations remain: go regenerate
        - "to_pick"  → regenerations exhausted (or explicit "show me all"): go pick

    Interrupt payload: {"stage": "image_review", "images": [...],
                        "regen_count": int, "max_regens": int, "can_regenerate": bool}
    Resume payload:    {"approved": [bool, ...], "feedback": {int|str: str}}
                       or {"action": "pick_from_history"}
    """
    creative = dict(state.get("creative_output") or {})
    images: list[str] = list(creative.get("generated_images") or [])
    image_mode: str = state.get("image_mode", "use_original")

    # On a text-only redo pass the image was already approved and reused, so
    # skip image review entirely and jump straight to text review.
    is_redo = bool((state.get("feedback") or {}).get("creative"))
    if is_redo:
        logger.info("image_review_node: redo pass — skipping image review")
        return {"review_route": "to_text"}

    if image_mode == "use_original":
        # User chose their own photo — confirm it, never regenerate.
        interrupt({
            "stage": "image_review",
            "images": images,
            "regen_count": 0,
            "max_regens": 0,
            "can_regenerate": False,
        })
        creative["generated_images"] = images
        return {"review_route": "to_text", "creative_output": creative}

    # "enhance_with_ai" mode — regeneration is allowed.
    # Seed the history with the first generated image(s) the first time through.
    image_history: list[str] = list(state.get("image_history") or images)
    regen_count: int = state.get("regen_count", 0)

    result = interrupt({
        "stage": "image_review",
        "images": images,
        "regen_count": regen_count,
        "max_regens": MAX_REGENERATIONS_ALLOWED,
        "can_regenerate": True,
    })

    explicit_pick = result.get("action") == "pick_from_history"
    approved_list: list[bool] = result.get("approved", [True] * len(images))
    img_feedback: dict = result.get("feedback", {})

    if not explicit_pick and approved_list and all(approved_list):
        # Approved as-is → commit and move on to text review.
        creative["generated_images"] = images
        return {
            "review_route": "to_text",
            "creative_output": creative,
            "image_history": image_history,
            "regen_count": regen_count,
        }

    if explicit_pick or regen_count >= MAX_REGENERATIONS_ALLOWED:
        # No more regenerations — show the picker (history + original). This is
        # the path that used to silently regenerate; it now NEVER does.
        return {
            "review_route": "to_pick",
            "image_history": image_history,
            "regen_count": regen_count,
        }

    # Otherwise regenerate the rejected image(s) in a dedicated node.
    regen_indices = [i for i, ok in enumerate(approved_list) if not ok]
    if not regen_indices:
        regen_indices = [0]
    return {
        "review_route": "to_regen",
        "image_history": image_history,
        "regen_count": regen_count,
        "regen_indices": regen_indices,
        "image_regen_feedback": img_feedback,
    }


# ------------------------------------------------------------------ #
# Phase 1b: Image regeneration — side effect node, no interrupt       #
# ------------------------------------------------------------------ #
def image_regen_node(state: dict) -> dict:
    """Regenerate the rejected image(s) exactly once.

    This is the only place image generation happens during review, and it has
    no `interrupt()`, so its (costly) output is committed to the checkpoint and
    never replayed. It then loops back to `image_review_node`.
    """
    creative = dict(state.get("creative_output") or {})
    images: list[str] = list(creative.get("generated_images") or [])
    visual_prompt: str = creative.get("visual_prompt", "")
    image_path: str = state.get("image_path", "")
    image_history: list[str] = list(state.get("image_history") or images)
    regen_count: int = state.get("regen_count", 0)
    regen_indices: list[int] = state.get("regen_indices") or [0]
    img_feedback: dict = state.get("image_regen_feedback") or {}

    for idx in regen_indices:
        if idx >= len(images):
            continue
        fb = img_feedback.get(idx, img_feedback.get(str(idx), ""))
        regen_prompt = visual_prompt
        if fb:
            regen_prompt = f"{visual_prompt}. Additional instruction: {fb}"
        try:
            if image_path:
                new_images = enhance_ad_image(image_path, regen_prompt, n=1)
            else:
                new_images = generate_ad_images(regen_prompt, n=1)
            if new_images:
                images[idx] = new_images[0]
                image_history.append(new_images[0])
                logger.info("image_regen_node: re-enhanced image %d", idx)
        except RuntimeError as e:
            logger.warning("image_regen_node: regen failed for image %d: %s", idx, e)

    creative["generated_images"] = images
    return {
        "creative_output": creative,
        "image_history": image_history,
        "regen_count": regen_count + 1,
    }


# ------------------------------------------------------------------ #
# Phase 1c: Pick from history — interrupt only, no generation         #
# ------------------------------------------------------------------ #
def image_pick_node(state: dict) -> dict:
    """Let the user pick one of the images we've already produced.

    Builds the gallery from the REAL stored history (original photo first, then
    every previously generated image) and never calls the image API. Safe to
    replay on resume.

    Interrupt payload: {"stage": "max_regenerations_exceeded",
                        "image_history": [...], "has_original": bool, "message": str}
    Resume payload:    {"chosen_index": int}
    """
    creative = dict(state.get("creative_output") or {})
    image_history: list[str] = list(state.get("image_history") or [])
    image_path: str = state.get("image_path", "")

    choices, has_original = _build_choices(image_path, image_history)
    pick_result = interrupt({
        "stage": "max_regenerations_exceeded",
        "image_history": choices,
        "has_original": has_original,
        "message": (
            "Here are all the versions we've created"
            + (" (your original photo is first)" if has_original else "")
            + " — pick the one you'd like to use."
        ),
    })

    chosen_index = pick_result.get("chosen_index", 0)
    chosen_index = max(0, min(chosen_index, len(choices) - 1)) if choices else 0
    if choices:
        creative["generated_images"] = [choices[chosen_index]]

    return {"review_route": "to_text", "creative_output": creative}


# ------------------------------------------------------------------ #
# Phase 2: Text review — single interrupt                             #
# ------------------------------------------------------------------ #
def text_review_node(state: dict) -> dict:
    """Let the user pick ONE copy + ONE headline (and optionally edit them).

    Interrupt payload: {"stage": "text_review", "copies": [...],
                        "headlines": [...], "cta": str}
    Resume payload:    {"copy_index": int, "headline_index": int,
                        "copy_text": str, "headline_text": str}

    The chosen (possibly edited) copy/headline are moved to the front of the
    creative so they're the primary text used everywhere downstream (ad preview,
    Meta creative). Always proceeds to merge_node.
    """
    creative = dict(state.get("creative_output") or {})
    copies = list(creative.get("copies") or [])
    headlines = list(creative.get("headlines") or [])

    result = interrupt({
        "stage": "text_review",
        "copies": copies,
        "headlines": headlines,
        "cta": creative.get("cta", ""),
    })

    ci = result.get("copy_index", 0)
    hi = result.get("headline_index", 0)

    def _pick(items: list[str], idx: int, override: str) -> tuple[str, list[str]]:
        chosen = override.strip() if (override or "").strip() else (
            items[idx] if 0 <= idx < len(items) else (items[0] if items else "")
        )
        rest = [it for i, it in enumerate(items) if i != idx]
        return chosen, [chosen] + rest

    chosen_copy, new_copies = _pick(copies, ci, result.get("copy_text", ""))
    chosen_headline, new_headlines = _pick(headlines, hi, result.get("headline_text", ""))

    creative["copies"] = new_copies
    creative["headlines"] = new_headlines
    creative["selected_copy"] = chosen_copy
    creative["selected_headline"] = chosen_headline

    return {
        "creative_output": creative,
        "review_stage": "done",
        "feedback": {},
    }
