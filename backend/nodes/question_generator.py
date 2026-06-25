"""Adaptive question generator.

Instead of generating all questions up front, this asks them as a real interview:
generate ONE question (grounded in the image + everything asked & answered so far),
wait for the answer, then generate the NEXT question informed by that answer — and
so on, until NUM_QUESTIONS are answered.

Implemented as two graph nodes so the (Gemini vision) generation never replays on
resume — same pattern as the review nodes:

    question_gen_node  → generates the next question (LLM side effect, no interrupt)
    question_ask_node  → interrupts to collect that answer (interrupt, no side effect)
    route_after_answer → loop back to gen until NUM_QUESTIONS answered, then orchestrator
"""

import logging
import os

from langgraph.types import interrupt

from AutoMarkAi.backend.llm_client import _parse_json_with_retry, _strip_markdown_fences, call_llm_vision
from AutoMarkAi.backend.i18n import get_question_prompts

logger = logging.getLogger(__name__)

NUM_QUESTIONS = int(os.getenv("NUM_QUESTIONS", "4"))


def _build_qa_context(questions: list, answers: dict, language: str) -> str:
    """Render the conversation so far so the next question can build on it."""
    completed = len(answers)
    if completed == 0:
        return (
            "(this is the first question — nothing has been asked yet)"
            if language != "ar"
            else "(دي أول سؤال — لسه مفيش حاجة اتسألت)"
        )
    header = "Conversation so far:" if language != "ar" else "المحادثة لحد دلوقتي:"
    lines = [header]
    for i in range(completed):
        q = questions[i] if i < len(questions) else ""
        a = answers.get(str(i), answers.get(i, ""))
        lines.append(f"Q{i + 1}: {q}")
        lines.append(f"A{i + 1}: {a}")
    return "\n".join(lines)


def _parse_question(raw: str, fallback: str) -> str:
    """Extract a single question string from the model output, robustly."""
    try:
        parsed = _parse_json_with_retry(raw)
        if isinstance(parsed, dict):
            q = parsed.get("question") or parsed.get("q")
            if q:
                return str(q).strip()
        if isinstance(parsed, list) and parsed:
            return str(parsed[0]).strip()
    except Exception:
        pass
    for line in _strip_markdown_fences(raw).splitlines():
        s = line.strip().strip('"').strip()
        if s:
            return s
    return fallback


def question_gen_node(state: dict) -> dict:
    """
    Generate the NEXT question (index = number already answered), grounded in the
    image + the prior Q&A. Uses Gemini vision. No interrupt → never replayed.

    State reads:  image_path, goal, language, marketing_type, questions, user_answers
    State writes: questions (appends one)
    """
    language = state.get("language", "en")
    marketing_type = state.get("marketing_type", "product")
    system, user_template, fallback = get_question_prompts(language, marketing_type)

    questions = list(state.get("questions") or [])
    answers = state.get("user_answers") or {}
    index = len(answers)  # 0-based index of the question we're about to produce

    if fallback:
        fb = fallback[index] if index < len(fallback) else fallback[-1]
    else:
        fb = "Tell me more about what makes this special."

    try:
        prompt = user_template.format(
            goal=state.get("goal", ""),
            qa_context=_build_qa_context(questions, answers, language),
            index=index + 1,
            total=NUM_QUESTIONS,
        )
        raw = call_llm_vision(state["image_path"], prompt, system)
        question = _parse_question(raw, fb)
    except Exception as e:
        logger.warning("question_gen_node failed (%s) — using fallback question", e)
        question = fb

    # Overwrite the slot for this index (defensive against any re-run).
    questions = questions[:index]
    questions.append(question)
    logger.info("question_gen_node produced Q%d/%d (lang=%s)", index + 1, NUM_QUESTIONS, language)
    return {"questions": questions}


def question_ask_node(state: dict) -> dict:
    """
    Interrupt to collect the answer for the latest generated question.

    Interrupt payload: {"stage": "questions", "question": str, "index": int, "total": int}
    Resume payload:    {"answer": str}

    State reads:  questions, user_answers
    State writes: user_answers (adds one)
    """
    questions = list(state.get("questions") or [])
    answers = dict(state.get("user_answers") or {})
    index = len(answers)
    question = questions[index] if index < len(questions) else (questions[-1] if questions else "")

    result = interrupt({
        "stage": "questions",
        "question": question,
        "index": index,
        "total": NUM_QUESTIONS,
    })

    answer = result.get("answer", "") if isinstance(result, dict) else str(result)
    answers[str(index)] = answer
    logger.info("question_ask_node collected answer %d/%d", index + 1, NUM_QUESTIONS)
    return {"user_answers": answers, "errors": []}


def route_after_answer(state: dict) -> str:
    """Loop back for another question until NUM_QUESTIONS are answered."""
    answers = state.get("user_answers") or {}
    if len(answers) >= NUM_QUESTIONS:
        return "orchestrator_node"
    return "question_gen_node"
