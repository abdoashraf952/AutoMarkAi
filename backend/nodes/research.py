"""Research squad — Phase 3.

Three non-interrupting nodes that run after discovery and before the
orchestrator. Their outputs are injected into the campaign plan and
media-buying prompt as additional context.

audience_node    → HOUSING-compliant geo + targeting plan (deterministic
                   price-tier defaults + optional LLM enrichment).
competitor_node  → Competitor hook/offer/format findings. Calls the real
                   Meta Ad Library API when META_SIMULATION_MODE=false.
trend_node       → Seasonal demand windows and paydays for Egypt, so the
                   scheduler can pick optimal launch timing.
"""

import logging
import os
from datetime import datetime, timezone

import requests

from AutoMarkAi.backend.real_estate_utils import get_price_tier, parse_price_egp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audience node
# ---------------------------------------------------------------------------

# Egypt metro areas with sensible geo-radius defaults
_EGYPT_GEO = {
    "cairo": {"city": "Cairo", "lat": 30.0444, "lon": 31.2357, "radius_km": 25},
    "alexandria": {"city": "Alexandria", "lat": 31.2001, "lon": 29.9187, "radius_km": 20},
    "giza": {"city": "Giza", "lat": 30.0131, "lon": 31.2089, "radius_km": 20},
    "new_cairo": {"city": "New Cairo", "lat": 30.0200, "lon": 31.4700, "radius_km": 15},
    "october": {"city": "6th of October", "lat": 29.9600, "lon": 30.9200, "radius_km": 15},
    "north_coast": {"city": "North Coast", "lat": 30.8500, "lon": 28.9500, "radius_km": 30},
    "ain_sokhna": {"city": "Ain Sokhna", "lat": 29.5967, "lon": 32.3500, "radius_km": 20},
    "new_administrative": {"city": "New Administrative Capital", "lat": 30.0200, "lon": 31.7400, "radius_km": 20},
}

_RETARGETING_POOLS = [
    "website_visitors_60d",
    "lead_form_openers_30d",
    "video_viewers_50pct_30d",
]


def _resolve_geo(location_text: str) -> dict:
    """Best-effort match location string to a known Egypt geo entry."""
    if not location_text:
        return _EGYPT_GEO["cairo"]
    loc = location_text.lower()
    for key, geo in _EGYPT_GEO.items():
        if key in loc or geo["city"].lower() in loc:
            return geo
    return {"city": location_text, "lat": None, "lon": None, "radius_km": 25}


def audience_node(state: dict) -> dict:
    """
    Build a HOUSING-compliant audience plan.

    Rules enforced here (mirroring the compliance gate — defence-in-depth):
      - age 18–65, genders=all (no narrowing)
      - geo-radius only (no ZIP/postal, no demographic neighbourhood)
      - broad delivery + creative-as-filter as primary targeting method
      - first-party retargeting pools listed but marked as Phase 6

    State reads:  real_estate_data, budget, language
    State writes: audience_plan
    """
    re_data = state.get("real_estate_data") or {}
    location_text = re_data.get("location", "")
    price_text = re_data.get("starting_price", "")
    target_buyer = re_data.get("target_buyer", "")

    tier = get_price_tier(price_text)
    geo = _resolve_geo(location_text)

    # Broad delivery + creative-as-filter is HOUSING-compliant and Meta-preferred
    broad_delivery_note = (
        "Use broad delivery (no interest/demographic targeting). "
        "Let the creative do the filtering — HOUSING Special Ad Category "
        "restricts demographic targeting; broad delivery + strong creative "
        "is the recommended approach."
    )

    audience_plan = {
        "targeting_approach": "broad_delivery_creative_as_filter",
        "geo": {
            "city": geo["city"],
            "radius_km": geo["radius_km"],
            "country": "EG",
            "lat": geo.get("lat"),
            "lon": geo.get("lon"),
        },
        "age_min": 18,
        "age_max": 65,
        "genders": ["all"],
        "interests": [],  # HOUSING: no interest targeting — broad delivery
        "broad_delivery_note": broad_delivery_note,
        "price_tier": tier["tier"],
        "buyer_profile": tier.get("buyer_type", ""),
        "archetype": tier.get("archetype", ""),
        "retargeting_pools": _RETARGETING_POOLS,
        "retargeting_note": "First-party retargeting is HOUSING-compliant; requires Pixel (Phase 6).",
        "platform_split": tier.get("platform_split", {"facebook": 0.5, "instagram": 0.5}),
    }

    logger.info(
        "audience_node: geo=%s radius=%dkm tier=%s",
        geo["city"], geo["radius_km"], tier["tier"],
    )
    return {"audience_plan": audience_plan, "errors": []}


