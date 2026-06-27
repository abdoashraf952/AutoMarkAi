"""Shared state schema for the AutoMark AI real-estate campaign pipeline."""

import operator
from typing import Annotated, TypedDict


def _merge_dicts(a: dict, b: dict) -> dict:
    """Deep-merge two dicts; b values override a on conflict."""
    return {**a, **b}


class CampaignState(TypedDict, total=False):
    # --- inputs (set at START) ---
    image_paths: list[str]   # Real unit photos uploaded by the user (1+, no AI images)
    marketing_type: str      # Always "real_estate" — hardcoded, not user-selectable
    language: str            # "en" | "ar"
    budget: float
    goal: str

    # --- client assets (CHANGE 4: structured file uploads) ---
    logo_path: str           # path to the uploaded company logo
    asset_paths: dict        # {"brochure": path, "floor_plans": [..], "master_plan": path, "price_list": path}

    # --- campaign-target question (the one fixed question, asked first) ---
    campaign_target_options: list   # ranked [{label, description, goal, recommended}]

    # --- real estate interview (CHANGE 3) ---
    # The interview alternates fixed questions (curated list) with optional
    # LLM-generated follow-ups. Bookkeeping fields drive the gen/ask loop:
    current_fixed_q_index: int      # index of the fixed question currently in play
    is_follow_up: bool              # whether the pending question is an LLM follow-up
    pending_question: dict          # interrupt payload built by question_gen_node
    pending_answered: bool          # ask_node sets True after storing an answer
    last_answer_was_follow_up: bool # whether the most recent answer was a follow-up
    follow_up_log: list             # [{"q": .., "a": ..}] of follow-ups, for context
    questions_done: bool            # set when the interview is complete

    # Collected real estate facts (compound_name, location, unit_types, ...).
    real_estate_data: dict
    campaign_duration_days: int     # from the duration question (daily budget calc)
    lead_destination: str           # "whatsapp" | "phone" | "instant_form" | "landing_page"

    # Legacy adaptive-answer maps kept for orchestrator Q&A context.
    user_answers: dict

    # --- orchestrator output ---
    campaign_plan: dict

    # --- strategy agent output (Strategist) ---
    strategy_output: dict

    # --- sub-agent outputs ---
    # creative_output includes generated_images: list[str] (the user's real photos)
    creative_output: dict
    media_output: dict

    # --- review state ---
    feedback: dict      # {"creative": str}
    review_stage: str   # "photos_selected" | "redo_creative" | "done"

    # --- final output ---
    campaign_bundle: dict

    # --- metadata ---
    # Custom reducers so fan-out workers don't overwrite each other's entries
    errors: Annotated[list, operator.add]
    llm_used: Annotated[dict, _merge_dicts]
