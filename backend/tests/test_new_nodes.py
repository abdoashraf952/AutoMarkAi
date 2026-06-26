"""Tests for question_generator_node, review_node, and new creative_node behaviour."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Test 6: adaptive question flow — gen decides + produces one question,
# ask collects answer, dynamic routing ends the interview
# ---------------------------------------------------------------------------

def test_question_gen_node_generates_single_question():
    """question_gen_node returns exactly one new question, parsed from JSON."""
    with patch("AutoMarkAi.backend.nodes.question_generator.analyze_visual",
               return_value=json.dumps({"done": False, "question": "Who is your ideal buyer?"})):
        from AutoMarkAi.backend.nodes.question_generator import question_gen_node
        result = question_gen_node({
            "image_path": "tests/sample_input/watch.jpg",
            "goal": "get WhatsApp leads",
            "questions": [],
            "user_answers": {},
        })

    assert result["questions"] == ["Who is your ideal buyer?"]
    assert result["questions_done"] is False


def test_question_gen_node_uses_prior_qa_context():
    """The next question's prompt must include the previous question and answer."""
    captured = {}

    def capture(image_path, prompt, system, description=None):
        captured["prompt"] = prompt
        return json.dumps({"done": False, "question": "What's your busiest season?"})

    with patch("AutoMarkAi.backend.nodes.question_generator.analyze_visual", side_effect=capture):
        from AutoMarkAi.backend.nodes.question_generator import question_gen_node
        result = question_gen_node({
            "image_path": "tests/sample_input/watch.jpg",
            "goal": "drive sales",
            "questions": ["Who is your ideal buyer?"],
            "user_answers": {"0": "Young women who love fragrances"},
        })

    assert "Young women who love fragrances" in captured["prompt"]
    assert len(result["questions"]) == 2  # appended the second question


def test_question_gen_node_falls_back_on_failure():
    """If the analyze call fails, gen_node uses the index-aligned fallback question."""
    with patch("AutoMarkAi.backend.nodes.question_generator.analyze_visual",
               side_effect=RuntimeError("vision down")):
        from AutoMarkAi.backend.nodes.question_generator import question_gen_node
        result = question_gen_node({
            "image_path": "tests/sample_input/watch.jpg",
            "goal": "drive traffic",
            "questions": [],
            "user_answers": {},
        })

    assert len(result["questions"]) == 1
    assert isinstance(result["questions"][0], str) and result["questions"][0]


def test_question_gen_node_respects_minimum_before_stopping():
    """The model can't end the interview before MIN_QUESTIONS is reached."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    # Model says done, but no adaptive answers yet → forced to keep asking.
    with patch("AutoMarkAi.backend.nodes.question_generator.analyze_visual",
               return_value=json.dumps({"done": True, "question": ""})):
        result = qg.question_gen_node({
            "image_path": "tests/sample_input/watch.jpg",
            "goal": "drive sales",
            "questions": [],
            "user_answers": {},
        })
    assert result["questions_done"] is False
    assert len(result["questions"]) == 1  # a fallback/real question was produced


def test_question_gen_node_stops_at_maximum():
    """Once the max adaptive count is reached, the interview ends without an LLM call."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    answers = {str(i): "x" for i in range(qg._MAX_ADAPTIVE)}
    result = qg.question_gen_node({
        "image_path": "tests/sample_input/watch.jpg",
        "goal": "drive sales",
        "questions": [f"Q{i}" for i in range(qg._MAX_ADAPTIVE)],
        "user_answers": answers,
    })
    assert result["questions_done"] is True


def test_question_ask_node_stores_answer_and_routes():
    """question_ask_node stores the answer; route_after_gen ends on questions_done."""
    import AutoMarkAi.backend.nodes.question_generator as qg

    with patch("AutoMarkAi.backend.nodes.question_generator.interrupt", return_value={"answer": "A1"}):
        result = qg.question_ask_node({"questions": ["Q1?"], "user_answers": {}})

    assert result["user_answers"] == {"0": "A1"}
    # not done → loop back to ask the generated question
    assert qg.route_after_gen({"questions_done": False}) == "question_ask_node"
    # done → move on to the orchestrator
    assert qg.route_after_gen({"questions_done": True}) == "orchestrator_node"


def test_target_ask_node_stores_goal_from_choice():
    """target_ask_node turns the chosen option into state['goal']."""
    import AutoMarkAi.backend.nodes.question_generator as qg
    with patch("AutoMarkAi.backend.nodes.question_generator.interrupt",
               return_value={"answer": "get WhatsApp messages from buyers"}):
        result = qg.target_ask_node({"campaign_target_options": [
            {"label": "Messages", "goal": "get WhatsApp messages from buyers", "recommended": True},
        ]})
    assert result["goal"] == "get WhatsApp messages from buyers"


