"""Tests for question_generator_node, review_node, and new creative_node behaviour."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Test 6: question_generator_node returns 4 questions and collects answers
# ---------------------------------------------------------------------------

def test_question_generator_returns_four_questions():
    """question_generator_node should produce exactly 4 questions and interrupt for answers."""
    mock_questions = ["Q1?", "Q2?", "Q3?", "Q4?"]
    mock_answers = {"0": "A1", "1": "A2", "2": "A3", "3": "A4"}

    with patch("nodes.question_generator.call_llm_vision",
               return_value=json.dumps(mock_questions)):
        with patch("nodes.question_generator.interrupt",
                   return_value={"answers": mock_answers}):
            from nodes.question_generator import question_generator_node
            result = question_generator_node({
                "image_path": "tests/sample_input/watch.jpg",
                "goal": "get WhatsApp leads",
            })

    assert result["questions"] == mock_questions
    assert result["user_answers"] == mock_answers
    assert result["errors"] == []


def test_question_generator_falls_back_on_bad_response():
    """question_generator_node must use 4 generic fallback questions if LLM returns garbage."""
    with patch("nodes.question_generator.call_llm_vision",
               return_value="not valid json"):
        with patch("nodes.question_generator.interrupt",
                   return_value={"answers": {}}):
            from nodes.question_generator import question_generator_node
            result = question_generator_node({
                "image_path": "tests/sample_input/watch.jpg",
                "goal": "drive traffic",
            })

    # Fallback set size depends on marketing_type (4–8 questions are valid).
    assert 4 <= len(result["questions"]) <= 8
    assert all(isinstance(q, str) for q in result["questions"])


# ---------------------------------------------------------------------------
# Test 7: creative_node image generation failure is graceful
# ---------------------------------------------------------------------------

def test_creative_node_image_generation_failure_is_graceful():
    """If image generation fails, creative_node still returns successfully with empty generated_images."""
    import importlib
    import nodes.creative
    importlib.reload(nodes.creative)
    from nodes.creative import creative_node

    mock_creative = {
        "copies": ["C1", "C2", "C3"],
        "headlines": ["H1", "H2", "H3"],
        "cta": "Shop Now",
        "visual_prompt": "A product on white background.",
    }

    state = {
        "campaign_plan": {
            "product_type": "watch",
            "objective": "CONVERSIONS",
            "tone": "bold",
            "platform": "both",
        },
        "budget": 200.0,
        "goal": "drive sales",
        # AI image mode (no source photo) → exercises the generate_ad_images path
        "image_mode": "enhance_with_ai",
    }

    with patch("nodes.creative.call_llm", return_value=(json.dumps(mock_creative), "gemini")):
        with patch("nodes.creative.generate_ad_images",
                   side_effect=RuntimeError("Quota exceeded")):
            result = creative_node(state)

    assert result["creative_output"]["generated_images"] == []
    assert any("image_generation_failed" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# Test 8: creative_node injects feedback into the prompt on redo passes
# ---------------------------------------------------------------------------

def test_creative_node_uses_feedback_in_prompt():
    """creative_node must append feedback text to the LLM prompt when state has creative feedback."""
    import importlib
    import nodes.creative
    importlib.reload(nodes.creative)
    from nodes.creative import creative_node

    mock_creative = {
        "copies": ["C1", "C2", "C3"],
        "headlines": ["H1", "H2", "H3"],
        "cta": "Learn More",
        "visual_prompt": "A product shot.",
    }

    state = {
        "campaign_plan": {
            "product_type": "watch",
            "objective": "TRAFFIC",
            "tone": "modern",
            "platform": "both",
        },
        "budget": 100.0,
        "goal": "drive traffic",
        "feedback": {"creative": "Make the tone more urgent"},
    }

    captured = []

    def capture_call_llm(prompt, system, node_name, **kwargs):
        captured.append(prompt)
        return json.dumps(mock_creative), "gemini"

    with patch("nodes.creative.call_llm", side_effect=capture_call_llm):
        with patch("nodes.creative.generate_ad_images", return_value=["b64"] * 3):
            creative_node(state)

    assert captured, "call_llm was never called"
    assert "Make the tone more urgent" in captured[0], (
        "Feedback text not found in the prompt"
    )


# ---------------------------------------------------------------------------
# Test 9: text_review_node returns done when copy is approved
# ---------------------------------------------------------------------------

def test_text_review_approved_returns_done():
    """text_review_node should return review_stage='done' when copy is approved."""
    import importlib
    import nodes.review
    importlib.reload(nodes.review)
    from nodes.review import text_review_node

    with patch("nodes.review.interrupt", return_value={"approved": True, "feedback": ""}):
        result = text_review_node({
            "creative_output": {
                "generated_images": ["b64_1"],
                "copies": ["C1", "C2", "C3"],
                "headlines": ["H1", "H2", "H3"],
                "cta": "Shop Now",
            }
        })

    assert result["review_stage"] == "done"
    assert result["feedback"] == {}


# ---------------------------------------------------------------------------
# Test 10: text_review_node routes back to creative on copy rejection
# ---------------------------------------------------------------------------

def test_text_review_rejected_routes_to_creative():
    """text_review_node should return review_stage='redo_creative' when copy is rejected."""
    import importlib
    import nodes.review
    importlib.reload(nodes.review)
    from nodes.review import text_review_node

    with patch("nodes.review.interrupt",
               return_value={"approved": False, "feedback": "Make it more urgent"}):
        result = text_review_node({
            "creative_output": {
                "generated_images": ["b64_1"],
                "copies": ["C1", "C2", "C3"],
                "headlines": ["H1", "H2", "H3"],
                "cta": "Shop Now",
            }
        })

    assert result["review_stage"] == "redo_creative"
    assert result["feedback"]["creative"] == "Make it more urgent"


# ---------------------------------------------------------------------------
# Test 11: image_review_node routes a rejection to the regen node (no generation)
# ---------------------------------------------------------------------------

def test_image_review_rejection_routes_to_regen_without_generating():
    """image_review_node must NOT generate images itself — it routes to image_regen_node.

    This is the core of the cost fix: the interrupting node has no side effects,
    so resuming never replays a (billed) generation.
    """
    import importlib
    import nodes.review
    importlib.reload(nodes.review)
    from nodes.review import image_review_node

    with patch("nodes.review.enhance_ad_image") as mock_enh, \
         patch("nodes.review.generate_ad_images") as mock_gen, \
         patch("nodes.review.interrupt",
               return_value={"approved": [False], "feedback": {"0": "make it darker"}}):
        result = image_review_node({
            "image_mode": "enhance_with_ai",
            "image_path": "tests/sample_input/watch.jpg",
            "creative_output": {
                "generated_images": ["b64_0"],
                "visual_prompt": "luxury watch on marble",
            },
        })

    assert result["review_route"] == "to_regen"
    assert result["regen_indices"] == [0]
    assert mock_enh.call_count == 0, "image_review_node must not generate images"
    assert mock_gen.call_count == 0, "image_review_node must not generate images"


# ---------------------------------------------------------------------------
# Test 11b: image_regen_node generates exactly once and grows the history
# ---------------------------------------------------------------------------

def test_image_regen_node_generates_once_and_records_history():
    """image_regen_node generates the rejected image a single time and appends it to history."""
    import importlib
    import nodes.review
    importlib.reload(nodes.review)
    from nodes.review import image_regen_node

    with patch("nodes.review.enhance_ad_image",
               return_value=["regenerated_b64"]) as mock_enh:
        result = image_regen_node({
            "image_path": "tests/sample_input/watch.jpg",
            "regen_indices": [0],
            "image_regen_feedback": {"0": "make it darker"},
            "image_history": ["b64_0"],
            "regen_count": 0,
            "creative_output": {
                "generated_images": ["b64_0"],
                "visual_prompt": "luxury watch on marble",
            },
        })

    assert mock_enh.call_count == 1
    assert result["creative_output"]["generated_images"][0] == "regenerated_b64"
    assert result["image_history"] == ["b64_0", "regenerated_b64"]
    assert result["regen_count"] == 1


# ---------------------------------------------------------------------------
# Test 11c: at the regen limit, image_review_node routes to the picker (no gen)
# ---------------------------------------------------------------------------

def test_image_review_at_limit_routes_to_pick_without_generating():
    """Once regen_count >= max, a rejection goes to the picker and never regenerates."""
    import importlib
    import nodes.review
    importlib.reload(nodes.review)
    from nodes.review import image_review_node

    with patch("nodes.review.enhance_ad_image") as mock_enh, \
         patch("nodes.review.generate_ad_images") as mock_gen, \
         patch("nodes.review.interrupt",
               return_value={"approved": [False], "feedback": {"0": "again"}}):
        result = image_review_node({
            "image_mode": "enhance_with_ai",
            "image_path": "tests/sample_input/watch.jpg",
            "regen_count": nodes.review.MAX_REGENERATIONS_ALLOWED,
            "image_history": ["b64_0", "b64_1", "b64_2"],
            "creative_output": {
                "generated_images": ["b64_2"],
                "visual_prompt": "luxury watch on marble",
            },
        })

    assert result["review_route"] == "to_pick"
    assert mock_enh.call_count == 0
    assert mock_gen.call_count == 0
