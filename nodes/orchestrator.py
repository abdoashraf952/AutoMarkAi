"""Orchestrator node — vision analysis via Gemini, produces campaign_plan."""

import logging

from llm_client import _parse_json_with_retry, call_llm_vision
from prompts.orchestrator import SYSTEM, USER_TEMPLATE

logger = logging.getLogger(__name__)


def orchestrator_node(state: dict) -> dict:
    """
    Analyze the product image and user inputs to produce a structured campaign_plan.

    Uses Gemini multimodal (vision). No Groq fallback on this node.
    On failure, writes to errors and returns empty campaign_plan (triggers early exit in main.py).
    """
    try:
        prompt = USER_TEMPLATE.format(budget=state["budget"], goal=state["goal"])

        # Edit 2: append Q&A context from question_generator_node if available
        questions = state.get("questions") or []
        answers = state.get("user_answers") or {}
        if questions and answers:
            qa_lines = ["\n\nAdditional product context from user Q&A:"]
            for i, question in enumerate(questions):
                answer = answers.get(str(i), answers.get(i, ""))
                if answer:
                    qa_lines.append(f"Q: {question}")
                    qa_lines.append(f"A: {answer}")
            prompt += "\n".join(qa_lines)

        raw = call_llm_vision(state["image_path"], prompt, SYSTEM)
        campaign_plan = _parse_json_with_retry(raw)
        logger.info("orchestrator_node produced campaign_plan: %s", campaign_plan)
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
