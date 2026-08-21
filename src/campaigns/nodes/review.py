"""Review nodes — human-in-the-loop for photo selection and ad copy.

Real estate ads use the agency's real photos, so the only image decision is
WHICH of the uploaded photos to include in the ad (photo_select_node). Each
node contains at most one interrupt and no costly side effects, so resuming
a paused graph is always safe.

    creative_node ─▶ photo_select_node ─▶ text_review_node ─▶ merge_node

Phase 1: approval_mode is respected.
  • photo_select_node  — skips the interrupt in 'autopilot' mode (selects all photos).
  • text_review_node   — skips the interrupt in 'autopilot' mode (picks first copy/headline).
  • 'full_manual' and 'guided' modes behave identically to the original.
"""

import base64
import logging

from langgraph.types import interrupt

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Photo selection — pick which uploaded photos go in the ad           #
# ------------------------------------------------------------------ #
def photo_select_node(state: dict) -> dict:
    """Let the user pick which of their uploaded photos to use in the ad.

    Interrupt payload: {"stage": "photo_select", "images": [...base64...], "count": int}
    Resume payload:    {"selected_indices": [0, 2, 3]}

    In 'autopilot' approval_mode, all photos are selected automatically
    without an interrupt.
    """
    image_paths = state.get("image_paths") or []
    images_b64: list[str] = []
    for path in image_paths:
        try:
            with open(path, "rb") as fh:
                images_b64.append(base64.b64encode(fh.read()).decode("utf-8"))
        except OSError as e:
            logger.warning("photo_select_node: could not read %s: %s", path, e)

    mode = state.get("approval_mode", "full_manual")

    if mode == "autopilot":
        # Auto-select all photos without interrupting.
        selected_images = images_b64
        logger.info(
            "photo_select_node: auto-selected all %d photo(s) (approval_mode=autopilot)",
            len(selected_images),
        )
    else:
        result = interrupt({
            "stage": "photo_select",
            "images": images_b64,
            "count": len(images_b64),
        })
        selected = result.get("selected_indices") if isinstance(result, dict) else None
        if not selected:
            selected = list(range(len(images_b64)))
        selected_images = [images_b64[i] for i in selected if 0 <= i < len(images_b64)]
        if not selected_images:
            selected_images = images_b64  # never end up with zero photos

    logger.info(
        "photo_select_node: %d/%d photo(s) selected", len(selected_images), len(images_b64)
    )
    creative = dict(state.get("creative_output") or {})
    creative["generated_images"] = selected_images
    return {"creative_output": creative, "review_stage": "photos_selected"}


# ------------------------------------------------------------------ #
# Text review — single interrupt                                      #
# ------------------------------------------------------------------ #
def text_review_node(state: dict) -> dict:
    """Let the user pick ONE copy + ONE headline (and optionally edit them).

    Interrupt payload: {"stage": "text_review", "copies": [...],
                        "headlines": [...], "cta": str}
    Resume payload:    {"copy_index": int, "headline_index": int,
                        "copy_text": str, "headline_text": str}

    In 'autopilot' approval_mode, the first copy and first headline are
    selected automatically without an interrupt.
    """
    creative = dict(state.get("creative_output") or {})
    copies = list(creative.get("copies") or [])
    headlines = list(creative.get("headlines") or [])
    mode = state.get("approval_mode", "full_manual")

    def _pick(items: list[str], idx: int, override: str) -> tuple[str, list[str]]:
        chosen = override.strip() if (override or "").strip() else (
            items[idx] if 0 <= idx < len(items) else (items[0] if items else "")
        )
        rest = [it for i, it in enumerate(items) if i != idx]
        return chosen, [chosen] + rest

    if mode == "autopilot":
        # Auto-pick the first copy and headline without interrupting.
        chosen_copy, new_copies = _pick(copies, 0, "")
        chosen_headline, new_headlines = _pick(headlines, 0, "")
        logger.info("text_review_node: auto-picked copy + headline (approval_mode=autopilot)")
    else:
        result = interrupt({
            "stage": "text_review",
            "copies": copies,
            "headlines": headlines,
            "cta": creative.get("cta", ""),
        })
        ci = result.get("copy_index", 0)
        hi = result.get("headline_index", 0)
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
