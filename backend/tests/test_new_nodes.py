"""Tests for the real estate interview, photo selection, and creative nodes."""

import base64
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Real estate interview — fixed questions + LLM follow-ups
# ---------------------------------------------------------------------------

def test_question_gen_presents_first_fixed_question():
    """On a fresh state, question_gen_node presents the first fixed question (no LLM).

    Phase 1: first question is 'advertiser_type' (added for critical-coverage).
    """
    import AutoMarkAi.backend.nodes.question_generator as qg
    result = qg.question_gen_node({"language": "en"})
    assert result["questions_done"] is False
    assert result["current_fixed_q_index"] == 0
    assert result["pending_question"]["data_field"] == "advertiser_type"
    assert result["pending_question"]["is_follow_up"] is False


def test_question_gen_advances_to_next_fixed_when_no_followup():
    """After a fixed answer with follow-ups disabled, it advances to the next fixed question.

    Phase 1: index 0 = 'advertiser_type', advancing lands on index 1 = 'compound_name'.
    """
    import AutoMarkAi.backend.nodes.question_generator as qg
    with patch.object(qg, "ENABLE_FOLLOW_UPS", False):
        result = qg.question_gen_node({
            "language": "en",
            "current_fixed_q_index": 0,
            "pending_answered": True,
            "last_answer_was_follow_up": False,
            "real_estate_data": {"advertiser_type": "developer"},
        })
    assert result["questions_done"] is False
    assert result["current_fixed_q_index"] == 1
    assert result["pending_question"]["data_field"] == "compound_name"


def test_question_gen_completes_after_last_fixed():
    """Advancing past the final fixed question ends the interview."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    last = qg.TOTAL_FIXED - 1
    with patch.object(qg, "ENABLE_FOLLOW_UPS", False):
        result = qg.question_gen_node({
            "language": "en",
            "current_fixed_q_index": last,
            "pending_answered": True,
            "last_answer_was_follow_up": False,
            "real_estate_data": {},
        })
    assert result["questions_done"] is True


def test_question_ask_stores_fixed_answer_and_derives_fields():
    """question_ask_node stores into real_estate_data and derives machine fields."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    pending = {
        "stage": "questions",
        "question": "How long should the campaign run?",
        "question_type": "single_select_with_other",
        "options": [
            {"label": "1 week", "value": "7", "recommended": False},
            {"label": "2 weeks", "value": "14", "recommended": True},
        ],
        "is_follow_up": False,
        "data_field": "campaign_duration",
        "key": "campaign_duration",
    }
    with patch("AutoMarkAi.backend.nodes.question_generator.interrupt",
               return_value={"answer": "2 weeks"}):
        result = qg.question_ask_node({"pending_question": pending})
    assert result["pending_answered"] is True
    assert result["real_estate_data"]["campaign_duration"] == "2 weeks"
    assert result["campaign_duration_days"] == 14


def test_question_ask_stores_follow_up_answer():
    """A follow-up answer is logged separately and flags the next advance."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    pending = {"question": "Any nearby landmarks?", "is_follow_up": True, "data_field": None}
    with patch("AutoMarkAi.backend.nodes.question_generator.interrupt",
               return_value={"answer": "Next to the mall"}):
        result = qg.question_ask_node({"pending_question": pending, "follow_up_log": []})
    assert result["last_answer_was_follow_up"] is True
    assert result["follow_up_log"][0]["a"] == "Next to the mall"


def test_route_after_gen():
    import AutoMarkAi.backend.nodes.question_generator as qg
    assert qg.route_after_gen({"questions_done": False}) == "question_ask_node"
    assert qg.route_after_gen({"questions_done": True}) == "orchestrator_node"


def test_target_ask_node_stores_goal_from_choice():
    """target_ask_node turns the chosen option into state['goal']."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    with patch("AutoMarkAi.backend.nodes.question_generator.interrupt",
               return_value={"answer": "generate leads for the project"}):
        result = qg.target_ask_node({"campaign_target_options": [
            {"label": "Lead Generation", "goal": "generate leads for the project", "recommended": True},
        ]})
    assert result["goal"] == "generate leads for the project"


# ---------------------------------------------------------------------------
# Photo selection — pick which uploaded photos to use (no generation)
# ---------------------------------------------------------------------------

