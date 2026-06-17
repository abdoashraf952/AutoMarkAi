"""Question generator node — vision call to produce campaign-specific questions."""

import json
import logging

from langgraph.types import interrupt

from llm_client import _strip_markdown_fences, call_llm_vision
from i18n import get_question_prompts

logger = logging.getLogger(__name__)

# Minimum and maximum number of questions to accept from the LLM
_MIN_Q = 4
_MAX_Q = 8


def question_generator_node(state: dict) -> dict:
    """
    Analyze the image + goal, generate 5-6 targeted questions, then interrupt for user answers.

    The number of questions varies by marketing_type (4-8 accepted from LLM).
    Questions are generated in the user's language (en or ar, Egyptian Arabic for ar).

    Interrupt payload:  {"stage": "questions", "questions": [str, ...]}
    Resume payload:     {"answers": {"0": str, "1": str, ...}}

    State reads:  image_path, goal, marketing_type, language
    State writes: questions (list[str]), user_answers (dict)
    """
    language = state.get("language", "en")
    marketing_type = state.get("marketing_type", "product")

    system, user_template, fallback = get_question_prompts(language, marketing_type)

    try:
        prompt = user_template.format(goal=state["goal"])
        raw = call_llm_vision(state["image_path"], prompt, system)
        cleaned = _strip_markdown_fences(raw)
        questions: list[str] = json.loads(cleaned)

        if not isinstance(questions, list) or not (_MIN_Q <= len(questions) <= _MAX_Q):
            raise ValueError(
                f"Expected {_MIN_Q}–{_MAX_Q} questions, got {len(questions) if isinstance(questions, list) else type(questions)}"
            )
        questions = [str(q).strip() for q in questions if str(q).strip()]
        logger.info("question_generator_node produced %d questions (lang=%s type=%s)", len(questions), language, marketing_type)

    except Exception as e:
        logger.warning("question_generator_node failed (%s) — using fallback questions", e)
        questions = fallback

    user_response = interrupt({"stage": "questions", "questions": questions})
    user_answers: dict = user_response.get("answers", {})

    return {
        "questions": questions,
        "user_answers": user_answers,
        "errors": [],
    }
