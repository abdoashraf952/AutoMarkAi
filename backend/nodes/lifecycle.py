"""Lifecycle squad — Phase 4: Operate loop.

Three sequential nodes invoked when campaign_phase == "operate":

  diagnose_node   Read metric snapshots; compute CPL + qualified-lead rate;
                  determine learning_state; build plain-language summary.
                  Never calls Meta in this node (checkpoint-safe).

  decision_node   Pure function: (metrics, policy, learning_state) →
                  OperateDecision + rationale. Interrupts in Full Manual mode
                  to ask approval before any money-moving action.

  act_node        Execute the approved decision via meta_client (sim or live).
                  Writes the outcome to decisions_log.

All three are checkpoint-safe: the costly operations (Meta API calls) are
confined to act_node and never sit inside an interrupting node.

In META_SIMULATION_MODE=true, act_node generates synthetic metrics so
the whole operate loop can be demoed without live spend.
"""

import logging
import os
import random
from datetime import datetime, timezone

from langgraph.types import interrupt

from AutoMarkAi.backend.policy.thresholds import (
    LearningState,
    OperateDecision,
    get_tier_thresholds,
)

logger = logging.getLogger(__name__)

_SIM_MODE = os.getenv("META_SIMULATION_MODE", "true").lower() == "true"


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _synthetic_metrics(existing_snapshots: list, spend_usd: float) -> dict:
    """Generate one realistic synthetic metric snapshot for simulation mode."""
    n = len(existing_snapshots)
    base_cpl = max(5.0, 20.0 - n * 1.5 + random.uniform(-3, 3))
    base_qual = min(0.5, 0.10 + n * 0.03 + random.uniform(-0.05, 0.05))
    freq = min(6.0, 1.0 + n * 0.4)
    leads = max(0, int(spend_usd / base_cpl))
    qualified = int(leads * base_qual)
    return {
        "ts": _now_iso(),
        "cpl": round(base_cpl, 2),
        "qualified_rate": round(base_qual, 3),
        "frequency": round(freq, 2),
        "leads": leads,
        "qualified_leads": qualified,
        "reach": int(leads * random.uniform(8, 15)),
        "spend_usd": round(spend_usd, 2),
        "simulated": True,
    }


def _determine_learning_state(snapshots: list, thresholds) -> str:
    """Infer learning state from snapshot history."""
    if not snapshots:
        return LearningState.LEARNING

    total_events = sum(s.get("leads", 0) for s in snapshots)
    n_days = len(snapshots)

    if total_events >= thresholds.learning_event_target:
        recent = snapshots[-3:] if len(snapshots) >= 3 else snapshots
        recent_cpls = [s["cpl"] for s in recent if "cpl" in s]
        if recent_cpls:
            variance = max(recent_cpls) - min(recent_cpls)
            if variance > thresholds.cpl_target_usd * 1.5:
                return LearningState.UNSTABLE
        return LearningState.EXITED

    if n_days >= thresholds.learning_max_days:
        return LearningState.UNSTABLE  # never exited in time

    return LearningState.LEARNING


