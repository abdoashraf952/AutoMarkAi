"""Campaign-target + adaptive question interview.

Flow (all generation happens in non-interrupting nodes so it never replays on
resume — same pattern as the review nodes):

    target_gen_node    → analyse the product, produce RANKED campaign-target
                         options (one recommended). No interrupt.
    target_ask_node    → interrupt to let the user pick a target; stores the
                         chosen goal as state["goal"]. (The campaign target is
                         the one FIXED question, always asked first — Edit 2/5.)
    question_gen_node  → decide whether one more adaptive question adds value and,
                         if so, generate it. No interrupt. Routes "ask" / "done".
    question_ask_node  → interrupt to collect that answer.
    route_after_gen    → ask another question or move on to orchestrator.

The number of adaptive questions is dynamic (Edit 5): the model asks basic
questions first and only adds follow-ups when they help, bounded by
MIN_QUESTIONS/MAX_QUESTIONS (which include the fixed campaign-target question).
"""

import logging
import os

from langgraph.types import interrupt

from AutoMarkAi.backend.llm_client import (
    _parse_json_with_retry,
    _strip_markdown_fences,
    analyze_visual,
)
from AutoMarkAi.backend.i18n import get_question_prompts, get_target_prompts

logger = logging.getLogger(__name__)

# Allowed total-question range (the campaign-target question counts as one).
MIN_QUESTIONS = int(os.getenv("MIN_QUESTIONS", "4"))
MAX_QUESTIONS = int(os.getenv("MAX_QUESTIONS", "10"))

# Adaptive follow-ups asked AFTER the fixed campaign-target question.
_MIN_ADAPTIVE = max(0, MIN_QUESTIONS - 1)
_MAX_ADAPTIVE = max(_MIN_ADAPTIVE, MAX_QUESTIONS - 1)


# ------------------------------------------------------------------ #
# Campaign target — the one fixed question (Edit 2)                   #
# ------------------------------------------------------------------ #
def _normalize_options(parsed) -> list[dict]:
    """Coerce the model output into a clean list of target option dicts."""
    options = parsed.get("options") if isinstance(parsed, dict) else parsed
    if not isinstance(options, list):
        return []
    clean: list[dict] = []
    for opt in options:
        if not isinstance(opt, dict):
            continue
        label = str(opt.get("label", "")).strip()
        if not label:
            continue
        clean.append({
            "label": label,
            "description": str(opt.get("description", "")).strip(),
            "goal": str(opt.get("goal") or opt.get("description") or label).strip(),
            "recommended": bool(opt.get("recommended", False)),
        })
    # Guarantee exactly one recommended option (default to the first / best).
    if clean and not any(o["recommended"] for o in clean):
        clean[0]["recommended"] = True
    return clean


def target_gen_node(state: dict) -> dict:
    """Produce ranked campaign-target options. No interrupt → never replayed.

    State reads:  image_path, budget, language, marketing_type
    State writes: campaign_target_options
    """
    language = state.get("language", "en")
    marketing_type = state.get("marketing_type", "product")
    system, user_template, fallback = get_target_prompts(language, marketing_type)

    options: list[dict] = []
    try:
        prompt = user_template.format(budget=state.get("budget", 0))
        raw = analyze_visual(
            state.get("image_path"), prompt, system,
            description=state.get("product_description"),
        )
        options = _normalize_options(_parse_json_with_retry(raw))
    except Exception as e:
        logger.warning("target_gen_node failed (%s) — using fallback options", e)

    if not options:
        options = [dict(o) for o in fallback]

    logger.info("target_gen_node produced %d campaign-target options", len(options))
    return {"campaign_target_options": options}


def target_ask_node(state: dict) -> dict:
    """Interrupt so the user picks a campaign target; store it as the goal.

    Interrupt payload: {"stage": "campaign_target", "options": [...]}
    Resume payload:    {"answer": "<chosen goal sentence>"}  (or {"goal": ...})

    State reads:  campaign_target_options
    State writes: goal
    """
    options = list(state.get("campaign_target_options") or [])
    result = interrupt({
        "stage": "campaign_target",
        "options": options,
    })

    if isinstance(result, dict):
        goal = result.get("goal") or result.get("answer") or ""
    else:
        goal = str(result)
    goal = (goal or "").strip()
    if not goal and options:
        # Fall back to the recommended option's goal.
        rec = next((o for o in options if o.get("recommended")), options[0])
        goal = rec.get("goal", "")

    logger.info("target_ask_node stored campaign goal")
    return {"goal": goal, "errors": []}


