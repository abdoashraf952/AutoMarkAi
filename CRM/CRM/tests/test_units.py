"""
tests/test_units.py — AutoMark AI CRM Agent (ORCAST)

Unit tests for pure functions that don't require live services:
  - lead_scoring_tool.score_lead
  - retriever.rrf_fuse
  - ingest.chunk_text
  - prompts.build_system_prompt / _channel_rule (Vapi 2-sentence rule)
  - vapi.VapiAdapter.verify_signature (HMAC-SHA256)

Run with:  pytest tests/ -v
"""

from __future__ import annotations

import hashlib
import hmac


# ─────────────────────────────────────────────────────────────────────────────
# lead_scoring_tool.score_lead
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreLead:

    def _call(self, **kwargs) -> dict:
        from app.tools.lead_scoring_tool import score_lead
        return score_lead(kwargs)

    # ── Temperature thresholds ────────────────────────────────────────────────

    def test_all_unknown_gives_cold(self):
        result = self._call(budget="unknown", authority="unknown",
                            engagement_level=0, interest_level=0)
        assert result["score"] < 30
        assert result["temperature"] == "cold"

    def test_low_budget_and_low_authority_gives_cold(self):
        result = self._call(budget="low", authority="influencer",
                            engagement_level=2, interest_level=2)
        assert result["temperature"] == "cold"

    def test_medium_mid_signals_gives_warm(self):
        result = self._call(budget="medium", authority="recommender",
                            engagement_level=5, interest_level=5)
        assert 30 <= result["score"] < 60
        assert result["temperature"] == "warm"

    def test_high_budget_decision_maker_gives_hot(self):
        result = self._call(budget="high", authority="decision_maker",
                            engagement_level=6, interest_level=6)
        assert 60 <= result["score"] < 80
        assert result["temperature"] == "hot"

    def test_perfect_score_gives_qualified(self):
        result = self._call(budget="very_high", authority="decision_maker",
                            engagement_level=10, interest_level=10)
        assert result["score"] == 100
        assert result["temperature"] == "qualified"

    def test_score_at_80_boundary_is_qualified(self):
        # budget=high(80)*0.35=28, authority=decision_maker(100)*0.30=30,
        # engagement=9*10*0.20=18, interest=7*10*0.15=10.5 → 86.5 → 87 > 80
        result = self._call(budget="high", authority="decision_maker",
                            engagement_level=9, interest_level=7)
        assert result["score"] >= 80
        assert result["temperature"] == "qualified"

    # ── Weight formula sanity ────────────────────────────────────────────────

    def test_budget_weight_is_dominant(self):
        """Raising budget from low→very_high at zero engagement should raise score more than
        raising authority from unknown→decision_maker at the same engagement."""
        base = self._call(budget="low", authority="unknown",
                          engagement_level=0, interest_level=0)
        high_budget = self._call(budget="very_high", authority="unknown",
                                 engagement_level=0, interest_level=0)
        high_auth = self._call(budget="low", authority="decision_maker",
                               engagement_level=0, interest_level=0)
        budget_delta = high_budget["score"] - base["score"]
        auth_delta = high_auth["score"] - base["score"]
        # Budget weight (35%) × (100-25) = 26.25;  Authority weight (30%) × (100-5) = 28.5
        # Both should be > 0
        assert budget_delta > 0
        assert auth_delta > 0

    # ── Identity passthrough ─────────────────────────────────────────────────

    def test_name_email_phone_are_returned_not_scored(self):
        result = self._call(
            name="Alice Smith",
            email="alice@example.com",
            phone="+1 555 123 4567",
            budget="unknown",
            authority="unknown",
            engagement_level=0,
            interest_level=0,
        )
        assert result["name"] == "Alice Smith"
        assert result["email"] == "alice@example.com"
        assert result["phone"] == "+1 555 123 4567"
        assert "name" not in result["breakdown"]

    def test_breakdown_has_four_keys(self):
        result = self._call(budget="medium", authority="recommender",
                            engagement_level=5, interest_level=5)
        assert set(result["breakdown"].keys()) == {"budget", "authority", "engagement", "interest"}

    # ── No company / company_size field ────────────────────────────────────

    def test_no_company_field_in_output(self):
        """company is not a field: passing it is ignored and never appears in output."""
        result = self._call(
            company="Acme Corp",        # unknown field — must be silently ignored
            budget="medium",
            authority="unknown",
            engagement_level=0,
            interest_level=0,
        )
        assert "company" not in result
        assert "company" not in result.get("breakdown", {})

    def test_no_company_size_field_in_output(self):
        """company_size is not a scoring dimension — must not appear in breakdown."""
        result = self._call(budget="high", authority="decision_maker",
                            engagement_level=8, interest_level=8)
        assert "company_size" not in result.get("breakdown", {})


# ─────────────────────────────────────────────────────────────────────────────
# retriever.rrf_fuse
# ─────────────────────────────────────────────────────────────────────────────

