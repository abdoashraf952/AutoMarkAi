"""Merge node — validates sub-agent outputs and assembles the final campaign_bundle."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# CTA values that match each campaign objective
_OBJECTIVE_CTA = {
    "MESSAGES": "Send Message",
    "CONVERSIONS": "Shop Now",
    "TRAFFIC": "Learn More",
    "AWARENESS": "Learn More",
}


def merge_node(state: dict) -> dict:
    """
    Validate creative_output and media_output, apply coherence fixes, and build campaign_bundle.
    No LLM calls — pure Python logic only.

    Edit 3: Guard against premature execution. When the review nodes are still in
            progress (media_buying_node finishes first), review_stage is set but not
            "done". In that case, return {} and let the real merge happen after review
            completes.
    """
    # Edit 3: skip if the human-in-the-loop review cycle hasn't completed yet
    review_stage = state.get("review_stage")
    if review_stage and review_stage != "done":
        logger.debug("merge_node: skipping — review_stage=%s", review_stage)
        return {}

    errors = list(state.get("errors") or [])
    creative = dict(state.get("creative_output") or {})
    media = dict(state.get("media_output") or {})
    strategy = dict(state.get("strategy_output") or {})
    plan = state.get("campaign_plan") or {}

    # --- Validate copies (3 required, max 125 chars each) ---
    copies = list(creative.get("copies") or [])
    while len(copies) < 3:
        copies.append("[Copy placeholder]")
    copies = [c[:125] for c in copies]
    creative["copies"] = copies

    # --- Validate headlines (3 required, max 40 chars each) ---
    headlines = list(creative.get("headlines") or [])
    while len(headlines) < 3:
        headlines.append("[Headline placeholder]")
    headlines = [h[:40] for h in headlines]
    creative["headlines"] = headlines

    # --- CTA coherence check ---
    objective = plan.get("objective", "").upper()
    expected_cta = _OBJECTIVE_CTA.get(objective)
    current_cta = creative.get("cta", "")
    if expected_cta and current_cta != expected_cta:
        warning = (
            f"CTA mismatch: objective={objective} expected '{expected_cta}' "
            f"but got '{current_cta}'. Overriding."
        )
        logger.warning(warning)
        errors.append(warning)
        creative["cta"] = expected_cta

    # --- Budget split coherence check ---
    split = media.get("budget_split") or {}
    if split:
        total = sum(split.values())
        if abs(total - 1.0) > 0.01:
            warning = f"budget_split summed to {total:.4f}; normalizing to 1.0"
            logger.warning(warning)
            errors.append(warning)
            media["budget_split"] = {k: round(v / total, 4) for k, v in split.items()}

    # --- Audience override (Strategist is the source of truth for "who") ---
    persona = strategy.get("target_persona") or {}
    if persona:
        audience = dict(media.get("audience") or {})
        if persona.get("age_min") is not None:
            audience["age_min"] = persona["age_min"]
        if persona.get("age_max") is not None:
            audience["age_max"] = persona["age_max"]
        gender = persona.get("gender")
        if gender in ("male", "female"):
            audience["genders"] = [gender]
        elif gender == "all":
            audience["genders"] = ["all"]
        if persona.get("interests"):
            audience["interests"] = persona["interests"]
        if persona.get("locations") and not audience.get("locations"):
            audience["locations"] = persona["locations"]
        media["audience"] = audience

    # --- HOUSING compliance — hard override (CHANGE 5) ---
    # Real estate ads fall under Meta's HOUSING Special Ad Category: no age/gender
    # narrowing. This wins over the Strategist persona above.
    audience = dict(media.get("audience") or {})
    audience["age_min"] = 18
    audience["age_max"] = 65
    audience["genders"] = ["all"]
    audience.pop("income_tier", None)
    if not audience.get("locations"):
        audience["locations"] = ["EG"]
    media["audience"] = audience

    # --- Daily budget from campaign duration (CHANGE 9) ---
    duration = state.get("campaign_duration_days") or 14
    try:
        total_budget = float(state.get("budget") or 0)
    except (TypeError, ValueError):
        total_budget = 0.0
    if total_budget > 0 and duration > 0:
        media["daily_budget_usd"] = round(total_budget / duration, 2)

    real_estate_data = state.get("real_estate_data") or {}

    # --- Assemble campaign_bundle ---
    campaign_bundle = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "llm_used": state.get("llm_used") or {},
            "warnings": errors,
        },
        "product": {
            "type": plan.get("product_type", "Real Estate"),
            "description": plan.get("product_description", ""),
        },
        "campaign": {
            "platform": plan.get("platform", ""),
            "objective": plan.get("objective", ""),
            "tone": plan.get("tone", ""),
            "special_ad_categories": ["HOUSING"],
        },
        "real_estate_project": {
            "compound_name": real_estate_data.get("compound_name", ""),
            "location": real_estate_data.get("location", ""),
            "unit_types": real_estate_data.get("unit_types", ""),
            "starting_price": real_estate_data.get("starting_price", ""),
            "payment_plan": real_estate_data.get("payment_plan", ""),
            "offer": real_estate_data.get("offer", ""),
            "lead_destination": state.get("lead_destination", "whatsapp"),
            "campaign_duration_days": state.get("campaign_duration_days", 14),
            "price_tier": (plan.get("price_tier") or {}).get("tier", ""),
        },
        "creative": {
            "copies": creative.get("copies", []),
            "headlines": creative.get("headlines", []),
            "cta": creative.get("cta", ""),
            "generated_images": creative.get("generated_images", []),  # user's real photos
        },
        "media": {
            "budget_split": media.get("budget_split", {}),
            "daily_budget_usd": media.get("daily_budget_usd", 0.0),
            "audience": media.get("audience", {}),
            "placement": media.get("placement", []),
            "bid_strategy": media.get("bid_strategy", ""),
            "optimization_goal": media.get("optimization_goal", ""),
            "estimated_reach": media.get("estimated_reach", {}),
            "reasoning": media.get("reasoning", ""),
        },
        "strategy": {
            "target_persona": strategy.get("target_persona", {}),
            "channels": strategy.get("channels", {}),
            "timezone": strategy.get("timezone", ""),
            "timezone_offset": strategy.get("timezone_offset", ""),
            "schedule": strategy.get("schedule", {}),
            "cadence": strategy.get("cadence", {}),
            "messaging_angles": strategy.get("messaging_angles", []),
            "rationale": strategy.get("rationale", ""),
        },
    }

    return {"campaign_bundle": campaign_bundle, "errors": errors}