# ---------------------------------------------------------------------------
# Test 7: creative_node image generation failure is graceful
# ---------------------------------------------------------------------------

def test_creative_node_image_generation_failure_is_graceful():
    """If image generation fails, creative_node still returns successfully with empty generated_images."""
    import importlib
    import AutoMarkAi.backend.nodes.creative
    importlib.reload(AutoMarkAi.backend.nodes.creative)
    from AutoMarkAi.backend.nodes.creative import creative_node

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

    with patch("AutoMarkAi.backend.nodes.creative.call_llm", return_value=(json.dumps(mock_creative), "gemini")):
        with patch("AutoMarkAi.backend.nodes.creative.generate_ad_images",
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
    import AutoMarkAi.backend.nodes.creative
    importlib.reload(AutoMarkAi.backend.nodes.creative)
    from AutoMarkAi.backend.nodes.creative import creative_node

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

    with patch("AutoMarkAi.backend.nodes.creative.call_llm", side_effect=capture_call_llm):
        with patch("AutoMarkAi.backend.nodes.creative.generate_ad_images", return_value=["b64"] * 3):
            creative_node(state)

    assert captured, "call_llm was never called"
    assert "Make the tone more urgent" in captured[0], (
        "Feedback text not found in the prompt"
    )


# ---------------------------------------------------------------------------
# Test 9: text_review_node moves the chosen copy + headline to the front
# ---------------------------------------------------------------------------

def test_text_review_selects_copy_and_headline():
    """Choosing copy #1 and headline #2 makes them the primary creative; always done."""
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
                "cta": "Shop Now",
            }
        })

    creative = result["creative_output"]
    assert result["review_stage"] == "done"
    assert creative["copies"][0] == "C2"          # chosen copy moved to front
    assert creative["headlines"][0] == "H3"       # chosen headline moved to front
    assert creative["selected_copy"] == "C2"
    assert creative["selected_headline"] == "H3"


# ---------------------------------------------------------------------------
# Test 10: text_review_node honours manual edits to the chosen text
# ---------------------------------------------------------------------------

def test_text_review_applies_manual_edits():
    """Edited copy/headline text overrides the chosen original."""
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
                "cta": "Shop Now",
            }
        })

    creative = result["creative_output"]
    assert creative["copies"][0] == "Edited copy!"
    assert creative["selected_copy"] == "Edited copy!"
    assert creative["headlines"][0] == "Edited headline!"
    assert result["review_stage"] == "done"


# ---------------------------------------------------------------------------
# Test 11: image_review_node routes a rejection to the regen node (no generation)
# ---------------------------------------------------------------------------

def test_image_review_rejection_routes_to_regen_without_generating():
    """image_review_node must NOT generate images itself — it routes to image_regen_node.

    This is the core of the cost fix: the interrupting node has no side effects,
    so resuming never replays a (billed) generation.
    """
    import importlib
    import AutoMarkAi.backend.nodes.review
    importlib.reload(AutoMarkAi.backend.nodes.review)
    from AutoMarkAi.backend.nodes.review import image_review_node

    with patch("AutoMarkAi.backend.nodes.review.enhance_ad_image") as mock_enh, \
         patch("AutoMarkAi.backend.nodes.review.generate_ad_images") as mock_gen, \
         patch("AutoMarkAi.backend.nodes.review.interrupt",
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
    import AutoMarkAi.backend.nodes.review
    importlib.reload(AutoMarkAi.backend.nodes.review)
    from AutoMarkAi.backend.nodes.review import image_regen_node

    with patch("AutoMarkAi.backend.nodes.review.enhance_ad_image",
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
    import AutoMarkAi.backend.nodes.review
    importlib.reload(AutoMarkAi.backend.nodes.review)
    from AutoMarkAi.backend.nodes.review import image_review_node

    with patch("AutoMarkAi.backend.nodes.review.enhance_ad_image") as mock_enh, \
         patch("AutoMarkAi.backend.nodes.review.generate_ad_images") as mock_gen, \
         patch("AutoMarkAi.backend.nodes.review.interrupt",
               return_value={"approved": [False], "feedback": {"0": "again"}}):
        result = image_review_node({
            "image_mode": "enhance_with_ai",
            "image_path": "tests/sample_input/watch.jpg",
            "regen_count": AutoMarkAi.backend.nodes.review.MAX_REGENERATIONS_ALLOWED,
            "image_history": ["b64_0", "b64_1", "b64_2"],
            "creative_output": {
                "generated_images": ["b64_2"],
                "visual_prompt": "luxury watch on marble",
            },
        })

    assert result["review_route"] == "to_pick"
    assert mock_enh.call_count == 0
    assert mock_gen.call_count == 0
