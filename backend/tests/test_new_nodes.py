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
    """On a fresh state, question_gen_node presents the first fixed question (no LLM)."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    result = qg.question_gen_node({"language": "en"})
    assert result["questions_done"] is False
    assert result["current_fixed_q_index"] == 0
    assert result["pending_question"]["data_field"] == "compound_name"
    assert result["pending_question"]["is_follow_up"] is False


def test_question_gen_advances_to_next_fixed_when_no_followup():
    """After a fixed answer with follow-ups disabled, it advances to the next fixed question."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    with patch.object(qg, "ENABLE_FOLLOW_UPS", False):
        result = qg.question_gen_node({
            "language": "en",
            "current_fixed_q_index": 0,
            "pending_answered": True,
            "last_answer_was_follow_up": False,
            "real_estate_data": {"compound_name": "Palm Hills"},
        })
    assert result["questions_done"] is False
    assert result["current_fixed_q_index"] == 1
    assert result["pending_question"]["data_field"] == "location"


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