def _make_decision(latest: dict, thresholds, learning_state: str, control_mode: str,
                   n_snapshots: int, days_since_last_scale: int) -> tuple[str, str]:
    """Return (decision, rationale). Pure function — no side effects."""
    cpl = latest.get("cpl", 999)
    qual = latest.get("qualified_rate", 0)
    freq = latest.get("frequency", 0)

    # ── Learning guard: never act during learning ──────────────────────
    if learning_state == LearningState.LEARNING:
        return (
            OperateDecision.HOLD,
            f"Ad set still in learning phase ({learning_state}). "
            f"Observing only — no changes to avoid resetting the counter.",
        )

    # ── Frequency / creative fatigue ──────────────────────────────────
    if freq >= thresholds.frequency_critical:
        return (
            OperateDecision.REFRESH_CREATIVE,
            f"Creative fatigue: frequency={freq:.1f} exceeds critical threshold "
            f"{thresholds.frequency_critical}. Must refresh ad creative.",
        )

    # ── Pause conditions ──────────────────────────────────────────────
    if cpl >= thresholds.cpl_pause_usd or qual <= thresholds.qualified_rate_pause:
        reason = (
            f"CPL ${cpl:.2f} ≥ pause threshold ${thresholds.cpl_pause_usd:.2f}"
            if cpl >= thresholds.cpl_pause_usd
            else f"Qualified-lead rate {qual:.0%} ≤ pause threshold {thresholds.qualified_rate_pause:.0%}"
        )
        return OperateDecision.PAUSE, f"Pausing campaign: {reason}. Audit creative and audience."

    # ── Advantage+ hand decision ──────────────────────────────────────
    if control_mode == "advantage_plus" and cpl > thresholds.cpl_target_usd * thresholds.advantage_plus_cpl_ratio:
        return (
            OperateDecision.TAKE_HAND,
            f"Advantage+ CPL ${cpl:.2f} is {cpl/thresholds.cpl_target_usd:.1f}× target "
            f"${thresholds.cpl_target_usd:.2f}. Taking manual control: switching to "
            "geo-radius ad sets with manual optimization.",
        )

    # ── Scale up ──────────────────────────────────────────────────────
    cool_ok = days_since_last_scale >= thresholds.scale_cooldown_days
    been_enough_days = n_snapshots >= thresholds.min_days_before_scale
    if (cpl <= thresholds.cpl_target_usd and qual >= thresholds.qualified_rate_target
            and cool_ok and been_enough_days):
        return (
            OperateDecision.SCALE_UP,
            f"CPL ${cpl:.2f} beats target ${thresholds.cpl_target_usd:.2f} and "
            f"qualified-lead rate {qual:.0%} meets target {thresholds.qualified_rate_target:.0%}. "
            f"Scaling budget +{thresholds.scale_up_pct:.0%}.",
        )

    # ── Scale down ────────────────────────────────────────────────────
    if cpl >= thresholds.cpl_high_usd and cool_ok:
        return (
            OperateDecision.SCALE_DOWN,
            f"CPL ${cpl:.2f} ≥ high threshold ${thresholds.cpl_high_usd:.2f}. "
            f"Reducing budget -{thresholds.scale_down_pct:.0%} to control cost.",
        )

    # ── Default: keep ────────────────────────────────────────────────
    return (
        OperateDecision.KEEP,
        f"Performance within acceptable range: CPL ${cpl:.2f}, "
        f"qualified rate {qual:.0%}. Continuing without changes.",
    )


# ────────────────────────────────────────────────────────────────────────────
# diagnose_node
# ────────────────────────────────────────────────────────────────────────────

