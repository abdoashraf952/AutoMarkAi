"""Policy thresholds — the playbook as a typed policy engine (Phase 4).

Every number here is a named discipline, not magic. The Lifecycle /
Decision agent reads these constants and produces a structured decision
with a rationale; the numbers themselves can be tuned per-market without
touching decision logic.

All monetary values are in USD (the Meta API currency for the account).
All time-based thresholds assume daily diagnosis after attribution settles
(typically T+24h for lead events in Egypt).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LeadGenThresholds:
    """Performance thresholds for a real estate lead-generation campaign."""

    # ── Learning phase ─────────────────────────────────────────────────
    # Meta needs ~50 optimisation events before it exits learning.
    # Act on NOTHING during the learning phase — it resets the counter.
    learning_event_target: int = 50          # events needed to exit learning
    learning_max_days: int = 7               # diagnose-only until this day
    learning_max_spend_usd: float = 100.0    # safety cap during learning

    # ── Cost per lead benchmarks (USD) ────────────────────────────────
    # Egyptian real estate: CPL varies widely by price tier and season.
    # These are median benchmarks; tier-specific overrides in get_tier_thresholds().
    cpl_target_usd: float = 8.0              # ideal CPL
    cpl_acceptable_usd: float = 15.0         # still within budget model
    cpl_high_usd: float = 25.0              # investigate / reduce spend
    cpl_pause_usd: float = 40.0             # pause if sustained this long

    # ── Lead quality ──────────────────────────────────────────────────
    # qualified_rate = leads that answer call / engage meaningfully.
    qualified_rate_target: float = 0.30     # 30% of leads qualify
    qualified_rate_low: float = 0.15        # below → creative or audience problem
    qualified_rate_pause: float = 0.08      # below → pause, audit, restart

    # ── Frequency / fatigue ───────────────────────────────────────────
    frequency_warning: float = 3.0          # same person saw ad 3× → consider refresh
    frequency_critical: float = 5.0         # creative fatigue; must refresh

    # ── Budget scaling ────────────────────────────────────────────────
    scale_up_pct: float = 0.25              # scale spend by 25% when beating target
    scale_down_pct: float = 0.20            # reduce spend by 20% when over cpl_high
    min_days_before_scale: int = 3          # never scale in first 3 days
    scale_cooldown_days: int = 2            # wait 2 days between scale actions

    # ── Advantage+ thresholds ─────────────────────────────────────────
    # If Advantage+ fails to exit learning within this window, take the hand.
    advantage_plus_learning_days: int = 7
    # If CPL on Advantage+ is worse than manual baseline, switch to manual.
    advantage_plus_cpl_ratio: float = 1.3  # 30% worse than target → take hand


def get_tier_thresholds(price_tier: str) -> LeadGenThresholds:
    """Return price-tier-adjusted thresholds.

    Luxury leads cost more and convert slower; affordable leads should be
    high-volume and cheap. Tier defaults override the base values.
    """
    overrides: dict = {}

    if price_tier == "affordable":
        overrides = {"cpl_target_usd": 5.0, "cpl_acceptable_usd": 10.0,
                     "cpl_high_usd": 18.0, "cpl_pause_usd": 30.0,
                     "qualified_rate_target": 0.25}
    elif price_tier == "mid_range":
        overrides = {"cpl_target_usd": 8.0, "cpl_acceptable_usd": 16.0,
                     "cpl_high_usd": 28.0, "cpl_pause_usd": 45.0,
                     "qualified_rate_target": 0.30}
    elif price_tier == "premium":
        overrides = {"cpl_target_usd": 15.0, "cpl_acceptable_usd": 30.0,
                     "cpl_high_usd": 50.0, "cpl_pause_usd": 80.0,
                     "qualified_rate_target": 0.35}
    elif price_tier == "luxury":
        overrides = {"cpl_target_usd": 25.0, "cpl_acceptable_usd": 50.0,
                     "cpl_high_usd": 80.0, "cpl_pause_usd": 120.0,
                     "qualified_rate_target": 0.40,
                     "scale_up_pct": 0.20}

    # dataclass is frozen — create a new one with field overrides
    base = LeadGenThresholds()
    if not overrides:
        return base
    import dataclasses
    return dataclasses.replace(base, **overrides)


# ── Decision labels (typed constants for the decision log) ─────────────

class OperateDecision:
    KEEP = "keep"               # performing well — no action
    SCALE_UP = "scale_up"       # beat CPL target → increase budget 25%
    SCALE_DOWN = "scale_down"   # over acceptable CPL → reduce budget 20%
    PAUSE = "pause"             # sustained poor CPL or quality → pause
    TAKE_HAND = "take_hand"     # Advantage+ failing → switch to manual
    HAND_BACK = "hand_back"     # manual recovered → offer Advantage+ again
    REFRESH_CREATIVE = "refresh_creative"  # frequency fatigue
    HOLD = "hold"               # learning phase — observe only


# ── Learning state labels ──────────────────────────────────────────────

class LearningState:
    LEARNING = "learning"
    EXITED = "exited"
    UNSTABLE = "unstable"       # exits learning then regresses
