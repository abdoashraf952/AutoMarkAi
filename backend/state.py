"""Shared state schema for the AutoMark AI campaign generation pipeline."""

import operator
from typing import Annotated, TypedDict


def _merge_dicts(a: dict, b: dict) -> dict:
    """Deep-merge two dicts; b values override a on conflict."""
    return {**a, **b}


class CampaignState(TypedDict, total=False):
    # --- inputs (set at START) ---
    image_path: str
    image_mode: str         # "use_original" | "enhance_with_ai" | "generate_with_ai"
    # Owner-typed description of the product/business/service. Required (and used
    # by the vision-less nodes) when the photo is skipped; empty otherwise.
    product_description: str
    marketing_type: str     # "product" | "business" | "service"
    language: str           # "en" | "ar"
    budget: float
    goal: str

    # --- campaign-target question (the one fixed question, asked first) ---
    campaign_target_options: list   # ranked [{label, description, goal, recommended}]

    # --- question_generator_node output ---
    # Dynamic count: basic questions first, follow-ups only when valuable,
    # bounded by MIN_QUESTIONS/MAX_QUESTIONS.
    questions: list[str]       # adaptive follow-up questions (variable length)
    user_answers: dict          # {"0": answer, "1": answer, ...} (adaptive answers)
    questions_done: bool        # set by question_gen_node to end the interview

    # --- orchestrator output ---
    campaign_plan: dict

    # --- strategy agent output (Strategist) ---
    # Customized marketing plan: target_persona, channels, schedule (dayparting),
    # cadence, messaging_angles, rationale. Produced before the fan-out so creative
    # and media_buying can consume it; merge_node folds it into the bundle and uses
    # target_persona as the source of truth for audience targeting.
    strategy_output: dict

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
