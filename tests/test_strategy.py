"""Tests for the Strategist agent (strategy_node), its deterministic tools, and
the merge_node audience override."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


_MOCK_STRATEGY = {
    "target_persona": {
        "primary_segment": "Young women, students & early-career",
        "archetype": "gen_z_women",
        "gender": "female",
        "age_min": 16,
        "age_max": 26,
        "locations": ["EG"],
        "psychographics": ["beauty-conscious", "budget-aware"],
        "motivations": ["affordable freshness"],
        "interests": ["beauty", "fragrance", "skincare"],
    },
    "channels": {"primary": ["instagram", "tiktok"], "secondary": ["facebook"], "rationale": "visual"},
    "schedule": {
        "peak_windows": [
            {"label": "weeknight scroll", "days": ["Sun", "Mon"], "start": "22:30", "end": "01:30"},
            {"label": "weekend wake-up", "days": ["Fri", "Sat"], "start": "11:00", "end": "13:00"},
        ]
    },
    "cadence": {"ads_per_week": 5, "flight_days": 14, "refresh_creative_every_days": 7},
    "messaging_angles": ["smell amazing for less"],
    "rationale": "Young women in Egypt, active late nights and weekend mornings.",
}


# ---------------------------------------------------------------------------
# strategy_node
# ---------------------------------------------------------------------------

def test_strategy_node_produces_finalized_plan():
    """strategy_node returns persona + a finalized schedule (timezone, Meta format, start_time)."""
    import nodes.strategy
    from nodes.strategy import strategy_node

    state = {
        "campaign_plan": {
            "product_type": "body splash",
            "objective": "CONVERSIONS",
            "language": "ar",
            "marketing_type": "product",
        },
        "goal": "get online orders",
        "budget": 300.0,
    }

    with patch.dict(os.environ, {"ENABLE_WEB_SEARCH": "false"}):
        with patch("nodes.strategy.call_llm", return_value=(json.dumps(_MOCK_STRATEGY), "groq")):
            result = strategy_node(state)

    strat = result["strategy_output"]
    assert result["llm_used"] == {"strategy": "groq"}
    assert strat["target_persona"]["gender"] == "female"
    # timezone resolved from locations (EG → Cairo)
    assert strat["timezone"] == "Africa/Cairo"
    assert strat["timezone_offset"] == "+02:00"
    # Meta schedule was produced and the cross-midnight window was split
    sched = strat["schedule"]
    assert sched["enforced_on_meta"] is False
    assert len(sched["meta_adset_schedule"]) == 3  # 22:30-01:30 splits into 2, + 11:00-13:00
    assert sched["best_single_start_time"].endswith("+02:00")


def test_strategy_node_graceful_on_llm_failure():
    """A bad LLM response must not crash the pipeline — returns empty strategy + error."""
    from nodes.strategy import strategy_node

    with patch.dict(os.environ, {"ENABLE_WEB_SEARCH": "false"}):
        with patch("nodes.strategy.call_llm", return_value=("not json", "groq")):
            result = strategy_node({"campaign_plan": {"language": "en"}, "goal": "x", "budget": 100})

    assert result["strategy_output"] == {}
    assert any("strategy_node failed" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# deterministic tools
# ---------------------------------------------------------------------------

def test_to_meta_adset_schedule_splits_cross_midnight():
    from strategy_tools import to_meta_adset_schedule

    entries = to_meta_adset_schedule(
        [{"days": ["Sun", "Mon"], "start": "22:30", "end": "01:30"}]
    )
    assert len(entries) == 2
    assert entries[0] == {"days": [0, 1], "start_minute": 1350, "end_minute": 1439, "timezone_type": "USER"}
    assert entries[1] == {"days": [0, 1], "start_minute": 0, "end_minute": 90, "timezone_type": "USER"}


def test_to_meta_adset_schedule_normal_window():
    from strategy_tools import to_meta_adset_schedule

    entries = to_meta_adset_schedule([{"days": ["Fri", "Sat"], "start": "11:00", "end": "13:00"}])
    assert entries == [
        {"days": [5, 6], "start_minute": 660, "end_minute": 780, "timezone_type": "USER"}
    ]


def test_resolve_timezone_from_locations_and_locale():
    from strategy_tools import resolve_timezone

    assert resolve_timezone(["SA"], "en") == ("Asia/Riyadh", "+03:00")
    assert resolve_timezone([], "ar") == ("Africa/Cairo", "+02:00")
    assert resolve_timezone([], "en") == ("UTC", "+00:00")


def test_web_search_disabled_returns_empty():
    from strategy_tools import web_search

    with patch.dict(os.environ, {"ENABLE_WEB_SEARCH": "false"}):
        assert web_search("anything") == []


# ---------------------------------------------------------------------------
# merge_node audience override (Option X)
# ---------------------------------------------------------------------------

def test_merge_overrides_audience_with_persona():
    import importlib
    import nodes.merge
    importlib.reload(nodes.merge)
    from nodes.merge import merge_node

    state = {
        "review_stage": "done",
        "campaign_plan": {"objective": "CONVERSIONS"},
        "creative_output": {
            "copies": ["c1", "c2", "c3"],
            "headlines": ["h1", "h2", "h3"],
            "cta": "Shop Now",
            "visual_prompt": "x",
            "generated_images": [],
        },
        "media_output": {
            "budget_split": {"instagram": 1.0, "facebook": 0.0},
            "daily_budget_usd": 10.0,
            "audience": {"age_min": 18, "age_max": 65, "genders": ["all"], "interests": ["generic"]},
        },
        "strategy_output": {
            "target_persona": {
                "gender": "female",
                "age_min": 16,
                "age_max": 26,
                "interests": ["beauty", "fragrance"],
                "locations": ["EG"],
            },
            "schedule": {"peak_windows": []},
            "messaging_angles": ["affordable freshness"],
            "rationale": "young women",
        },
    }

    bundle = merge_node(state)["campaign_bundle"]
    audience = bundle["media"]["audience"]
    assert audience["genders"] == ["female"]
    assert audience["age_min"] == 16 and audience["age_max"] == 26
    assert audience["interests"] == ["beauty", "fragrance"]
    assert audience["locations"] == ["EG"]  # filled from persona when media had none
    # strategy section is folded into the bundle
    assert bundle["strategy"]["target_persona"]["gender"] == "female"
    assert bundle["strategy"]["rationale"] == "young women"
