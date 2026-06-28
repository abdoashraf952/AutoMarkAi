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

    # --- control plane (Phase 0 + 1) ---
    # campaign_phase tracks which part of the advanced pipeline is active.
    # Phase 0: only "discovery" and "build" are used.
    # Phase 4+: "operate" drives the lifecycle/diagnosis loop.
    campaign_phase: str           # "discovery" | "build" | "operate"

    # approval_mode controls how much the user is interrupted.
    #   full_manual  — all configurable gates interrupt (reproduces original behaviour)
    #   guided       — campaign-target auto-picked; creative gates still interrupt
    #   autopilot    — entire build path auto-approved; only publish requires user action
    approval_mode: str            # "full_manual" | "guided" | "autopilot"

    # feature_flags is the optionality matrix (all off by default in Phase 1).
    # e.g. {"image_gen": False, "video_gen": False, "retargeting": False}
    feature_flags: dict

    # pending_approval holds the current approval-gate item while waiting for
    # the user (or auto-approval). None / absent when no gate is open.
    pending_approval: dict

    # --- Phase 2: Compliance ---
    compliance_result: dict       # {passed, violations, warnings, market}

    # --- Phase 3: Research squad ---
    audience_plan: dict           # HOUSING-compliant geo/targeting plan
    competitor_findings: list     # [{hook, offer, format, run_days}] from Ad Library
    demand_windows: list          # [{label, months, rationale}] seasonal demand

    # --- Phase 4: Operate lifecycle ---
    # control_mode: which Meta strategy is active.
    control_mode: str             # "advantage_plus" | "manual"
    # metric_snapshots: time-series performance readings from Meta.
    metric_snapshots: list        # [{ts, cpl, qualified_rate, frequency, reach, spend}]
    # learning_state: whether the ad set is still in Meta's learning phase.
    learning_state: str           # "learning" | "exited" | "unstable"
    # decisions_log: every operate action + rationale (audit trail).
    decisions_log: list           # [{ts, decision, rationale, action_taken}]
    # lead_records: delivered leads (hashed PII) + quality feedback.
    lead_records: list            # [{ts, id, quality, crm_status}]
    # latest_diagnosis: plain-language report from the most recent diagnose cycle.
    latest_diagnosis: dict        # {summary, cpl, qualified_rate, recommendation}

    # --- Phase 4: Published campaign IDs (set after /publish succeeds) ---
    # Stored so diagnose_node and act_node can call the Meta Insights/Management APIs.
    meta_campaign_id: str         # Meta campaign ID returned by create_campaign
    meta_adset_id: str            # Meta ad set ID returned by create_ad_set

    # --- Phase 5: Memory ---
    # rolling_summary: compressed conversation / campaign history for this thread.
    rolling_summary: str
    # client_memory_ref: key into the long-term per-client JSON store.
    client_memory_ref: str        # compound_name or client identifier

    # --- metadata ---
    # Custom reducers so fan-out workers don't overwrite each other's entries
    errors: Annotated[list, operator.add]
    llm_used: Annotated[dict, _merge_dicts]
