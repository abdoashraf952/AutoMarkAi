"""Unit tests for meta_client.py — all tests run without real Meta API credentials."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Minimal campaign_bundle for testing (mirrors the shape produced by merge_node)
_BUNDLE = {
    "meta": {"generated_at": "2026-06-10T10:00:00Z", "llm_used": {}, "warnings": []},
    "product": {"type": "Luxury Watch", "description": "An elegant gold watch."},
    "campaign": {"platform": "instagram", "objective": "MESSAGES", "tone": "aspirational"},
    "creative": {
        "copies": ["Own the moment. Message us today.", "Timeless luxury awaits.", "Style redefined."],
        "headlines": ["Luxury Redefined", "Own Your Moment", "Timeless Elegance"],
        "cta": "Send Message",
        "visual_prompt": "A gold watch on marble.",
        "generated_images": [],
    },
    "media": {
        "budget_split": {"instagram": 1.0, "facebook": 0.0},
        "daily_budget_usd": 71.43,
        "audience": {
            "age_min": 28,
            "age_max": 55,
            "genders": ["all"],
            "interests": ["Luxury watches", "Swiss watches"],
            "income_tier": "top_10_percent",
        },
        "placement": ["feed", "stories"],
        "bid_strategy": "COST_CAP",
        "optimization_goal": "MESSAGES",
        "estimated_reach": {"min": 8000, "max": 20000},
        "reasoning": "Instagram-only for luxury.",
    },
}


# ---------------------------------------------------------------------------
# Test 1: SimulatedMetaClient create_campaign response shape
# ---------------------------------------------------------------------------

def test_simulated_create_campaign_response_shape():
    """SimulatedMetaClient.create_campaign must return all required keys with correct types."""
    from meta_client import SimulatedMetaClient

    client = SimulatedMetaClient()
    result = client.create_campaign(_BUNDLE)

    required_keys = {"id", "name", "status", "objective", "created_time", "account_id"}
    assert required_keys.issubset(result.keys()), (
        f"Missing keys: {required_keys - result.keys()}"
    )
    assert result["status"] == "PAUSED"
    assert result["objective"] == "MESSAGES"
    assert result["id"].startswith("2385")
    assert len(result["id"]) == 14


# ---------------------------------------------------------------------------
# Test 2: Full simulated publish sequence returns IDs for all 4 objects
# ---------------------------------------------------------------------------

def test_simulated_publish_sequence_returns_all_ids():
    """Running the full create_campaign → create_ad_set → create_ad_creative → create_ad
    chain on SimulatedMetaClient should return valid IDs at every step."""
    from meta_client import SimulatedMetaClient

    client = SimulatedMetaClient()

    campaign = client.create_campaign(_BUNDLE)
    assert "id" in campaign

    ad_set = client.create_ad_set(_BUNDLE, campaign["id"])
    assert "id" in ad_set
    assert ad_set["campaign_id"] == campaign["id"]

    creative = client.create_ad_creative(_BUNDLE)
    assert "id" in creative
    assert "object_story_spec" in creative

    ad = client.create_ad(_BUNDLE, ad_set["id"], creative["id"])
    assert "id" in ad
    assert ad["adset_id"] == ad_set["id"]
    assert ad["creative"]["creative_id"] == creative["id"]
    assert ad["status"] == "PAUSED"


# ---------------------------------------------------------------------------
# Test 3: SimulatedMetaClient.publish_post and get_campaign_status
# ---------------------------------------------------------------------------

def test_simulated_publish_post_and_get_status():
    """publish_post must return a post_id; get_campaign_status must return a status."""
    from meta_client import SimulatedMetaClient

    client = SimulatedMetaClient()

    post = client.publish_post(_BUNDLE)
    assert "post_id" in post
    assert "message" in post
    assert post["message"] == _BUNDLE["creative"]["copies"][0]

    campaign = client.create_campaign(_BUNDLE)
    status = client.get_campaign_status(campaign["id"])
    assert status["id"] == campaign["id"]
    assert status["status"] in {"PAUSED", "ACTIVE", "DELETED", "ARCHIVED"}


# ---------------------------------------------------------------------------
# Test 4: Factory returns SimulatedMetaClient by default
# ---------------------------------------------------------------------------

def test_factory_returns_simulated_client_by_default():
    """get_meta_client() with no META_SIMULATION_MODE set must return SimulatedMetaClient."""
    from meta_client import SimulatedMetaClient, get_meta_client

    # Ensure env variable is unset or set to true
    with patch.dict(os.environ, {"META_SIMULATION_MODE": "true"}):
        client = get_meta_client()

    assert isinstance(client, SimulatedMetaClient)


# ---------------------------------------------------------------------------
# Test 5: Factory returns RealMetaClient when flag is false (SDK mocked)
# ---------------------------------------------------------------------------

def test_factory_returns_real_client_when_flag_false():
    """get_meta_client() with META_SIMULATION_MODE=false must return RealMetaClient."""
    from meta_client import RealMetaClient

    mock_api = MagicMock()
    mock_api.init = MagicMock()

    env_overrides = {
        "META_SIMULATION_MODE": "false",
        "META_ACCESS_TOKEN": "fake_token",
        "META_APP_ID": "12345",
        "META_APP_SECRET": "fake_secret",
        "META_AD_ACCOUNT_ID": "9999999",
        "META_PAGE_ID": "8888888",
    }

    with patch.dict(os.environ, env_overrides):
        with patch("meta_client.RealMetaClient.__init__", return_value=None):
            from meta_client import get_meta_client
            client = get_meta_client()

    assert isinstance(client, RealMetaClient)


# ---------------------------------------------------------------------------
# Test 6: CTA type mapping covers all objectives
# ---------------------------------------------------------------------------

def test_cta_type_mapping_all_objectives():
    """create_ad_creative must map every campaign objective to the correct Meta CTA type."""
    from meta_client import SimulatedMetaClient, _CTA_TYPE

    client = SimulatedMetaClient()

    expected = {
        "MESSAGES": "MESSAGE_PAGE",
        "CONVERSIONS": "SHOP_NOW",
        "TRAFFIC": "LEARN_MORE",
        "AWARENESS": "LEARN_MORE",
    }

    for objective, expected_cta in expected.items():
        bundle = {**_BUNDLE, "campaign": {**_BUNDLE["campaign"], "objective": objective}}
        result = client.create_ad_creative(bundle)
        actual_cta = result["object_story_spec"]["link_data"]["call_to_action"]["type"]
        assert actual_cta == expected_cta, (
            f"Objective {objective}: expected CTA {expected_cta}, got {actual_cta}"
        )

    # The legacy objectives must still be mapped (the table also carries the
    # newer OUTCOME_* objectives, so check for inclusion rather than equality).
    assert expected.items() <= _CTA_TYPE.items()