def test_photo_select_node_keeps_only_selected(tmp_path):
    import AutoMarkAi.backend.nodes.review as review
    f1 = tmp_path / "a.jpg"
    f2 = tmp_path / "b.jpg"
    f1.write_bytes(b"AAA")
    f2.write_bytes(b"BBB")
    with patch("AutoMarkAi.backend.nodes.review.interrupt", return_value={"selected_indices": [1]}):
        result = review.photo_select_node({"image_paths": [str(f1), str(f2)], "creative_output": {}})
    imgs = result["creative_output"]["generated_images"]
    assert imgs == [base64.b64encode(b"BBB").decode("utf-8")]
    assert result["review_stage"] == "photos_selected"


# ---------------------------------------------------------------------------
# Creative node — attaches real photos, never generates AI images
# ---------------------------------------------------------------------------

def test_creative_node_attaches_real_photos_no_ai(tmp_path):
    import importlib
    import AutoMarkAi.backend.nodes.creative
    importlib.reload(AutoMarkAi.backend.nodes.creative)
    from AutoMarkAi.backend.nodes.creative import creative_node

    photo = tmp_path / "unit.jpg"
    photo.write_bytes(b"PHOTO")

    mock_creative = {
        "copies": ["C1", "C2", "C3"],
        "headlines": ["H1", "H2", "H3"],
        "cta": "Sign Up",
        "visual_prompt": "should be stripped",
    }
    state = {
        "campaign_plan": {"product_type": "Real Estate", "objective": "LEADS", "language": "en"},
        "budget": 500.0,
        "goal": "generate leads",
        "image_paths": [str(photo)],
    }
    with patch("AutoMarkAi.backend.nodes.creative.call_llm", return_value=(json.dumps(mock_creative), "groq")):
        result = creative_node(state)

    creative = result["creative_output"]
    assert creative["generated_images"] == [base64.b64encode(b"PHOTO").decode("utf-8")]
    assert "visual_prompt" not in creative  # no AI images for real estate
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# Text review — chosen copy + headline move to the front (unchanged behaviour)
# ---------------------------------------------------------------------------

def test_text_review_selects_copy_and_headline():
    import importlib
    import AutoMarkAi.backend.nodes.review
    importlib.reload(AutoMarkAi.backend.nodes.review)
    from AutoMarkAi.backend.nodes.review import text_review_node

    with patch("AutoMarkAi.backend.nodes.review.interrupt",
               return_value={"copy_index": 1, "headline_index": 2,
                             "copy_text": "", "headline_text": ""}):
        result = text_review_node({
            "creative_output": {
                "generated_images": ["b64_1"],
                "copies": ["C1", "C2", "C3"],
                "headlines": ["H1", "H2", "H3"],
                "cta": "Sign Up",
            }
        })

    creative = result["creative_output"]
    assert result["review_stage"] == "done"
    assert creative["copies"][0] == "C2"
    assert creative["headlines"][0] == "H3"
    assert creative["selected_copy"] == "C2"
    assert creative["selected_headline"] == "H3"


def test_text_review_applies_manual_edits():
    import importlib
    import AutoMarkAi.backend.nodes.review
    importlib.reload(AutoMarkAi.backend.nodes.review)
    from AutoMarkAi.backend.nodes.review import text_review_node

    with patch("AutoMarkAi.backend.nodes.review.interrupt",
               return_value={"copy_index": 0, "headline_index": 0,
                             "copy_text": "Edited copy!", "headline_text": "Edited headline!"}):
        result = text_review_node({
            "creative_output": {
                "generated_images": ["b64_1"],
                "copies": ["C1", "C2", "C3"],
                "headlines": ["H1", "H2", "H3"],
                "cta": "Sign Up",
            }
        })

    creative = result["creative_output"]
    assert creative["copies"][0] == "Edited copy!"
    assert creative["selected_copy"] == "Edited copy!"
    assert creative["headlines"][0] == "Edited headline!"
    assert result["review_stage"] == "done"


# ---------------------------------------------------------------------------
# Phase 1: interview covers all 12 fixed questions (critical coverage)
# ---------------------------------------------------------------------------

def test_interview_covers_all_critical_fields():
    """FIXED_QUESTIONS must contain all 12 critical data fields."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    required_fields = {
        "advertiser_type", "compound_name", "location", "unit_types",
        "unit_status", "starting_price", "payment_plan", "amenities",
        "target_buyer", "offer", "lead_destination", "campaign_duration",
    }
    actual_fields = {q["data_field"] for q in qg.FIXED_QUESTIONS}
    missing = required_fields - actual_fields
    assert not missing, f"Missing critical fields: {missing}"
    assert qg.TOTAL_FIXED == 12


def test_new_questions_have_bilingual_support():
    """Every new question must have both EN and AR question text."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    new_keys = {"advertiser_type", "unit_status", "amenities", "target_buyer"}
    for q in qg.FIXED_QUESTIONS:
        if q["key"] in new_keys:
            assert q.get("question_en"), f"Missing EN text for '{q['key']}'"
            assert q.get("question_ar"), f"Missing AR text for '{q['key']}'"
            if q.get("options_en"):
                assert q.get("options_ar"), f"Missing AR options for '{q['key']}'"


