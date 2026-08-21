"""
Unit tests for app/tools/lead_scoring_tool.py

All tests are pure (no I/O, no LLM calls, no database) — the scoring
function is deterministic and fully testable in isolation.
"""
import pytest

from src.crm.tools.lead_scoring_tool import (
    AUTHORITY_SCORES,
    BUDGET_SCORES,
    W_AUTHORITY,
    W_BUDGET,
    W_ENGAGEMENT,
    W_INTEREST,
    interpret,
    score_lead,
)


# ─────────────────────────────────────────────────────────────────────────────
# Score table values (per README specification)
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreTables:
    """Verify lookup tables match the README documentation exactly."""

    def test_budget_unknown(self):
        assert BUDGET_SCORES["unknown"] == 0

    def test_budget_low(self):
        assert BUDGET_SCORES["low"] == 25

    def test_budget_medium(self):
        assert BUDGET_SCORES["medium"] == 50

    def test_budget_high(self):
        assert BUDGET_SCORES["high"] == 75

    def test_budget_very_high(self):
        assert BUDGET_SCORES["very_high"] == 100

    def test_authority_unknown(self):
        assert AUTHORITY_SCORES["unknown"] == 0

    def test_authority_influencer(self):
        assert AUTHORITY_SCORES["influencer"] == 33

    def test_authority_recommender(self):
        assert AUTHORITY_SCORES["recommender"] == 66

    def test_authority_decision_maker(self):
        assert AUTHORITY_SCORES["decision_maker"] == 100

    def test_weights_sum_to_one(self):
        total = W_BUDGET + W_AUTHORITY + W_ENGAGEMENT + W_INTEREST
        assert abs(total - 1.0) < 1e-9

    def test_weight_values(self):
        assert W_BUDGET == pytest.approx(0.35)
        assert W_AUTHORITY == pytest.approx(0.30)
        assert W_ENGAGEMENT == pytest.approx(0.20)
        assert W_INTEREST == pytest.approx(0.15)


# ─────────────────────────────────────────────────────────────────────────────
# Temperature thresholds (per README specification)
# ─────────────────────────────────────────────────────────────────────────────

class TestTemperatureThresholds:
    """Boundary tests for the four temperature bands."""

    def test_score_0_is_cold(self):
        r = score_lead({"budget": "unknown", "authority": "unknown", "engagement_level": 0, "interest_level": 0})
        assert r["score"] == 0
        assert r["temperature"] == "cold"

    def test_score_29_is_cold(self):
        # engagement=2, interest=2 → 20*0.20 + 20*0.15 = 4+3 = 7 → cold
        r = score_lead({"engagement_level": 2, "interest_level": 2})
        assert r["temperature"] == "cold"

    def test_score_30_is_warm(self):
        # low budget (25*0.35=8.75) + influencer (33*0.30=9.9) + engagement 4 (40*0.20=8) + interest 3 (30*0.15=4.5) = 31.15 ≈ 31
        r = score_lead({"budget": "low", "authority": "influencer", "engagement_level": 4, "interest_level": 3})
        assert r["temperature"] == "warm"
        assert r["score"] >= 30

    def test_score_60_is_hot(self):
        # medium (50*0.35=17.5) + recommender (66*0.30=19.8) + engagement 6 (60*0.20=12) + interest 6 (60*0.15=9) = 58.3 → warm
        # high (75*0.35=26.25) + recommender (66*0.30=19.8) + engagement 4 (40*0.20=8) + interest 4 (40*0.15=6) = 60.05 ≈ 60
        r = score_lead({"budget": "high", "authority": "recommender", "engagement_level": 4, "interest_level": 4})
        assert r["temperature"] == "hot"
        assert 60 <= r["score"] <= 79

    def test_score_80_is_qualified(self):
        # very_high (100*0.35=35) + decision_maker (100*0.30=30) + engagement 8 (80*0.20=16) + interest 0 (0) = 81
        r = score_lead({"budget": "very_high", "authority": "decision_maker", "engagement_level": 8, "interest_level": 0})
        assert r["score"] >= 80
        assert r["temperature"] == "qualified"

    def test_perfect_score_is_qualified(self):
        r = score_lead({"budget": "very_high", "authority": "decision_maker", "engagement_level": 10, "interest_level": 10})
        assert r["score"] == 100
        assert r["temperature"] == "qualified"


