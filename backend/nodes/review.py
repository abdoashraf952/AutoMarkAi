"""Review nodes — human-in-the-loop for photo selection and ad copy.

CHANGE 2: AI image generation/enhancement and the regeneration loop are gone.
Real estate ads use the agency's real photos, so the only image decision is
WHICH of the uploaded photos to include in the ad (photo_select_node). Each node
contains a single interrupt and no costly side effects, so resuming is safe.

    creative_node ─▶ photo_select_node ─▶ text_review_node ─▶ merge_node
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
    """
    image_paths = state.get("image_paths") or []
    images_b64: list[str] = []
    for path in image_paths:
        try:
            with open(path, "rb") as fh:
                images_b64.append(base64.b64encode(fh.read()).decode("utf-8"))
        except OSError as e:
            logger.warning("photo_select_node: could not read %s: %s", path, e)

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

    creative = dict(state.get("creative_output") or {})
    creative["generated_images"] = selected_images
    logger.info("photo_select_node: %d/%d photos selected", len(selected_images), len(images_b64))
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