# ---------------------------------------------------------------------------
# Phase 0: supervisor routing
# ---------------------------------------------------------------------------

def test_supervisor_route_discovery_phase():
    """supervisor_route returns 'target_gen_node' during discovery phase."""
    from AutoMarkAi.backend.nodes.supervisor import supervisor_route
    result = supervisor_route({"campaign_phase": "discovery"})
    assert result == "target_gen_node"


def test_supervisor_route_build_phase():
    """supervisor_route returns 'orchestrator_node' during build phase."""
    from AutoMarkAi.backend.nodes.supervisor import supervisor_route
    result = supervisor_route({"campaign_phase": "build"})
    assert result == "orchestrator_node"


def test_supervisor_route_defaults_to_discovery():
    """supervisor_route defaults to discovery when campaign_phase is absent."""
    from AutoMarkAi.backend.nodes.supervisor import supervisor_route
    result = supervisor_route({})
    assert result == "target_gen_node"


def test_supervisor_build_path_routing_functions():
    """route_after_orchestrator, route_to_subagents, route_after_text_review work correctly."""
    from AutoMarkAi.backend.nodes.supervisor import (
        route_after_orchestrator,
        route_after_text_review,
    )
    assert route_after_orchestrator({"campaign_plan": {"x": 1}}) == "strategy_node"
    assert route_after_orchestrator({}) == "merge_node"
    assert route_after_text_review({"review_stage": "redo_creative"}) == "creative_node"
    assert route_after_text_review({"review_stage": "done"}) == "merge_node"


# ---------------------------------------------------------------------------
# Phase 1: Approval Gateway — approval_mode branching
# ---------------------------------------------------------------------------

def test_target_ask_auto_picks_in_guided_mode():
    """In guided mode, target_ask_node auto-selects the recommended goal without interrupt."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    options = [
        {"label": "Lead Generation", "goal": "generate leads for the project", "recommended": True},
        {"label": "Brand Awareness", "goal": "grow brand awareness", "recommended": False},
    ]
    result = qg.target_ask_node({"approval_mode": "guided", "campaign_target_options": options})
    assert result["goal"] == "generate leads for the project"


def test_target_ask_auto_picks_in_autopilot_mode():
    """In autopilot mode, target_ask_node also auto-selects without interrupt."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    options = [
        {"label": "Lead Generation", "goal": "generate leads", "recommended": True},
    ]
    result = qg.target_ask_node({"approval_mode": "autopilot", "campaign_target_options": options})
    assert result["goal"] == "generate leads"


