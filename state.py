"""Shared state schema for the AutoMark AI campaign generation pipeline."""

import operator
from typing import Annotated, TypedDict


def _merge_dicts(a: dict, b: dict) -> dict:
    """Deep-merge two dicts; b values override a on conflict."""
    return {**a, **b}


class CampaignState(TypedDict, total=False):
    # --- inputs (set at START) ---
    image_path: str
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

    # --- final output ---
    campaign_bundle: dict

    # --- metadata ---
    # Custom reducers so fan-out workers don't overwrite each other's entries
    errors: Annotated[list, operator.add]
    llm_used: Annotated[dict, _merge_dicts]
