"""Real estate helpers — price-tier smart defaults (CHANGE 8).

Given a compound's starting price (in EGP), infer sensible defaults for tone,
platform split, buyer type, and strategist archetype. These flow into the
campaign_plan so the strategy, creative, and media nodes share one source of
truth for "who" and "how".
"""

import logging
import re

logger = logging.getLogger(__name__)


def parse_price_egp(raw) -> float:
    """Best-effort parse of a free-text price into a float number of EGP.

    Handles inputs like "2,500,000", "2.5M", "starts at 3 million EGP", "٣ مليون".
    Returns 0.0 when nothing numeric can be extracted.
    """
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip().lower()
    # Normalise Arabic-Indic digits to ASCII.
    trans = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    text = text.translate(trans)

    # Detect a "million" hint (English or Arabic).
    million = bool(re.search(r"m\b|million|مليون", text))
    # Grab the first number (allow decimals and thousands separators).
    match = re.search(r"\d[\d,\.]*", text)
    if not match:
        return 0.0
    num_str = match.group(0).replace(",", "")
    try:
        value = float(num_str)
    except ValueError:
        return 0.0
    if million and value < 1000:
        value *= 1_000_000
    return value


def get_price_tier(starting_price_egp: float) -> dict:
    """Return smart defaults based on the real estate price tier."""
    price = parse_price_egp(starting_price_egp)
    if price < 2_000_000:
        return {
            "tier": "affordable",
            "tone": "warm and family-oriented",
            "platform_split": {"facebook": 0.6, "instagram": 0.4},
            "buyer_type": "first-time buyers, young couples",
            "archetype": "millennial_general",
            "recommended_offer": "zero_down",
        }
    elif price < 5_000_000:
        return {
            "tier": "mid_range",
            "tone": "modern and aspirational",
            "platform_split": {"facebook": 0.5, "instagram": 0.5},
            "buyer_type": "mid-income families, upgraders",
            "archetype": "millennial_general",
            "recommended_offer": "limited_units",
        }
    elif price < 15_000_000:
        return {
            "tier": "premium",
            "tone": "exclusive and lifestyle-driven",
            "platform_split": {"facebook": 0.4, "instagram": 0.6},
            "buyer_type": "upper professionals, executive families",
            "archetype": "professionals_b2b",
            "recommended_offer": "cash_discount",
        }
    else:
        return {
            "tier": "luxury",
            "tone": "exclusive and aspirational",
            "platform_split": {"facebook": 0.3, "instagram": 0.7},
            "buyer_type": "high-net-worth individuals, investors",
            "archetype": "professionals_b2b",
            "recommended_offer": "cash_discount",
        }
