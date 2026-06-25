"""Orchestrator node — vision analysis via Gemini, produces campaign_plan."""

import logging

from llm_client import _parse_json_with_retry, call_llm_vision
from i18n import get_orchestrator_prompts

logger = logging.getLogger(__name__)


def orchestrator_node(state: dict) -> dict:
    """
    Analyze the product/business/service image and user inputs to produce campaign_plan.

    Uses Gemini's multimodal (vision) model. On failure, writes to errors and
    returns an empty campaign_plan.

    State reads:  image_path, budget, goal, marketing_type, language, questions, user_answers
    State writes: campaign_plan, llm_used, errors
    """
    language = state.get("language", "en")
    marketing_type = state.get("marketing_type", "product")

    system, user_template = get_orchestrator_prompts(language, marketing_type)

    try:
        # Build Q&A context block from question_generator_node
        questions = state.get("questions") or []
        answers = state.get("user_answers") or {}
        qa_context = ""
        if questions and answers:
            lines = ["Additional context from user Q&A:\n"]
            for i, question in enumerate(questions):
                answer = answers.get(str(i), answers.get(i, ""))
                if answer:
                    lines.append(f"Q: {question}")
                    lines.append(f"A: {answer}\n")
            qa_context = "\n".join(lines) + "\n"

        prompt = user_template.format(
            budget=state["budget"],
            goal=state["goal"],
            qa_context=qa_context,
        )

        raw = call_llm_vision(state["image_path"], prompt, system)
        campaign_plan = _parse_json_with_retry(raw)

        # Inject language and marketing_type into the plan so downstream nodes can use them
        campaign_plan["language"] = language
        campaign_plan["marketing_type"] = marketing_type

        logger.info("orchestrator_node produced campaign_plan (lang=%s type=%s)", language, marketing_type)
        return {
            "campaign_plan": campaign_plan,
            "llm_used": {"orchestrator": "gemini"},
            "errors": [],
        }
    except Exception as e:
        logger.error("orchestrator_node failed: %s", e)
        return {
            "campaign_plan": {},
            "errors": [f"orchestrator_node failed: {e}"],
        }
