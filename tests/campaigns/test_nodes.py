"""Unit tests for all pipeline nodes. All LLM calls are mocked — no real API calls."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is on sys.path so imports work


# ---------------------------------------------------------------------------
# Test 1: orchestrator_node returns a valid campaign_plan
# ---------------------------------------------------------------------------

def test_orchestrator_returns_valid_campaign_plan():
    """Orchestrator should parse LLM JSON and populate all required campaign_plan keys."""
    from src.campaigns.nodes.orchestrator import orchestrator_node

    mock_plan = {
        "product_type": "luxury_watch",
        "product_description": "An elegant Swiss-made timepiece with a gold bezel.",
        "platform": "instagram",
        "objective": "MESSAGES",
        "tone": "aspirational",
        "target_audience_hint": "Affluent adults aged 28-50 interested in luxury lifestyle",
        "budget": 500.0,
        "currency": "USD",
    }

    state = {
        "image_path": "tests/sample_input/watch.jpg",
        "budget": 500.0,
        "goal": "get WhatsApp leads for luxury watch",
    }

    with patch("src.campaigns.nodes.orchestrator.analyze_visual", return_value=json.dumps(mock_plan)):
        result = orchestrator_node(state)

    assert "campaign_plan" in result
    plan = result["campaign_plan"]
    for key in ("product_type", "product_description", "platform", "objective", "tone"):
        assert key in plan, f"Missing key: {key}"
    assert plan["tone"] == "aspirational"
    assert result.get("errors") == []


# ---------------------------------------------------------------------------
# Test 2: creative_node returns exactly three copies
# ---------------------------------------------------------------------------

def test_creative_node_returns_three_copies(tmp_path):
    """Creative node should produce 3 copies/headlines and attach the real photos."""
    import base64
    from src.campaigns.nodes.creative import creative_node

    mock_creative = {
        "copies": [
            "Own a home in New Cairo. 0% down payment, 8 years installments.",
            "Your dream villa is waiting — limited units in Palm Hills.",
            "Last phase. Prices rising soon. Reserve your unit today.",
        ],
        "headlines": [
            "Live in New Cairo",
            "Limited Units Left",
            "0% Down Payment",
        ],
        "cta": "Sign Up",
        "visual_prompt": "should be stripped for real estate",
    }

    photo = tmp_path / "unit.jpg"
    photo.write_bytes(b"UNIT")

    state = {
        "campaign_plan": {
            "product_type": "Real Estate",
            "objective": "LEADS",
            "tone": "aspirational",
            "platform": "instagram",
            "language": "en",
        },
        "budget": 500.0,
        "goal": "generate leads",
        "image_paths": [str(photo)],
    }

    with patch("src.campaigns.nodes.creative.call_llm", return_value=(json.dumps(mock_creative), "gemini")):
        result = creative_node(state)

    assert "creative_output" in result
    assert len(result["creative_output"]["copies"]) == 3
    assert len(result["creative_output"]["headlines"]) == 3
    assert result["creative_output"]["cta"] == "Sign Up"
    assert result["llm_used"]["creative"] == "gemini"
    # Real estate uses the agency's actual photo, never AI images.
    assert result["creative_output"]["generated_images"] == [base64.b64encode(b"UNIT").decode("utf-8")]
    assert "visual_prompt" not in result["creative_output"]


# ---------------------------------------------------------------------------
# Test 3: media_buying_node budget_split sums to 1.0
# ---------------------------------------------------------------------------

def test_media_buying_budget_split_sums_to_one():
    """Media buying node should produce a budget_split that sums to exactly 1.0."""
    from src.campaigns.nodes.media_buying import media_buying_node

    mock_media = {
        "budget_split": {"instagram": 1.0, "facebook": 0.0},
        "daily_budget_usd": 71.43,
        "audience": {
            "age_min": 28,
            "age_max": 50,
            "genders": ["all"],
            "interests": ["luxury watches", "Swiss watches", "fine jewelry"],
            "income_tier": "top_10_percent",
        },
        "placement": ["feed", "stories", "reels"],
        "bid_strategy": "COST_CAP",
        "optimization_goal": "MESSAGES",
        "estimated_reach": {"min": 8000, "max": 20000},
        "reasoning": "Instagram-only for luxury product; COST_CAP for mid-range budget.",
    }

    state = {
        "campaign_plan": {
            "product_type": "luxury_watch",
            "platform": "instagram",
            "objective": "MESSAGES",
        },
        "budget": 500.0,
        "goal": "get WhatsApp leads",
    }

    with patch("src.campaigns.nodes.media_buying.call_llm", return_value=(json.dumps(mock_media), "gemini")):
        result = media_buying_node(state)

    assert "media_output" in result
    split = result["media_output"]["budget_split"]
    assert abs(sum(split.values()) - 1.0) <= 0.01, f"budget_split sums to {sum(split.values())}"


# ---------------------------------------------------------------------------
# Test 4: merge_node corrects mismatched CTA and logs a warning
# ---------------------------------------------------------------------------

def test_merge_node_cta_coherence_fix():
    """
    merge_node must override CTA to 'Send Message' when objective is MESSAGES
    but the creative node returned 'Shop Now', and log a warning.
    """
    from src.campaigns.nodes.merge import merge_node

    state = {
        "image_path": "tests/sample_input/watch.jpg",
        "budget": 500.0,
        "goal": "get WhatsApp leads",
        "campaign_plan": {
            "product_type": "luxury_watch",
            "product_description": "A gold Swiss watch.",
            "platform": "instagram",
            "objective": "MESSAGES",
            "tone": "aspirational",
            "target_audience_hint": "Affluent adults",
            "budget": 500.0,
            "currency": "USD",
        },
        "creative_output": {
            "copies": ["Copy A", "Copy B", "Copy C"],
            "headlines": ["H1", "H2", "H3"],
            "cta": "Shop Now",  # Mismatched — should be "Send Message"
            "visual_prompt": "A luxury watch on marble.",
        },
        "media_output": {
            "budget_split": {"instagram": 1.0, "facebook": 0.0},
            "daily_budget_usd": 71.43,
            "audience": {
                "age_min": 28,
                "age_max": 50,
                "genders": ["all"],
                "interests": ["luxury watches"],
                "income_tier": "top_10_percent",
            },
            "placement": ["feed", "stories"],
            "bid_strategy": "COST_CAP",
            "optimization_goal": "MESSAGES",
            "estimated_reach": {"min": 8000, "max": 20000},
            "reasoning": "Instagram-only for luxury.",
        },
        "errors": [],
        "llm_used": {"orchestrator": "gemini", "creative": "gemini", "media_buying": "gemini"},
    }

    result = merge_node(state)

    bundle = result["campaign_bundle"]
    assert bundle["creative"]["cta"] == "Send Message", (
        f"Expected CTA 'Send Message', got '{bundle['creative']['cta']}'"
    )
    # Warning should be recorded
    assert any("CTA mismatch" in w for w in result["errors"]), (
        "Expected a CTA mismatch warning in errors"
    )


# ---------------------------------------------------------------------------
# Test 5: call_llm runs on Gemini, standard and fast tiers
# ---------------------------------------------------------------------------

def test_call_llm_uses_gemini_standard_tier():
    """call_llm defaults to the standard Gemini text model."""
    import src.campaigns.llm_client as lc

    with patch.object(
        lc, "_gemini_text", return_value='{"result": "from gemini"}'
    ) as mock_gem:
        text, provider = lc.call_llm("test prompt", "system prompt", "test_node")

    assert provider == "gemini"
    assert "gemini" in text
    assert mock_gem.call_count == 1
    # (prompt, system_prompt, model_name)
    assert mock_gem.call_args.args[2] == lc.GEMINI_TEXT_MODEL


def test_call_llm_fast_uses_cheap_tier():
    """fast=True routes to the cheap/fast Gemini model, for summarisation."""
    import src.campaigns.llm_client as lc

    with patch.object(lc, "_gemini_text", return_value="• a bullet") as mock_gem:
        text, provider = lc.call_llm(
            "test prompt", "system prompt", "summarizer", fast=True
        )

    assert provider == "gemini"
    assert text == "• a bullet"
    assert mock_gem.call_args.args[2] == lc.GEMINI_FAST_MODEL
    assert lc.GEMINI_FAST_MODEL != lc.GEMINI_TEXT_MODEL


def test_call_llm_wraps_failures_with_node_name():
    """A provider failure surfaces as a RuntimeError naming the failing node."""
    import src.campaigns.llm_client as lc

    with patch.object(lc, "_gemini_text", side_effect=ValueError("boom")):
        with pytest.raises(RuntimeError, match="test_node"):
            lc.call_llm("p", "s", "test_node")
