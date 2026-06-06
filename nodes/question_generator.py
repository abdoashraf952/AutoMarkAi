"""Question generator node — vision call to produce 4 campaign-specific questions."""

import json
import logging

from langgraph.types import interrupt

from llm_client import _strip_markdown_fences, call_llm_vision
from prompts.question_generator import SYSTEM, USER_TEMPLATE

logger = logging.getLogger(__name__)

_FALLBACK_QUESTIONS = [
    "Who is the primary target customer for this product?",
    "What is the key benefit or differentiator to highlight?",
    "What tone or style should the ad convey?",
    "Are there any promotions, pricing, or offers to mention?",
]


def question_generator_node(state: dict) -> dict:
    """
    Analyze product image + goal, generate 4 targeted questions, then interrupt for user answers.

    Interrupt payload sent to UI:
        {"stage": "questions", "questions": [str, str, str, str]}

    Resume payload expected from UI:
        {"answers": {"0": str, "1": str, "2": str, "3": str}}

    State reads:  image_path, goal
    State writes: questions (list[str]), user_answers (dict)
    """
    try:
        prompt = USER_TEMPLATE.format(goal=state["goal"])
        raw = call_llm_vision(state["image_path"], prompt, SYSTEM)
        cleaned = _strip_markdown_fences(raw)
        questions: list[str] = json.loads(cleaned)

        if not isinstance(questions, list) or len(questions) != 4:
            raise ValueError(f"Expected list of 4 questions, got: {questions}")
        questions = [str(q) for q in questions]
        logger.info("question_generator_node produced %d questions", len(questions))

    except Exception as e:
        logger.warning("question_generator_node failed (%s) — using fallback questions", e)
        questions = _FALLBACK_QUESTIONS

    # Pause execution and wait for user to answer the 4 questions
    user_response = interrupt({"stage": "questions", "questions": questions})
    user_answers: dict = user_response.get("answers", {})

    return {
        "questions": questions,
        "user_answers": user_answers,
        "errors": [],
    }