# ---------------------------------------------------------------------------
# Competitor node (simulated — Ad Library API stub)
# ---------------------------------------------------------------------------

_SIMULATED_COMPETITORS = [
    {
        "brand": "Sodic",
        "hook": "Live the life you deserve — starting from 5% down payment",
        "offer": "5% down, 10-year installments",
        "format": "carousel",
        "run_days": 45,
        "insight": "Long run-length signals winning creative; down-payment hook outperforms price-led hooks",
    },
    {
        "brand": "Ora Developers",
        "hook": "Zed — where Cairo meets green living",
        "offer": "Flexible payment, handover 2026",
        "format": "video",
        "run_days": 32,
        "insight": "Lifestyle/greenery angle performs well for premium tier; delivery timeline builds urgency",
    },
    {
        "brand": "Mountain View",
        "hook": "Book your unit with 0% down",
        "offer": "Zero down payment, 8-year plan",
        "format": "single_image",
        "run_days": 28,
        "insight": "Zero-down is a strong hook for mid-range; single image with clear offer text outperforms carousel for direct response",
    },
]


def _fetch_ad_library(search_terms: str = "") -> list[dict]:
    """
    Call the Meta Ad Library API and return structured competitor findings.

    Endpoint: GET https://graph.facebook.com/v19.0/ads_archive
    Filters:  ad_reached_countries=EG, ad_type=ALL, ad_category=HOUSING
    Auth:     META_AD_LIBRARY_TOKEN (falls back to META_ACCESS_TOKEN)
    """
    token = os.getenv("META_AD_LIBRARY_TOKEN") or os.getenv("META_ACCESS_TOKEN", "")
    if not token:
        logger.warning("competitor_node: no META_AD_LIBRARY_TOKEN or META_ACCESS_TOKEN set")
        return []

    params: dict = {
        "access_token": token,
        "ad_reached_countries": '["EG"]',
        "ad_type": "ALL",
        "ad_category": "HOUSING",
        "fields": (
            "id,ad_creation_time,ad_creative_bodies,ad_creative_link_titles,"
            "ad_delivery_start_time,ad_delivery_stop_time,page_name,impressions"
        ),
        "limit": 20,
    }
    if search_terms:
        params["search_terms"] = search_terms

    try:
        resp = requests.get(
            "https://graph.facebook.com/v19.0/ads_archive",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        ads = resp.json().get("data", [])
    except Exception as e:
        logger.warning("competitor_node: Ad Library API call failed: %s", e)
        return []

    now = datetime.now(timezone.utc)
    findings: list[dict] = []
    for ad in ads:
        start_raw = ad.get("ad_delivery_start_time", "")
        stop_raw = ad.get("ad_delivery_stop_time", "")
        try:
            start_dt = datetime.fromisoformat(start_raw.replace("+0000", "+00:00")) if start_raw else None
            stop_dt = datetime.fromisoformat(stop_raw.replace("+0000", "+00:00")) if stop_raw else None
            end = stop_dt or now
            run_days = max(0, (end - start_dt).days) if start_dt else 0
        except Exception:
            run_days = 0

        bodies = ad.get("ad_creative_bodies") or []
        titles = ad.get("ad_creative_link_titles") or []
        hook = bodies[0] if bodies else (titles[0] if titles else "")
        imps = ad.get("impressions") or {}
        findings.append({
            "brand": ad.get("page_name", "Unknown"),
            "hook": hook[:200] if hook else "",
            "offer": titles[0][:100] if titles else "",
            "format": "unknown",
            "run_days": run_days,
            "impressions_range": f"{imps.get('lower_bound', '?')}–{imps.get('upper_bound', '?')}",
            "insight": (
                f"Running for {run_days} days — "
                + ("long run-length signals winner; " if run_days > 21 else "")
                + "extracted from live Meta Ad Library."
            ),
        })

    logger.info("competitor_node: fetched %d live ads from Meta Ad Library", len(findings))
    return findings


def competitor_node(state: dict) -> dict:
    """
    Gather competitor ad intelligence.

    META_SIMULATION_MODE=false → calls Meta Ad Library API (real Egyptian RE ads).
    META_SIMULATION_MODE=true  → returns curated synthetic data.

    State reads:  real_estate_data (for search_terms enrichment)
    State writes: competitor_findings
    """
    sim = os.getenv("META_SIMULATION_MODE", "true").lower() == "true"

    if sim:
        findings = _SIMULATED_COMPETITORS
        logger.info("competitor_node: simulation mode — %d synthetic findings", len(findings))
    else:
        re_data = state.get("real_estate_data") or {}
        compound = re_data.get("compound_name", "")
        location = re_data.get("location", "")
        search_terms = " ".join(filter(None, [compound, location, "عقارات", "كمبوند"]))
        findings = _fetch_ad_library(search_terms)
        if not findings:
            logger.warning("competitor_node: Ad Library returned 0 results — using synthetic fallback")
            findings = _SIMULATED_COMPETITORS

    return {"competitor_findings": findings, "errors": []}


# ---------------------------------------------------------------------------
# Trend & Demand node
# ---------------------------------------------------------------------------

# Egyptian real estate demand calendar (deterministic domain knowledge)
_EGYPT_DEMAND_WINDOWS = [
    {
        "label": "Post-Eid al-Fitr launch window",
        "months": [4, 5],
        "rationale": "Eid bonuses released; buyer motivation peaks; families planning new homes",
        "priority": "high",
    },
    {
        "label": "September–October school-year settling",
        "months": [9, 10],
        "rationale": "Families commit to location before next school year; strong for family units",
        "priority": "high",
    },
    {
        "label": "Year-end investor push",
        "months": [11, 12],
        "rationale": "Tax-year-end investor purchases; developers offer year-end promotions",
        "priority": "medium",
    },
    {
        "label": "Summer North Coast window",
        "months": [6, 7, 8],
        "rationale": "Chalets and second-home demand peaks; target vacation buyers",
        "priority": "medium",
    },
]

_EGYPT_PAYDAYS = {
    "government_sector": "last thursday of month",
    "private_sector": "25th–1st of month",
    "best_ad_days": ["thursday", "friday", "saturday"],
    "note": "Weekend in Egypt is Fri–Sat; Thursday evening is peak engagement for property ads",
}


def trend_node(state: dict) -> dict:
    """
    Determine seasonal demand windows and payday timing for Egypt.

    In Phase 3 this is purely deterministic (domain knowledge encoded
    above). When ENABLE_WEB_SEARCH=true (future), it could enrich with
    live PropTech data. For now it gives the planner enough to recommend
    a launch window and the scheduler enough to know peak engagement days.

    State reads:  (nothing required — deterministic)
    State writes: demand_windows
    """
    web_search = os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "true"
    if web_search:
        logger.info("trend_node: ENABLE_WEB_SEARCH=true (live search not yet wired in Phase 3)")

    demand_windows = {
        "seasonal_windows": _EGYPT_DEMAND_WINDOWS,
        "payday_calendar": _EGYPT_PAYDAYS,
        "scheduling_advice": (
            "Launch on Thursday or Friday for maximum weekend reach. "
            "Align campaign start with post-salary period (25th–2nd). "
            "Budget boost during high-priority seasonal windows."
        ),
    }

    logger.info("trend_node: %d seasonal windows loaded", len(_EGYPT_DEMAND_WINDOWS))
    return {"demand_windows": [demand_windows], "errors": []}
