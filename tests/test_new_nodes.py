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

    assert len(result["questions"]) == 4
    assert all(isinstance(q, str) for q in result["questions"])


# ---------------------------------------------------------------------------
# Test 7: creative_node image generation failure is graceful
# ---------------------------------------------------------------------------

def test_creative_node_image_generation_failure_is_graceful():
    """If Imagen fails, creative_node still returns successfully with empty generated_images."""
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
# Test 9: review_node returns done when all approved
# ---------------------------------------------------------------------------

def test_review_node_all_approved():
    """review_node should return review_stage='done' when user approves images and text."""
    import importlib
    import nodes.review
    importlib.reload(nodes.review)
    from nodes.review import review_node

    with patch("nodes.review.interrupt") as mock_interrupt:
        mock_interrupt.side_effect = [
            # Phase 1: image_review — all approved
            {"approved": [True, True, True], "feedback": {}},
            # Phase 2: text_review — approved
            {"approved": True, "feedback": ""},
        ]
        with patch("nodes.review.generate_ad_images"):
            result = review_node({
                "creative_output": {
                    "generated_images": ["b64_1", "b64_2", "b64_3"],
                    "visual_prompt": "product shot",
                    "copies": ["C1", "C2", "C3"],
                    "headlines": ["H1", "H2", "H3"],
                    "cta": "Shop Now",
                }
            })

    assert result["review_stage"] == "done"
    assert result["feedback"] == {}


# ---------------------------------------------------------------------------
# Test 10: review_node routes back to creative on text rejection
# ---------------------------------------------------------------------------

def test_review_node_text_rejected_routes_to_creative():
    """review_node should return review_stage='redo_creative' when text is rejected."""
    import importlib
    import nodes.review
    importlib.reload(nodes.review)
    from nodes.review import review_node

    with patch("nodes.review.interrupt") as mock_interrupt:
        mock_interrupt.side_effect = [
            {"approved": [True, True, True], "feedback": {}},   # images approved
            {"approved": False, "feedback": "Make it more urgent"},  # text rejected
        ]
        with patch("nodes.review.generate_ad_images"):
            result = review_node({
                "creative_output": {
                    "generated_images": ["b64_1", "b64_2", "b64_3"],
                    "visual_prompt": "product shot",
                    "copies": ["C1", "C2", "C3"],
                    "headlines": ["H1", "H2", "H3"],
                    "cta": "Shop Now",
                }
            })

    assert result["review_stage"] == "redo_creative"
    assert result["feedback"]["creative"] == "Make it more urgent"


# ---------------------------------------------------------------------------
# Test 11: review_node regenerates rejected images
# ---------------------------------------------------------------------------

def test_review_node_regenerates_rejected_image():
    """review_node should call generate_ad_images for each rejected image."""
    import importlib
    import nodes.review
    importlib.reload(nodes.review)
    from nodes.review import review_node

    with patch("nodes.review.interrupt") as mock_interrupt:
        mock_interrupt.side_effect = [
            # First image_review: image 1 rejected
            {"approved": [True, False, True], "feedback": {1: "make it darker"}},
            # Second image_review: all approved after regen
            {"approved": [True, True, True], "feedback": {}},
            # text_review: approved
            {"approved": True, "feedback": ""},
        ]
        with patch("nodes.review.generate_ad_images",
                   return_value=["regenerated_b64"]) as mock_gen:
            result = review_node({
                "creative_output": {
                    "generated_images": ["b64_0", "b64_1", "b64_2"],
                    "visual_prompt": "luxury watch on marble",
                    "copies": ["C1", "C2", "C3"],
                    "headlines": ["H1", "H2", "H3"],
                    "cta": "Send Message",
                }
            })

    assert mock_gen.call_count == 1
    assert result["review_stage"] == "done"
    assert result["creative_output"]["generated_images"][1] == "regenerated_b64"