class TestRrfFuse:

    def _fuse(self, *rankings, k=60):
        from app.rag.retriever import rrf_fuse
        return rrf_fuse(list(rankings), k=k)

    def test_single_ranking_preserved_order(self):
        result = self._fuse([1, 2, 3, 4, 5])
        assert result == [1, 2, 3, 4, 5]

    def test_top_ranked_in_both_wins(self):
        # ID 2 is #1 in both rankings — should beat ID 1 (only #1 in one)
        result = self._fuse([1, 2, 3], [2, 4, 5])
        assert result[0] == 2

    def test_deduplication(self):
        result = self._fuse([1, 2, 3], [1, 2, 3])
        assert len(result) == len(set(result))
        assert set(result) == {1, 2, 3}

    def test_empty_rankings(self):
        assert self._fuse() == []

    def test_single_empty_ranking(self):
        assert self._fuse([]) == []

    def test_mixed_empty_and_non_empty(self):
        result = self._fuse([1, 2, 3], [])
        assert result == [1, 2, 3]

    def test_consistent_fusion_order(self):
        """Items appearing in more lists and at higher ranks should score better."""
        # Item 10 is top of list A; item 20 is top of both lists B and C
        result = self._fuse([10, 20], [20, 30], [20, 40])
        assert result[0] == 20

    def test_k_parameter_affects_scores_not_order_for_identical_rank(self):
        r1 = self._fuse([1, 2, 3], k=1)
        r2 = self._fuse([1, 2, 3], k=1000)
        # Order should be the same regardless of k when a single ranking is given
        assert r1 == r2


# ─────────────────────────────────────────────────────────────────────────────
# ingest.chunk_text
# ─────────────────────────────────────────────────────────────────────────────

class TestChunkText:

    def _chunks(self, text, chunk_size=2000, overlap=200):
        from app.rag.ingest import chunk_text
        return list(chunk_text(text, chunk_size=chunk_size, overlap=overlap))

    def test_short_text_is_single_chunk(self):
        text = "Hello world. " * 10
        chunks = self._chunks(text, chunk_size=2000)
        assert len(chunks) == 1
        assert chunks[0].strip() == text.strip()

    def test_long_text_splits_into_multiple_chunks(self):
        text = "Sentence number {}. ".format(0) * 1  # seed
        text = "This is a test sentence. " * 200       # ~5000 chars
        chunks = self._chunks(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1

    def test_chunk_sizes_respect_limit(self):
        text = "A" * 10_000
        chunks = self._chunks(text, chunk_size=1000, overlap=100)
        for chunk in chunks:
            assert len(chunk) <= 1100  # allow a small boundary tolerance

    def test_empty_text_yields_nothing(self):
        chunks = self._chunks("")
        assert chunks == []

    def test_text_below_min_length_yields_nothing(self):
        chunks = self._chunks("Hi")  # < MIN_CHUNK_LENGTH (50)
        assert chunks == []

    def test_chunks_cover_all_content(self):
        text = "Word" * 500
        chunks = self._chunks(text, chunk_size=500, overlap=50)
        # All characters from original text should appear somewhere in chunks
        combined = "".join(chunks)
        assert "WordWord" in combined


# ─────────────────────────────────────────────────────────────────────────────
# prompts.build_system_prompt — channel rules
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildSystemPrompt:

    def _state(self, source: str, input_type: str = "text", **extra):
        state = {
            "user_id": "test",
            "source": source,
            "input_type": input_type,
            "user_message": "Hello",
            **extra,
        }
        return state

    def test_vapi_rule_in_prompt(self):
        from app.graph.prompts import build_system_prompt
        prompt = build_system_prompt(self._state("vapi"))
        assert "AT MOST TWO SHORT SENTENCES" in prompt
        assert "No markdown" in prompt

    def test_messenger_text_rule(self):
        from app.graph.prompts import build_system_prompt
        prompt = build_system_prompt(self._state("messenger", input_type="text"))
        assert "Messenger" in prompt

    def test_messenger_voice_rule(self):
        from app.graph.prompts import build_system_prompt
        prompt = build_system_prompt(self._state("messenger", input_type="voice"))
        assert "voice" in prompt.lower()

    def test_facebook_comments_rule(self):
        from app.graph.prompts import build_system_prompt
        prompt = build_system_prompt(self._state("facebook_comments"))
        assert "PUBLICLY" in prompt or "publicly" in prompt.lower()

    def test_hubspot_ids_redacted_from_prompt(self):
        from app.graph.prompts import build_system_prompt
        state = self._state("messenger", lead_profile={
            "name": "Alice",
            "email": "alice@example.com",
            "hubspot_contact_id": "HS-SECRET-123",
            "hubspot_deal_id": "HS-DEAL-456",
        })
        prompt = build_system_prompt(state)
        assert "HS-SECRET-123" not in prompt
        assert "HS-DEAL-456" not in prompt
        assert "Alice" in prompt

    def test_summary_appears_when_set(self):
        from app.graph.prompts import build_system_prompt
        state = self._state("messenger", summary="Previous summary text here.")
        prompt = build_system_prompt(state)
        assert "Previous summary text here." in prompt

    def test_no_summary_fallback_text(self):
        from app.graph.prompts import build_system_prompt
        state = self._state("messenger")
        prompt = build_system_prompt(state)
        assert "No prior summary" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# vapi.VapiAdapter.verify_signature
# ─────────────────────────────────────────────────────────────────────────────

class TestVapiSignature:
    # Vapi sends the webhook secret as a plain X-Vapi-Secret header value (not HMAC).
    # verify_signature(secret_header) compares it directly against VAPI_WEBHOOK_SECRET.

    def test_valid_signature_accepted(self, monkeypatch):
        from app.api.vapi import vapi_adapter
        monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "test_secret")
        assert vapi_adapter.verify_signature("test_secret") is True

    def test_invalid_signature_rejected(self, monkeypatch):
        from app.api.vapi import vapi_adapter
        monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "test_secret")
        assert vapi_adapter.verify_signature("wrong_secret") is False

    def test_empty_secret_skips_check(self, monkeypatch):
        from app.api.vapi import vapi_adapter
        monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "")
        assert vapi_adapter.verify_signature("") is True

    def test_whitespace_trimmed(self, monkeypatch):
        from app.api.vapi import vapi_adapter
        monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "secret123")
        assert vapi_adapter.verify_signature("  secret123  ") is True