def diagnose_node(state: dict) -> dict:
    """
    Snapshot metrics and produce a plain-language diagnosis.

    In simulation mode, generates synthetic metrics so the loop can be
    demoed without live spend. In live mode, calls meta_client.get_insights().

    State reads:  metric_snapshots, budget, campaign_bundle, campaign_plan
    State writes: metric_snapshots (appended), learning_state, latest_diagnosis
    """
    existing = list(state.get("metric_snapshots") or [])
    budget = float(state.get("budget") or 100)
    plan = state.get("campaign_bundle", {}) or {}
    price_tier = (plan.get("real_estate_project") or {}).get("price_tier", "mid_range")
    duration = (plan.get("real_estate_project") or {}).get("campaign_duration_days", 14) or 14
    daily_budget = budget / duration

    thresholds = get_tier_thresholds(price_tier)

    if _SIM_MODE:
        snapshot = _synthetic_metrics(existing, daily_budget)
        logger.info(
            "diagnose_node (sim): CPL=%.2f qualified_rate=%.0f%% frequency=%.1f",
            snapshot["cpl"], snapshot["qualified_rate"] * 100, snapshot["frequency"],
        )
    else:
        adset_id = state.get("meta_adset_id", "")
        if not adset_id:
            logger.warning("diagnose_node: meta_adset_id not in state — cannot pull insights")
            snapshot = {}
        else:
            from AutoMarkAi.backend.meta_client import get_meta_client
            try:
                client = get_meta_client()
                raw = client.get_insights(adset_id)
                snapshot = {
                    "ts": _now_iso(),
                    "cpl": raw.get("cpl_usd", 0),
                    "qualified_rate": raw.get("qualified_rate", 0),
                    "frequency": raw.get("frequency", 0),
                    "leads": raw.get("leads", 0),
                    "qualified_leads": 0,
                    "reach": raw.get("reach", 0),
                    "spend_usd": raw.get("spend_usd", 0),
                    "simulated": False,
                }
                logger.info(
                    "diagnose_node (live): CPL=%.2f leads=%d frequency=%.1f",
                    snapshot["cpl"], snapshot["leads"], snapshot["frequency"],
                )
            except Exception as e:
                logger.error("diagnose_node: get_insights failed: %s", e)
                snapshot = {}

    all_snapshots = existing + ([snapshot] if snapshot else [])
    learning_state = _determine_learning_state(all_snapshots, thresholds)

    # Plain-language diagnosis (no jargon in the default view)
    latest = snapshot or (existing[-1] if existing else {})
    cpl = latest.get("cpl", 0)
    qual = latest.get("qualified_rate", 0)
    leads = latest.get("leads", 0)
    freq = latest.get("frequency", 0)

    if learning_state == LearningState.LEARNING:
        status = "Campaign is still in the learning phase — collecting data."
    elif cpl <= thresholds.cpl_target_usd and qual >= thresholds.qualified_rate_target:
        status = "Performing well — cost per lead is on target and lead quality is good."
    elif cpl >= thresholds.cpl_high_usd:
        status = "Cost per lead is higher than target — may need budget or creative adjustment."
    elif qual <= thresholds.qualified_rate_low:
        status = "Lead quality is low — consider refreshing the ad creative."
    else:
        status = "Performance is acceptable — monitoring for improvement."

    latest_diagnosis = {
        "ts": _now_iso(),
        "status": status,
        "cpl": cpl,
        "qualified_rate": qual,
        "leads_today": leads,
        "frequency": freq,
        "learning_state": learning_state,
        "price_tier": price_tier,
        "simulated": _SIM_MODE,
    }

    return {
        "metric_snapshots": all_snapshots,
        "learning_state": learning_state,
        "latest_diagnosis": latest_diagnosis,
        "errors": [],
    }


# ────────────────────────────────────────────────────────────────────────────
# decision_node
# ────────────────────────────────────────────────────────────────────────────

def decision_node(state: dict) -> dict:
    """
    Make an operate decision based on the latest diagnosis.

    Full Manual mode: interrupts with the proposed action so the user can
    approve or modify before anything runs.
    Guided / Autopilot: proceeds without interrupt unless it's a
    money-moving or irreversible action (pause, scale, take_hand).

    State reads:  metric_snapshots, learning_state, approval_mode,
                  control_mode, campaign_bundle
    State writes: _operate_action, decisions_log, pending_approval
    """
    snapshots = list(state.get("metric_snapshots") or [])
    learning_state = state.get("learning_state", LearningState.LEARNING)
    approval_mode = state.get("approval_mode", "full_manual")
    control_mode = state.get("control_mode", "advantage_plus")
    plan = state.get("campaign_bundle") or {}
    price_tier = (plan.get("real_estate_project") or {}).get("price_tier", "mid_range")

    thresholds = get_tier_thresholds(price_tier)
    latest = snapshots[-1] if snapshots else {}

    # Days since last scale action (rough estimate from decisions_log)
    decisions = list(state.get("decisions_log") or [])
    scale_decisions = [d for d in decisions if d.get("decision") in (
        OperateDecision.SCALE_UP, OperateDecision.SCALE_DOWN
    )]
    days_since_scale = len(snapshots) - (
        snapshots.index(next(
            (s for s in reversed(snapshots) if s["ts"] <= (scale_decisions[-1]["ts"] if scale_decisions else "")),
            None
        )) if scale_decisions else 0
    ) if scale_decisions and snapshots else len(snapshots)

    decision, rationale = _make_decision(
        latest, thresholds, learning_state, control_mode,
        n_snapshots=len(snapshots), days_since_last_scale=days_since_scale
    )

    # Money-moving decisions require approval in guided mode too
    money_moving = decision in (
        OperateDecision.SCALE_UP, OperateDecision.SCALE_DOWN,
        OperateDecision.PAUSE, OperateDecision.TAKE_HAND,
        OperateDecision.HAND_BACK,
    )

    needs_interrupt = (
        approval_mode == "full_manual"
        or (approval_mode == "guided" and money_moving)
    )

    if needs_interrupt:
        interrupt({
            "stage": "approval",
            "type": "money" if money_moving else "plan",
            "description": f"Proposed action: {decision}\n\n{rationale}",
            "payload": {"decision": decision, "rationale": rationale},
        })

    # Log decision
    log_entry = {
        "ts": _now_iso(),
        "decision": decision,
        "rationale": rationale,
        "learning_state": learning_state,
        "cpl": latest.get("cpl"),
        "qualified_rate": latest.get("qualified_rate"),
    }

    return {
        "_operate_action": decision if decision != OperateDecision.HOLD else None,
        "decisions_log": decisions + [log_entry],
        "errors": [],
    }


