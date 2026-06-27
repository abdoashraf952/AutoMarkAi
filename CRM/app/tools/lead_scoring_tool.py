"""
app/tools/lead_scoring_tool.py — AutoMark AI CRM Agent (ORCAST)

Deterministic lead scoring (0-100). Pure function — no I/O, no LLM call.

Score formula
-------------
    score = budget_score     * W_BUDGET       (35%)
          + authority_score  * W_AUTHORITY    (30%)
          + engagement_score * W_ENGAGEMENT   (20%)
          + interest_score   * W_INTEREST     (15%)

All factor scores are normalised to [0, 100] before weighting. Weights sum to 1.0.

Temperature thresholds
-----------------------
    COLD      :  0 - 29
    WARM      : 30 - 59
    HOT       : 60 - 79
    QUALIFIED : 80 - 100

`name`, `email`, `phone` are identity passthrough fields — they are not used
in the scoring calculation, but are returned alongside the score so the
caller can persist the full lead profile in one update.
"""

from __future__ import annotations

import re
from typing import Optional

import structlog
from pydantic import BaseModel, EmailStr, Field, field_validator

logger = structlog.get_logger(__name__)

# ── Scoring weights (must sum to 1.0) ───────────────────────────────────────
W_BUDGET = 0.35
W_AUTHORITY = 0.30
W_ENGAGEMENT = 0.20
W_INTEREST = 0.15

assert abs(W_BUDGET + W_AUTHORITY + W_ENGAGEMENT + W_INTEREST - 1.0) < 1e-9

# ── Factor lookup tables ─────────────────────────────────────────────────────
BUDGET_SCORES: dict[str, int] = {
    "unknown": 5,
    "low": 25,
    "medium": 55,
    "high": 80,
    "very_high": 100,
}

AUTHORITY_SCORES: dict[str, int] = {
    "unknown": 5,
    "influencer": 40,
    "recommender": 70,
    "decision_maker": 100,
}

# Engagement and interest are already 0-10; scaled x10 -> 0-100


def _validate_phone(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    digits = re.sub(r"[\s\-().+]", "", v)
    if not digits.isdigit() or not (7 <= len(digits) <= 15):
        raise ValueError(
            f"Invalid phone number: '{v}'. Must contain 7-15 digits. "
            "Spaces, dashes, and parentheses are allowed."
        )
    return v


def _temperature(score: int) -> str:
    if score >= 80:
        return "qualified"
    elif score >= 60:
        return "hot"
    elif score >= 30:
        return "warm"
    else:
        return "cold"


class LeadScoringInput(BaseModel):
    """Mirrors the score_lead tool schema exactly."""

    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    budget: str = Field(
        default="unknown",
        description="unknown | low | medium | high | very_high",
    )
    authority: str = Field(
        default="unknown",
        description="unknown | influencer | recommender | decision_maker",
    )
    engagement_level: int = Field(default=0, ge=0, le=10)
    interest_level: int = Field(default=0, ge=0, le=10)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone(v)


def score_lead(args: dict) -> dict:
    """
    Calculate a lead score (0-100) from the provided factors.

    Returns
    -------
    {
        "score": int,
        "temperature": "cold" | "warm" | "hot" | "qualified",
        "breakdown": {...},
        "name": str | None,
        "email": str | None,
        "phone": str | None,
    }
    """
    data = LeadScoringInput(**args)

    budget = data.budget.lower()
    authority = data.authority.lower()
    engagement = max(0, min(10, data.engagement_level))
    interest = max(0, min(10, data.interest_level))

    f_budget = BUDGET_SCORES.get(budget, 5)
    f_authority = AUTHORITY_SCORES.get(authority, 5)
    f_engagement = engagement * 10
    f_interest = interest * 10

    raw_score = (
        f_budget * W_BUDGET
        + f_authority * W_AUTHORITY
        + f_engagement * W_ENGAGEMENT
        + f_interest * W_INTEREST
    )
    final_score = round(raw_score)
    temperature = _temperature(final_score)

    logger.info("lead_scoring.done", score=final_score, temperature=temperature)

    return {
        "score": final_score,
        "temperature": temperature,
        "breakdown": {
            "budget":     {"input": budget,     "raw_score": f_budget,     "weight": W_BUDGET,     "contribution": round(f_budget * W_BUDGET, 1)},
            "authority":  {"input": authority,  "raw_score": f_authority,  "weight": W_AUTHORITY,  "contribution": round(f_authority * W_AUTHORITY, 1)},
            "engagement": {"input": engagement, "raw_score": f_engagement, "weight": W_ENGAGEMENT, "contribution": round(f_engagement * W_ENGAGEMENT, 1)},
            "interest":   {"input": interest,   "raw_score": f_interest,   "weight": W_INTEREST,   "contribution": round(f_interest * W_INTEREST, 1)},
        },
        "name": data.name,
        "email": data.email,
        "phone": data.phone,
    }


def interpret(score: int) -> str:
    """Return a human-readable interpretation of the score."""
    temperature = _temperature(score)
    messages = {
        "cold": f"Cold lead ({score}/100). Needs nurturing before sales contact.",
        "warm": f"Warm lead ({score}/100). Good candidate for follow-up messaging.",
        "hot": f"Hot lead ({score}/100). Prioritise for sales outreach.",
        "qualified": f"Qualified lead ({score}/100). Sales-ready; escalate immediately.",
    }
    return messages[temperature]