# ------------------------------------------------------------------ #
# Adaptive follow-up questions — dynamic count (Edit 5)              #
# ------------------------------------------------------------------ #
def _build_qa_context(questions: list, answers: dict, language: str) -> str:
    """Render the conversation so far so the next question can build on it."""
    completed = len(answers)
    if completed == 0:
        return (
            "(no follow-up questions have been asked yet)"
            if language != "ar"
            else "(لسه مفيش أسئلة follow-up اتسألت)"
        )
    header = "Conversation so far:" if language != "ar" else "المحادثة لحد دلوقتي:"
    lines = [header]
    for i in range(completed):
        q = questions[i] if i < len(questions) else ""
        a = answers.get(str(i), answers.get(i, ""))
        lines.append(f"Q{i + 1}: {q}")
        lines.append(f"A{i + 1}: {a}")
    return "\n".join(lines)


def _parse_decision(raw: str, fallback: str) -> tuple[bool, str]:
    """Extract (done, question) from the model output, robustly."""
    try:
        parsed = _parse_json_with_retry(raw)
        if isinstance(parsed, dict):
            done = bool(parsed.get("done", False))
            q = parsed.get("question") or parsed.get("q") or ""
            return done, str(q).strip()
    except Exception:
        pass
    # No JSON — treat the first non-empty line as the question, not done.
    for line in _strip_markdown_fences(raw).splitlines():
        s = line.strip().strip('"').strip()
        if s:
            return False, s
    return False, fallback


def question_gen_node(state: dict) -> dict:
    """Decide whether to ask another adaptive question and, if so, generate it.

    No interrupt → never replayed. Routing is via route_after_gen, which reads
    the `questions_done` flag this node sets.

    State reads:  image_path, goal, language, marketing_type, questions, user_answers
    State writes: questions (appends one when asking), questions_done
    """
    language = state.get("language", "en")
    marketing_type = state.get("marketing_type", "product")
    system, user_template, fallback = get_question_prompts(language, marketing_type)

    questions = list(state.get("questions") or [])
    answers = state.get("user_answers") or {}
    answered = len(answers)  # adaptive answers collected so far

    # Hard bounds — these win over the model's preference.
    if answered >= _MAX_ADAPTIVE:
        logger.info("question_gen_node: reached max adaptive questions (%d)", answered)
        return {"questions_done": True}

    fb = (fallback[answered] if answered < len(fallback) else fallback[-1]) if fallback else (
        "Tell me more about what makes this special."
    )

    done = False
    question = fb
    try:
        prompt = user_template.format(
            goal=state.get("goal", ""),
            qa_context=_build_qa_context(questions, answers, language),
            answered=answered,
            min_q=MIN_QUESTIONS,
            max_q=MAX_QUESTIONS,
        )
        raw = analyze_visual(
            state.get("image_path"), prompt, system,
            description=state.get("product_description"),
        )
        done, parsed_q = _parse_decision(raw, fb)
        question = parsed_q or fb
    except Exception as e:
        logger.warning("question_gen_node failed (%s) — using fallback question", e)
        done, question = False, fb

    # Enforce the minimum: the model can't stop early.
    if answered < _MIN_ADAPTIVE:
        done = False

    if done:
        logger.info("question_gen_node: interview complete after %d adaptive questions", answered)
        return {"questions_done": True}

    # Overwrite the slot for this index (defensive against any re-run).
    questions = questions[:answered]
    questions.append(question)
    logger.info("question_gen_node produced adaptive Q%d (lang=%s)", answered + 1, language)
    return {"questions": questions, "questions_done": False}


def question_ask_node(state: dict) -> dict:
    """Interrupt to collect the answer for the latest generated question.

    Interrupt payload: {"stage": "questions", "question": str, "index": int,
                        "min": int, "max": int}
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
        "min": MIN_QUESTIONS,
        "max": MAX_QUESTIONS,
    })

    answer = result.get("answer", "") if isinstance(result, dict) else str(result)
    answers[str(index)] = answer
    logger.info("question_ask_node collected adaptive answer %d", index + 1)
    return {"user_answers": answers, "errors": []}


def route_after_gen(state: dict) -> str:
    """After question_gen_node: ask the question or move on to the orchestrator."""
    if state.get("questions_done"):
        return "orchestrator_node"
    return "question_ask_node"
