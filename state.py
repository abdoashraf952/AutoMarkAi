"""Shared state schema for the AutoMark AI campaign generation pipeline."""

import operator
from typing import Annotated, TypedDict


def _merge_dicts(a: dict, b: dict) -> dict:
    """Deep-merge two dicts; b values override a on conflict."""
    return {**a, **b}


class CampaignState(TypedDict, total=False):
    # --- inputs (set at START) ---
    image_path: str
    image_mode: str         # "use_original" | "enhance_with_ai"
    marketing_type: str     # "product" | "business" | "service"
    language: str           # "en" | "ar"
    budget: float
    goal: str

    # --- question_generator_node output (Edit 2) ---
    questions: list[str]       # 4 product-specific questions
    user_answers: dict          # {"0": answer, "1": answer, "2": answer, "3": answer}

    # --- orchestrator output ---
    campaign_plan: dict

    # --- sub-agent outputs ---
    # creative_output now includes generated_images: list[str] (Edit 1)
    creative_output: dict
    media_output: dict

    # --- review state (Edit 3) ---
    feedback: dict      # {"images": {int: str}, "creative": str}
    review_stage: str   # "images" | "redo_creative" | "done"

    # --- image-review sub-state (split review nodes) ---
    # These let each image generation happen in its own checkpointed graph
    # super-step so LangGraph never replays (and re-bills) a generation when
    # the graph resumes from an interrupt.
    image_history: list      # every image ever generated, in order
    regen_count: int         # how many regeneration rounds have run
    review_route: str        # router hint: "to_regen" | "to_pick" | "to_text"
    regen_indices: list      # which image indices the user rejected
    image_regen_feedback: dict  # {str(idx): "what to change"} for the rejected ones

    # --- final output ---
    campaign_bundle: dict

    # --- metadata ---
    # Custom reducers so fan-out workers don't overwrite each other's entries
    errors: Annotated[list, operator.add]
    llm_used: Annotated[dict, _merge_dicts]