def test_target_ask_interrupts_in_full_manual_mode():
    """In full_manual mode (default), target_ask_node raises an interrupt."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    options = [{"label": "Lead Gen", "goal": "generate leads", "recommended": True}]
    with patch("AutoMarkAi.backend.nodes.question_generator.interrupt",
               return_value={"goal": "generate leads"}):
        result = qg.target_ask_node({"approval_mode": "full_manual", "campaign_target_options": options})
    assert result["goal"] == "generate leads"


def test_photo_select_auto_selects_in_autopilot(tmp_path):
    """In autopilot mode, photo_select_node selects all photos without interrupt."""
    import importlib
    import AutoMarkAi.backend.nodes.review
    importlib.reload(AutoMarkAi.backend.nodes.review)
    from AutoMarkAi.backend.nodes.review import photo_select_node
    f1 = tmp_path / "a.jpg"
    f2 = tmp_path / "b.jpg"
    f1.write_bytes(b"AAA")
    f2.write_bytes(b"BBB")
    result = photo_select_node({
        "approval_mode": "autopilot",
        "image_paths": [str(f1), str(f2)],
        "creative_output": {},
    })
    assert result["review_stage"] == "photos_selected"
    assert len(result["creative_output"]["generated_images"]) == 2


def test_text_review_auto_picks_in_autopilot():
    """In autopilot mode, text_review_node picks the first copy/headline without interrupt."""
    import importlib
    import AutoMarkAi.backend.nodes.review
    importlib.reload(AutoMarkAi.backend.nodes.review)
    from AutoMarkAi.backend.nodes.review import text_review_node
    result = text_review_node({
        "approval_mode": "autopilot",
        "creative_output": {
            "generated_images": ["b64_1"],
            "copies": ["Copy A", "Copy B", "Copy C"],
            "headlines": ["H1", "H2", "H3"],
            "cta": "Sign Up",
        },
    })
    assert result["review_stage"] == "done"
    assert result["creative_output"]["selected_copy"] == "Copy A"
    assert result["creative_output"]["selected_headline"] == "H1"


def test_request_approval_auto_approves_creative_in_guided():
    """request_approval auto-approves 'creative' gate in guided mode."""
    from AutoMarkAi.backend.nodes.approvals import request_approval
    result = request_approval(
        {"approval_mode": "guided"},
        {"type": "creative", "description": "Review ad copy"},
    )
    assert result["decision"] == "approved"
    assert result["auto"] is True


def test_request_approval_interrupts_money_gate_in_guided():
    """request_approval raises interrupt for 'money' gate even in guided mode."""
    from AutoMarkAi.backend.nodes.approvals import request_approval
    with patch("AutoMarkAi.backend.nodes.approvals.interrupt",
               return_value={"decision": "approved"}):
        result = request_approval(
            {"approval_mode": "guided"},
            {"type": "money", "description": "Scale budget +25%"},
        )
    assert result["decision"] == "approved"
    assert result["auto"] is False


def test_request_approval_auto_approves_everything_in_autopilot():
    """request_approval auto-approves both creative and schedule gates in autopilot."""
    from AutoMarkAi.backend.nodes.approvals import request_approval
    for gate_type in ("creative", "plan", "schedule"):
        result = request_approval(
            {"approval_mode": "autopilot"},
            {"type": gate_type, "description": "some gate"},
        )
        assert result["decision"] == "approved", f"gate '{gate_type}' should auto-approve"
        assert result["auto"] is True


# ---------------------------------------------------------------------------
# Phase 2: Compliance gate
# ---------------------------------------------------------------------------

def test_compliance_node_passes_clean_campaign():
    """compliance_node passes a HOUSING-compliant media_output."""
    from AutoMarkAi.backend.nodes.compliance import compliance_node
    state = {
        "media_output": {
            "audience": {"age_min": 18, "age_max": 65, "genders": ["all"], "locations": ["EG"]},
            "special_ad_category": "HOUSING",
        },
        "creative_output": {
            "copies": ["Discover your dream unit today"],
            "headlines": ["New Cairo | Starting 2.5M"],
        },
    }
    result = compliance_node(state)
    assert result["compliance_result"]["passed"] is True
    assert result["compliance_result"]["violations"] == []


def test_compliance_node_blocks_demographic_narrowing():
    """compliance_node catches narrowed age range as HOUSING violation."""
    from AutoMarkAi.backend.nodes.compliance import compliance_node
    state = {
        "media_output": {
            "audience": {
                "age_min": 25, "age_max": 45,   # narrowed — not allowed
                "genders": ["all"],
                "income_tier": "high",           # blocked field
            },
            "special_ad_category": "HOUSING",
        },
        "creative_output": {"copies": [], "headlines": []},
    }
    result = compliance_node(state)
    assert result["compliance_result"]["passed"] is False
    assert any("age_max" in v for v in result["compliance_result"]["violations"])
    assert any("income_tier" in v for v in result["compliance_result"]["violations"])


def test_compliance_node_catches_preference_language():
    """compliance_node catches 'perfect for families' as a copy violation."""
    from AutoMarkAi.backend.nodes.compliance import compliance_node
    state = {
        "media_output": {
            "audience": {"age_min": 18, "age_max": 65, "genders": ["all"]},
            "special_ad_category": "HOUSING",
        },
        "creative_output": {
            "copies": ["This compound is perfect for families looking for space"],
            "headlines": ["Family living at its best"],
        },
    }
    result = compliance_node(state)
    assert result["compliance_result"]["passed"] is False
    assert any("perfect for families" in v for v in result["compliance_result"]["violations"])


def test_compliance_node_warns_missing_special_ad_category():
    """compliance_node adds a violation when special_ad_category is not HOUSING."""
    from AutoMarkAi.backend.nodes.compliance import compliance_node
    state = {
        "media_output": {
            "audience": {"age_min": 18, "age_max": 65, "genders": ["all"]},
            # no special_ad_category
        },
        "creative_output": {"copies": [], "headlines": []},
    }
    result = compliance_node(state)
    assert result["compliance_result"]["passed"] is False
    assert any("HOUSING" in v for v in result["compliance_result"]["violations"])


# ---------------------------------------------------------------------------
# Phase 3: Research squad
# ---------------------------------------------------------------------------

def test_audience_node_produces_compliant_plan():
    """audience_node returns HOUSING-compliant audience plan (no demographic targeting)."""
    from AutoMarkAi.backend.nodes.research import audience_node
    state = {
        "real_estate_data": {
            "location": "New Cairo",
            "starting_price": "3,500,000",
        },
        "budget": 500.0,
    }
    result = audience_node(state)
    plan = result["audience_plan"]
    assert plan["age_min"] == 18
    assert plan["age_max"] == 65
    assert plan["genders"] == ["all"]
    assert plan["interests"] == []   # broad delivery — no interest targeting
    assert "geo" in plan
    assert plan["geo"]["radius_km"] > 0
    assert result["errors"] == []


def test_audience_node_infers_price_tier():
    """audience_node populates price_tier and platform_split from price."""
    from AutoMarkAi.backend.nodes.research import audience_node
    state = {
        "real_estate_data": {"location": "6th of October", "starting_price": "1,200,000"},
    }
    result = audience_node(state)
    assert result["audience_plan"]["price_tier"] == "affordable"
    assert "facebook" in result["audience_plan"]["platform_split"]


def test_competitor_node_returns_findings_in_sim_mode():
    """competitor_node returns synthetic findings in simulation mode."""
    from AutoMarkAi.backend.nodes.research import competitor_node
    with patch.dict("os.environ", {"META_SIMULATION_MODE": "true"}):
        result = competitor_node({})
    assert len(result["competitor_findings"]) > 0
    assert "hook" in result["competitor_findings"][0]
    assert "insight" in result["competitor_findings"][0]


def test_trend_node_returns_egypt_demand_windows():
    """trend_node returns seasonal demand windows for Egypt."""
    from AutoMarkAi.backend.nodes.research import trend_node
    result = trend_node({})
    assert len(result["demand_windows"]) == 1
    windows = result["demand_windows"][0]
    assert "seasonal_windows" in windows
    assert "payday_calendar" in windows
    assert len(windows["seasonal_windows"]) >= 3


# ---------------------------------------------------------------------------
# Phase 4: Policy thresholds + lifecycle decisions
# ---------------------------------------------------------------------------

def test_thresholds_mid_range_tier():
    """get_tier_thresholds returns mid_range values."""
    from AutoMarkAi.backend.policy.thresholds import get_tier_thresholds
    t = get_tier_thresholds("mid_range")
    assert t.cpl_target_usd == 8.0
    assert t.cpl_acceptable_usd == 16.0


def test_thresholds_luxury_tier_has_higher_cpl():
    """Luxury tier has higher CPL thresholds than mid_range."""
    from AutoMarkAi.backend.policy.thresholds import get_tier_thresholds
    mid = get_tier_thresholds("mid_range")
    lux = get_tier_thresholds("luxury")
    assert lux.cpl_target_usd > mid.cpl_target_usd
    assert lux.cpl_pause_usd > mid.cpl_pause_usd


def test_diagnose_node_generates_synthetic_snapshot_in_sim_mode():
    """diagnose_node appends a synthetic metric snapshot in sim mode."""
    with patch.dict("os.environ", {"META_SIMULATION_MODE": "true"}):
        from AutoMarkAi.backend.nodes import lifecycle
        import importlib
        importlib.reload(lifecycle)
        result = lifecycle.diagnose_node({"budget": 500.0, "metric_snapshots": []})
    assert len(result["metric_snapshots"]) == 1
    snap = result["metric_snapshots"][0]
    assert "cpl" in snap
    assert "qualified_rate" in snap
    assert snap["simulated"] is True
    assert "learning_state" in result
    assert "latest_diagnosis" in result
    assert "status" in result["latest_diagnosis"]


def test_diagnose_node_determines_learning_state_after_50_leads():
    """learning_state becomes 'exited' after enough lead events."""
    from AutoMarkAi.backend.policy.thresholds import LearningState
    with patch.dict("os.environ", {"META_SIMULATION_MODE": "true"}):
        from AutoMarkAi.backend.nodes import lifecycle
        import importlib
        importlib.reload(lifecycle)
        # Build 10 snapshots each with 6 leads = 60 total > threshold 50
        existing = [{"cpl": 10.0, "qualified_rate": 0.3, "frequency": 1.5, "leads": 6, "ts": "t"} for _ in range(10)]
        result = lifecycle.diagnose_node({"budget": 500.0, "metric_snapshots": existing})
    assert result["learning_state"] == LearningState.EXITED


def test_decision_node_holds_during_learning():
    """decision_node emits HOLD during learning phase (never act)."""
    with patch.dict("os.environ", {"META_SIMULATION_MODE": "true"}):
        from AutoMarkAi.backend.nodes import lifecycle
        import importlib
        importlib.reload(lifecycle)
        state = {
            "metric_snapshots": [{"cpl": 10.0, "qualified_rate": 0.3, "frequency": 1.0, "leads": 5, "ts": "t"}],
            "learning_state": "learning",
            "approval_mode": "autopilot",
            "control_mode": "advantage_plus",
            "campaign_bundle": {"real_estate_project": {"price_tier": "mid_range"}},
            "decisions_log": [],
        }
        result = lifecycle.decision_node(state)
    from AutoMarkAi.backend.policy.thresholds import OperateDecision
    assert result["_operate_action"] is None  # HOLD produces no action
    assert any(d["decision"] == OperateDecision.HOLD for d in result["decisions_log"])


def test_act_node_executes_in_sim_mode():
    """act_node marks execution as completed in simulation mode."""
    with patch.dict("os.environ", {"META_SIMULATION_MODE": "true"}):
        from AutoMarkAi.backend.nodes import lifecycle
        import importlib
        importlib.reload(lifecycle)
        from AutoMarkAi.backend.policy.thresholds import OperateDecision
        state = {
            "_operate_action": OperateDecision.SCALE_UP,
            "control_mode": "advantage_plus",
            "decisions_log": [{"ts": "t", "decision": OperateDecision.SCALE_UP, "rationale": "test"}],
        }
        result = lifecycle.act_node(state)
    assert result["decisions_log"][-1]["outcome"]["executed"] is True


# ---------------------------------------------------------------------------
# Phase 4: route_operate supervisor function
# ---------------------------------------------------------------------------

def test_route_operate_returns_diagnose_for_operate_phase():
    """route_operate routes to diagnose_node when campaign_phase=operate."""
    from AutoMarkAi.backend.nodes.supervisor import route_operate
    assert route_operate({"campaign_phase": "operate"}) == "diagnose_node"


def test_route_operate_returns_target_gen_for_discovery():
    """route_operate routes to target_gen_node for discovery phase."""
    from AutoMarkAi.backend.nodes.supervisor import route_operate
    assert route_operate({"campaign_phase": "discovery"}) == "target_gen_node"
    assert route_operate({}) == "target_gen_node"


# ---------------------------------------------------------------------------
# Phase 5: Memory
# ---------------------------------------------------------------------------

def test_client_store_recall_returns_empty_for_new_client(tmp_path):
    """client_store.recall returns empty dict for an unknown client."""
    import AutoMarkAi.backend.memory.client_store as cs
    with patch.object(cs, "_STORE_DIR", tmp_path):
        result = cs.recall("brand_new_client")
    assert result == {}


def test_client_store_merge_and_recall(tmp_path):
    """client_store.merge persists data; recall retrieves it."""
    import AutoMarkAi.backend.memory.client_store as cs
    with patch.object(cs, "_STORE_DIR", tmp_path):
        cs.merge("sodic_east", {
            "compound_name": "Sodic East",
            "location": "New Cairo",
            "price_tier": "premium",
            "outcome": "published",
            "performance_notes": "CPL was strong in September.",
        })
        data = cs.recall("sodic_east")
    assert data["total_sessions"] == 1
    assert "Sodic East" in data["known_compounds"]
    assert data["sessions"][0]["location"] == "New Cairo"


def test_client_store_build_context_snippet_for_returning_client(tmp_path):
    """build_context_snippet returns a non-empty string for a known client."""
    import AutoMarkAi.backend.memory.client_store as cs
    with patch.object(cs, "_STORE_DIR", tmp_path):
        cs.merge("ora", {
            "compound_name": "Zed",
            "location": "Cairo",
            "price_tier": "luxury",
            "outcome": "published",
            "performance_notes": "Video ads outperformed static.",
        })
        mem = cs.recall("ora")
    snippet = cs.build_context_snippet(mem, language="en")
    assert "Zed" in snippet
    assert len(snippet) > 10