# ─────────────────────────────────────────────────────────────────────────────
# Formula correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestFormula:
    """Verify the weighted sum formula produces correct results."""

    def test_high_decision_maker_baseline(self):
        # high (75*0.35) + decision_maker (100*0.30) + 0 + 0 = 26.25 + 30 = 56.25 ≈ 56
        r = score_lead({"budget": "high", "authority": "decision_maker"})
        assert r["score"] == 56
        assert r["temperature"] == "warm"

    def test_medium_recommender_mid_engagement(self):
        # medium (50*0.35=17.5) + recommender (66*0.30=19.8) + eng5 (50*0.20=10) + int5 (50*0.15=7.5) = 54.8 ≈ 55
        r = score_lead({"budget": "medium", "authority": "recommender", "engagement_level": 5, "interest_level": 5})
        assert r["score"] == 55
        assert r["temperature"] == "warm"

    def test_very_high_decision_full_engagement(self):
        # 100*0.35 + 100*0.30 + 100*0.20 + 100*0.15 = 35+30+20+15 = 100
        r = score_lead({"budget": "very_high", "authority": "decision_maker", "engagement_level": 10, "interest_level": 10})
        assert r["score"] == 100

    def test_score_is_int(self):
        r = score_lead({"budget": "medium", "authority": "recommender"})
        assert isinstance(r["score"], int)

    def test_breakdown_keys(self):
        r = score_lead({"budget": "high", "authority": "influencer", "engagement_level": 3, "interest_level": 4})
        bd = r["breakdown"]
        assert set(bd.keys()) == {"budget", "authority", "engagement", "interest"}

    def test_breakdown_contributions_sum_to_score(self):
        r = score_lead({"budget": "medium", "authority": "recommender", "engagement_level": 5, "interest_level": 5})
        total = sum(r["breakdown"][k]["contribution"] for k in r["breakdown"])
        assert abs(total - r["score"]) <= 1  # rounding tolerance of 1 point


# ─────────────────────────────────────────────────────────────────────────────
# Identity field passthrough
# ─────────────────────────────────────────────────────────────────────────────

class TestIdentityFields:
    def test_name_passthrough(self):
        r = score_lead({"name": "Alice Smith", "budget": "high"})
        assert r["name"] == "Alice Smith"

    def test_email_passthrough(self):
        r = score_lead({"email": "alice@example.com", "budget": "medium"})
        assert r["email"] == "alice@example.com"

    def test_phone_passthrough_valid(self):
        r = score_lead({"phone": "+1 800 555 0100", "budget": "low"})
        assert r["phone"] == "+1 800 555 0100"

    def test_phone_invalid_raises(self):
        with pytest.raises(Exception):
            score_lead({"phone": "not-a-phone"})

    def test_none_identity_fields(self):
        r = score_lead({})
        assert r["name"] is None
        assert r["email"] is None
        assert r["phone"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Clamp / normalisation
# ─────────────────────────────────────────────────────────────────────────────

class TestClamping:
    def test_engagement_max_10_accepted(self):
        r = score_lead({"engagement_level": 10})
        assert r["score"] >= 0

    def test_engagement_above_10_rejected(self):
        with pytest.raises(Exception):
            score_lead({"engagement_level": 11})

    def test_interest_max_10_accepted(self):
        r = score_lead({"interest_level": 10})
        assert r["score"] >= 0

    def test_interest_above_10_rejected(self):
        with pytest.raises(Exception):
            score_lead({"interest_level": 11})

    def test_engagement_below_0_rejected(self):
        with pytest.raises(Exception):
            score_lead({"engagement_level": -1})

    def test_unknown_budget_defaults(self):
        r = score_lead({})
        # budget="unknown" (0), authority="unknown" (0) → score=0
        assert r["score"] == 0

    def test_unknown_budget_string_defaults(self):
        r = score_lead({"budget": "unknown", "authority": "unknown", "engagement_level": 0, "interest_level": 0})
        assert r["score"] == 0

    def test_engagement_zero_gives_zero_contribution(self):
        r_zero = score_lead({"budget": "unknown", "authority": "unknown", "engagement_level": 0, "interest_level": 0})
        r_five = score_lead({"budget": "unknown", "authority": "unknown", "engagement_level": 5, "interest_level": 0})
        assert r_five["score"] > r_zero["score"]


# ─────────────────────────────────────────────────────────────────────────────
# interpret() helper
# ─────────────────────────────────────────────────────────────────────────────

class TestInterpret:
    def test_cold_message(self):
        msg = interpret(0)
        assert "Cold" in msg
        assert "0" in msg

    def test_warm_message(self):
        msg = interpret(45)
        assert "Warm" in msg
        assert "45" in msg

    def test_hot_message(self):
        msg = interpret(70)
        assert "Hot" in msg
        assert "70" in msg

    def test_qualified_message(self):
        msg = interpret(95)
        assert "Qualified" in msg or "qualified" in msg.lower()
        assert "95" in msg

    def test_boundary_29_cold(self):
        assert "Cold" in interpret(29)

    def test_boundary_30_warm(self):
        assert "Warm" in interpret(30)

    def test_boundary_59_warm(self):
        assert "Warm" in interpret(59)

    def test_boundary_60_hot(self):
        assert "Hot" in interpret(60)

    def test_boundary_79_hot(self):
        assert "Hot" in interpret(79)

    def test_boundary_80_qualified(self):
        msg = interpret(80)
        assert "qualified" in msg.lower()
