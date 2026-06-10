"""
Meta Marketing API client with simulation and real implementations.

Usage:
    from meta_client import get_meta_client
    client = get_meta_client()          # reads META_SIMULATION_MODE from .env
    result = client.create_campaign(bundle)

Set META_SIMULATION_MODE=true  → SimulatedMetaClient (safe for dev/demo, no credentials needed)
Set META_SIMULATION_MODE=false → RealMetaClient      (hits live Meta Marketing API)

All code that uses this module calls MetaClient methods only — it never knows
which implementation is running.
"""

import logging
import os
import random
import string
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Meta CTA type mapping: campaign objective → Meta API CTA type string
_CTA_TYPE: dict[str, str] = {
    "MESSAGES": "MESSAGE_PAGE",
    "CONVERSIONS": "SHOP_NOW",
    "TRAFFIC": "LEARN_MORE",
    "AWARENESS": "LEARN_MORE",
}


def _meta_id() -> str:
    """Generate a realistic-looking Meta object ID (14-digit string prefixed with 2385)."""
    return "2385" + "".join(random.choices(string.digits, k=10))


def _meta_now() -> str:
    """Return current UTC time in Meta's API timestamp format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")


# ---------------------------------------------------------------------------
# Abstract base class — the only interface callers use
# ---------------------------------------------------------------------------

class MetaClient(ABC):
    """Abstract base class defining the Meta Marketing API interface."""

    @abstractmethod
    def create_campaign(self, bundle: dict) -> dict:
        """
        Create a Meta ad campaign from a campaign_bundle.

        Args:
            bundle: The campaign_bundle dict produced by merge_node.

        Returns:
            Dict mirroring the Meta API Campaign object:
            {id, name, status, objective, created_time, account_id}
        """

    @abstractmethod
    def create_ad_set(self, bundle: dict, campaign_id: str) -> dict:
        """
        Create an ad set under an existing campaign.

        Args:
            bundle:      The campaign_bundle dict.
            campaign_id: ID returned by create_campaign.

        Returns:
            Dict mirroring the Meta API AdSet object:
            {id, name, status, campaign_id, daily_budget, optimization_goal,
             targeting, billing_event, created_time}
        """

    @abstractmethod
    def create_ad_creative(self, bundle: dict) -> dict:
        """
        Create an ad creative (the visual + copy asset).

        Args:
            bundle: The campaign_bundle dict.

        Returns:
            Dict mirroring the Meta API AdCreative object:
            {id, name, status, object_story_spec}
        """

    @abstractmethod
    def create_ad(self, bundle: dict, ad_set_id: str, creative_id: str) -> dict:
        """
        Create an ad combining an ad set with a creative.

        Args:
            bundle:      The campaign_bundle dict.
            ad_set_id:   ID returned by create_ad_set.
            creative_id: ID returned by create_ad_creative.

        Returns:
            Dict mirroring the Meta API Ad object:
            {id, name, status, adset_id, creative, created_time}
        """

    @abstractmethod
    def publish_post(self, bundle: dict) -> dict:
        """
        Publish an organic post to the Meta Page.

        Args:
            bundle: The campaign_bundle dict.

        Returns:
            Dict mirroring the Meta API Page Post object:
            {id, post_id, message, created_time}
        """

    @abstractmethod
    def get_campaign_status(self, campaign_id: str) -> dict:
        """
        Retrieve the current status of a campaign.

        Args:
            campaign_id: The Meta campaign ID.

        Returns:
            Dict mirroring the Meta API Campaign object with status fields:
            {id, name, status, objective, created_time, account_id}
        """


# ---------------------------------------------------------------------------
# Simulated implementation — no API calls, realistic fake responses
# ---------------------------------------------------------------------------

class SimulatedMetaClient(MetaClient):
    """
    Returns realistic fake Meta API responses.

    ID format matches real Meta IDs (14-digit numeric strings).
    Status fields match real Meta defaults for new campaigns (PAUSED).
    Timestamps are in Meta's format: "2026-06-10T10:00:00+0000".
    """

    def __init__(self) -> None:
        self._account_id = os.getenv("META_AD_ACCOUNT_ID", "simulated_account")
        self._page_id = os.getenv("META_PAGE_ID", "simulated_page")
        logger.info("MetaClient: simulation mode active")

    def create_campaign(self, bundle: dict) -> dict:
        campaign = bundle.get("campaign", {})
        product = bundle.get("product", {})
        name = (
            f"AutoMark — {product.get('type', 'Product')} — "
            f"{campaign.get('objective', 'MESSAGES')}"
        )
        result = {
            "id": _meta_id(),
            "name": name,
            "status": "PAUSED",
            "objective": campaign.get("objective", "MESSAGES"),
            "created_time": _meta_now(),
            "account_id": f"act_{self._account_id}",
        }
        logger.info("SimulatedMetaClient.create_campaign → id=%s", result["id"])
        return result

    def create_ad_set(self, bundle: dict, campaign_id: str) -> dict:
        media = bundle.get("media", {})
        campaign = bundle.get("campaign", {})
        audience = media.get("audience", {})
        daily_budget_cents = int(media.get("daily_budget_usd", 0) * 100)
        result = {
            "id": _meta_id(),
            "name": f"Ad Set — {campaign.get('platform', 'instagram').title()}",
            "status": "PAUSED",
            "campaign_id": campaign_id,
            "daily_budget": str(daily_budget_cents),
            "optimization_goal": media.get("optimization_goal", "MESSAGES"),
            "billing_event": "IMPRESSIONS",
            "targeting": {
                "age_min": audience.get("age_min", 18),
                "age_max": audience.get("age_max", 65),
                "genders": audience.get("genders", ["all"]),
                "interests": [
                    {"id": _meta_id(), "name": interest}
                    for interest in audience.get("interests", [])
                ],
            },
            "created_time": _meta_now(),
        }
        logger.info("SimulatedMetaClient.create_ad_set → id=%s", result["id"])
        return result

    def create_ad_creative(self, bundle: dict) -> dict:
        creative = bundle.get("creative", {})
        campaign = bundle.get("campaign", {})
        copies = creative.get("copies", [""])
        headlines = creative.get("headlines", [""])
        objective = campaign.get("objective", "MESSAGES").upper()
        cta_type = _CTA_TYPE.get(objective, "LEARN_MORE")
        result = {
            "id": _meta_id(),
            "name": f"Creative — {headlines[0][:40] if headlines else 'Ad Creative'}",
            "status": "ACTIVE",
            "object_story_spec": {
                "page_id": self._page_id,
                "link_data": {
                    "message": copies[0] if copies else "",
                    "name": headlines[0] if headlines else "",
                    "call_to_action": {"type": cta_type},
                },
            },
        }
        logger.info("SimulatedMetaClient.create_ad_creative → id=%s", result["id"])
        return result

    def create_ad(self, bundle: dict, ad_set_id: str, creative_id: str) -> dict:
        creative = bundle.get("creative", {})
        headlines = creative.get("headlines", ["Ad"])
        result = {
            "id": _meta_id(),
            "name": f"Ad — {headlines[0][:40] if headlines else 'Ad'}",
            "status": "PAUSED",
            "adset_id": ad_set_id,
            "creative": {"creative_id": creative_id},
            "created_time": _meta_now(),
        }
        logger.info("SimulatedMetaClient.create_ad → id=%s", result["id"])
        return result

    def publish_post(self, bundle: dict) -> dict:
        creative = bundle.get("creative", {})
        copies = creative.get("copies", [""])
        page_post_id = f"{self._page_id}_{_meta_id()}"
        result = {
            "id": page_post_id,
            "post_id": page_post_id,
            "message": copies[0] if copies else "",
            "created_time": _meta_now(),
        }
        logger.info("SimulatedMetaClient.publish_post → id=%s", result["id"])
        return result

    def get_campaign_status(self, campaign_id: str) -> dict:
        result = {
            "id": campaign_id,
            "name": "AutoMark Campaign",
            "status": "PAUSED",
            "objective": "MESSAGES",
            "created_time": _meta_now(),
            "account_id": f"act_{self._account_id}",
        }
        logger.info("SimulatedMetaClient.get_campaign_status → status=%s", result["status"])
        return result


# ---------------------------------------------------------------------------
# Real implementation — uses facebook-business SDK
# ---------------------------------------------------------------------------

class RealMetaClient(MetaClient):
    """
    Calls the real Meta Marketing API using the facebook-business Python SDK.

    Required .env keys:
        META_ACCESS_TOKEN   — user or system access token
        META_APP_ID         — app ID from Meta developer console
        META_APP_SECRET     — app secret from Meta developer console
        META_AD_ACCOUNT_ID  — numeric ad account ID (without "act_" prefix)
        META_PAGE_ID        — Facebook Page ID for organic posts and ad creatives
    """

    def __init__(self) -> None:
        try:
            from facebook_business.api import FacebookAdsApi
        except ImportError as exc:
            raise RuntimeError(
                "facebook-business is not installed. "
                "Run: pip install facebook-business>=3.0.0"
            ) from exc

        self._access_token = os.getenv("META_ACCESS_TOKEN", "")
        self._app_id = os.getenv("META_APP_ID", "")
        self._app_secret = os.getenv("META_APP_SECRET", "")
        self._ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
        self._page_id = os.getenv("META_PAGE_ID", "")

        for name, val in [
            ("META_ACCESS_TOKEN", self._access_token),
            ("META_AD_ACCOUNT_ID", self._ad_account_id),
            ("META_PAGE_ID", self._page_id),
        ]:
            if not val or val.startswith("your_"):
                raise RuntimeError(
                    f"{name} is not set in .env. "
                    "Set META_SIMULATION_MODE=true to use simulation mode."
                )

        FacebookAdsApi.init(self._app_id, self._app_secret, self._access_token)
        logger.info("MetaClient: real mode active — ad_account=%s", self._ad_account_id)

    def _account(self):
        from facebook_business.adobjects.adaccount import AdAccount
        return AdAccount(f"act_{self._ad_account_id}")

    def create_campaign(self, bundle: dict) -> dict:
        from facebook_business.adobjects.campaign import Campaign

        campaign_data = bundle.get("campaign", {})
        product = bundle.get("product", {})
        objective = campaign_data.get("objective", "MESSAGES")
        name = (
            f"AutoMark — {product.get('type', 'Product')} — {objective}"
        )
        params = {
            Campaign.Field.name: name,
            Campaign.Field.objective: objective,
            Campaign.Field.status: Campaign.Status.paused,
            Campaign.Field.special_ad_categories: [],
        }
        result = self._account().create_campaign(params=params)
        return {
            "id": result["id"],
            "name": result.get("name", name),
            "status": result.get("status", "PAUSED"),
            "objective": objective,
            "created_time": result.get("created_time", _meta_now()),
            "account_id": f"act_{self._ad_account_id}",
        }

    def create_ad_set(self, bundle: dict, campaign_id: str) -> dict:
        from facebook_business.adobjects.adset import AdSet

        media = bundle.get("media", {})
        campaign_data = bundle.get("campaign", {})
        audience = media.get("audience", {})
        daily_budget_cents = int(media.get("daily_budget_usd", 10) * 100)
        optimization_goal = media.get("optimization_goal", "MESSAGES")
        name = f"Ad Set — {campaign_data.get('platform', 'instagram').title()}"

        interests = [
            {"id": interest, "name": interest}
            for interest in audience.get("interests", [])
        ]
        targeting = {
            "age_min": audience.get("age_min", 18),
            "age_max": audience.get("age_max", 65),
            "interests": interests,
        }
        params = {
            AdSet.Field.name: name,
            AdSet.Field.campaign_id: campaign_id,
            AdSet.Field.daily_budget: daily_budget_cents,
            AdSet.Field.optimization_goal: optimization_goal,
            AdSet.Field.billing_event: AdSet.BillingEvent.impressions,
            AdSet.Field.targeting: targeting,
            AdSet.Field.status: AdSet.Status.paused,
        }
        result = self._account().create_ad_set(params=params)
        return {
            "id": result["id"],
            "name": result.get("name", name),
            "status": result.get("status", "PAUSED"),
            "campaign_id": campaign_id,
            "daily_budget": str(daily_budget_cents),
            "optimization_goal": optimization_goal,
            "billing_event": "IMPRESSIONS",
            "targeting": targeting,
            "created_time": result.get("created_time", _meta_now()),
        }

    def create_ad_creative(self, bundle: dict) -> dict:
        from facebook_business.adobjects.adcreative import AdCreative

        creative_data = bundle.get("creative", {})
        campaign_data = bundle.get("campaign", {})
        copies = creative_data.get("copies", [""])
        headlines = creative_data.get("headlines", [""])
        objective = campaign_data.get("objective", "MESSAGES").upper()
        cta_type = _CTA_TYPE.get(objective, "LEARN_MORE")
        name = f"Creative — {headlines[0][:40] if headlines else 'Ad Creative'}"

        object_story_spec = {
            "page_id": self._page_id,
            "link_data": {
                "message": copies[0] if copies else "",
                "name": headlines[0] if headlines else "",
                "call_to_action": {"type": cta_type},
            },
        }
        params = {
            AdCreative.Field.name: name,
            AdCreative.Field.object_story_spec: object_story_spec,
        }
        result = self._account().create_ad_creative(params=params)
        return {
            "id": result["id"],
            "name": result.get("name", name),
            "status": result.get("status", "ACTIVE"),
            "object_story_spec": object_story_spec,
        }

    def create_ad(self, bundle: dict, ad_set_id: str, creative_id: str) -> dict:
        from facebook_business.adobjects.ad import Ad

        creative_data = bundle.get("creative", {})
        headlines = creative_data.get("headlines", ["Ad"])
        name = f"Ad — {headlines[0][:40] if headlines else 'Ad'}"

        params = {
            Ad.Field.name: name,
            Ad.Field.adset_id: ad_set_id,
            Ad.Field.creative: {"creative_id": creative_id},
            Ad.Field.status: Ad.Status.paused,
        }
        result = self._account().create_ad(params=params)
        return {
            "id": result["id"],
            "name": result.get("name", name),
            "status": result.get("status", "PAUSED"),
            "adset_id": ad_set_id,
            "creative": {"creative_id": creative_id},
            "created_time": result.get("created_time", _meta_now()),
        }

    def publish_post(self, bundle: dict) -> dict:
        from facebook_business.adobjects.page import Page

        creative_data = bundle.get("creative", {})
        copies = creative_data.get("copies", [""])
        message = copies[0] if copies else ""

        page = Page(self._page_id)
        result = page.create_feed(params={"message": message})
        post_id = result.get("id", f"{self._page_id}_{_meta_id()}")
        return {
            "id": post_id,
            "post_id": post_id,
            "message": message,
            "created_time": _meta_now(),
        }

    def get_campaign_status(self, campaign_id: str) -> dict:
        from facebook_business.adobjects.campaign import Campaign

        campaign = Campaign(campaign_id)
        result = campaign.api_get(fields=[
            Campaign.Field.name,
            Campaign.Field.status,
            Campaign.Field.objective,
            Campaign.Field.created_time,
            Campaign.Field.account_id,
        ])
        return {
            "id": campaign_id,
            "name": result.get("name", ""),
            "status": result.get("status", "UNKNOWN"),
            "objective": result.get("objective", ""),
            "created_time": result.get("created_time", _meta_now()),
            "account_id": result.get("account_id", f"act_{self._ad_account_id}"),
        }


# ---------------------------------------------------------------------------
# Factory function — the only entry point callers should use
# ---------------------------------------------------------------------------

def get_meta_client() -> MetaClient:
    """
    Return the active MetaClient based on META_SIMULATION_MODE in .env.

    META_SIMULATION_MODE=true  (default) → SimulatedMetaClient
    META_SIMULATION_MODE=false           → RealMetaClient
    """
    simulation_mode = os.getenv("META_SIMULATION_MODE", "true").strip().lower()
    if simulation_mode == "true":
        return SimulatedMetaClient()
    return RealMetaClient()