# ────────────────────────────────────────────────────────────────────────────
# act_node
# ────────────────────────────────────────────────────────────────────────────

def act_node(state: dict) -> dict:
    """
    Execute the approved operate decision via meta_client.

    In simulation mode, logs the action without making real API calls.
    In live mode, calls the appropriate meta_client method.

    State reads:  _operate_action, decisions_log, campaign_bundle
    State writes: control_mode, decisions_log (outcome appended), errors
    """
    action = state.get("_operate_action")
    if not action:
        return {}

    decisions = list(state.get("decisions_log") or [])
    control_mode = state.get("control_mode", "advantage_plus")

    logger.info("act_node: executing decision=%s sim=%s", action, _SIM_MODE)

    adset_id = state.get("meta_adset_id", "")
    outcome: dict = {"executed": False, "sim": _SIM_MODE}

    if _SIM_MODE:
        outcome["executed"] = True
        logger.info("act_node (sim): action=%s logged without real API call", action)
    elif not adset_id:
        outcome["error"] = "meta_adset_id not in state — cannot execute live action"
        logger.warning("act_node: %s", outcome["error"])
    else:
        from AutoMarkAi.backend.meta_client import get_meta_client
        try:
            client = get_meta_client()
            if action == OperateDecision.PAUSE:
                result = client.pause_adset(adset_id)
            elif action == OperateDecision.SCALE_UP:
                thresholds = get_tier_thresholds(
                    (state.get("campaign_bundle") or {}).get("real_estate_project", {}).get("price_tier", "mid_range")
                )
                result = client.update_adset_budget(adset_id, 1 + thresholds.scale_up_pct)
            elif action == OperateDecision.SCALE_DOWN:
                thresholds = get_tier_thresholds(
                    (state.get("campaign_bundle") or {}).get("real_estate_project", {}).get("price_tier", "mid_range")
                )
                result = client.update_adset_budget(adset_id, 1 - thresholds.scale_down_pct)
            elif action == OperateDecision.TAKE_HAND:
                result = client.disable_advantage_plus(adset_id)
            elif action == OperateDecision.HAND_BACK:
                result = client.enable_advantage_plus(adset_id)
            else:
                result = {"note": f"No live API action required for decision={action}"}
            outcome = {"executed": True, "sim": False, "api_result": result}
            logger.info("act_node (live): action=%s result=%s", action, result)
        except Exception as e:
            outcome = {"executed": False, "sim": False, "error": str(e)}
            logger.error("act_node: live action failed: %s", e)

    # Update control_mode for decisions that change it
    new_control_mode = control_mode
    if action == OperateDecision.TAKE_HAND:
        new_control_mode = "manual"
    elif action == OperateDecision.HAND_BACK:
        new_control_mode = "advantage_plus"

    # Append outcome to the last decisions_log entry
    if decisions:
        decisions[-1]["outcome"] = outcome
        decisions[-1]["executed_at"] = _now_iso()

    return {
        "control_mode": new_control_mode,
        "decisions_log": decisions,
        "errors": [] if outcome.get("executed") else [outcome.get("error", "")],
    }
