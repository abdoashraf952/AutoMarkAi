"""Compliance gate — HOUSING Special Ad Category validation (Phase 2).

Mandatory gate in the critical path: consolidates the three existing
HOUSING layers (prompts / node hard-override / Meta client declaration)
into a single explicit assertion node that runs AFTER merge_node and
BEFORE the campaign is considered ready to publish.

Per-market rules live in compliance/<market>.json so the constraints are
data, not code — swap the JSON to add a new market without touching Python.

Existing HOUSING layers that remain intact (defence-in-depth):
  1. Prompt-level HOUSING instructions in creative.py / media_buying.py prompts
  2. Hard age/gender override in media_buying_node
  3. merge_node audience override (Strategist persona → HOUSING wins)
  4. Meta client declaration: special_ad_categories: ["HOUSING"]
  5. ← THIS NODE: explicit assertion + logged compliance_result
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_RULES_DIR = Path(__file__).resolve().parents[1] / "compliance"


def _load_rules(market: str = "egypt") -> dict:
    path = _RULES_DIR / f"{market}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("compliance: rules file not found for market=%s", market)
        return {}


def _check_targeting(audience: dict, rules: dict) -> list[str]:
    """Return hard violations in the audience targeting block."""
    violations: list[str] = []
    tr = rules.get("targeting_rules", {})
    blocked = tr.get("blocked_fields", [])

    for field in blocked:
        if audience.get(field):
            violations.append(f"HOUSING: audience.{field} is set — not allowed under Special Ad Category")

    age_min = audience.get("age_min")
    age_max = audience.get("age_max")
    allowed_min = tr.get("age_min", 18)
    allowed_max = tr.get("age_max", 65)
    if isinstance(age_min, int) and age_min > allowed_min:
        violations.append(
            f"HOUSING: age_min={age_min} narrows below the allowed floor {allowed_min}"
        )
    if isinstance(age_max, int) and age_max < allowed_max:
        violations.append(
            f"HOUSING: age_max={age_max} narrows above the allowed ceiling {allowed_max}"
        )

    genders = audience.get("genders", [])
    if genders and set(genders) != {"all"}:
        violations.append(
            f"HOUSING: genders={genders} targets a specific gender — must be ['all']"
        )

    return violations


def _check_copy(copies: list[str], headlines: list[str], rules: dict) -> list[str]:
    """Return violations for preference/personal-attribute language in copy."""
    violations: list[str] = []
    cv = rules.get("copy_violations", {})
    preference = cv.get("preference_language", [])
    personal = cv.get("personal_attribute_framing", [])
    all_text = " ".join(copies + headlines).lower()

    for phrase in preference:
        if phrase.lower() in all_text:
            violations.append(f"HOUSING copy: preference language detected — '{phrase}'")

    for phrase in personal:
        if phrase.lower() in all_text:
            violations.append(f"HOUSING copy: personal-attribute framing — '{phrase}'")

    return violations


def compliance_node(state: dict) -> dict:
    """
    Validate the assembled campaign bundle for HOUSING compliance.

    State reads:  media_output, creative_output, campaign_plan
    State writes: compliance_result

    compliance_result["passed"] = False → /publish endpoint will block the request
    compliance_result["warnings"]       → soft issues logged but not blocking
    All findings are appended to errors[] so the frontend can surface them.
    """
    rules = _load_rules("egypt")

    media = dict(state.get("media_output") or {})
    creative = dict(state.get("creative_output") or {})

    audience = media.get("audience") or {}
    copies = creative.get("copies") or []
    headlines = creative.get("headlines") or []

    violations: list[str] = []
    warnings: list[str] = []

    # ── Targeting ──────────────────────────────────────────────────────
    violations.extend(_check_targeting(audience, rules))

    # ── Copy ───────────────────────────────────────────────────────────
    violations.extend(_check_copy(copies, headlines, rules))

    # ── Special ad category declaration ────────────────────────────────
    if media.get("special_ad_category") != "HOUSING":
        violations.append("special_ad_category not declared as HOUSING in media_output")

    # ── Soft warnings ──────────────────────────────────────────────────
    if not audience.get("locations"):
        warnings.append("No locations on audience; will default to EG at publish time")

    geo = rules.get("geo_targeting", {})
    radius = audience.get("radius_km")
    if radius and radius > geo.get("radius_max_km", 80):
        warnings.append(
            f"Geo radius {radius}km exceeds recommended max {geo['radius_max_km']}km"
        )

    passed = len(violations) == 0

    if violations:
        logger.warning(
            "compliance_node FAILED: %d violation(s): %s", len(violations), violations
        )
    else:
        logger.info("compliance_node PASSED (warnings=%d)", len(warnings))

    compliance_result = {
        "passed": passed,
        "violations": violations,
        "warnings": warnings,
        "market": "EG",
        "special_ad_category": "HOUSING",
    }

    # Violations surface in the shared errors list so merge_node / api.py
    # can include them in bundle.meta.warnings without a separate read.
    return {
        "compliance_result": compliance_result,
        "errors": violations,
    }
