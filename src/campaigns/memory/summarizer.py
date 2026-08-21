"""Rolling summary generator — Phase 5.

Compresses the interview answers + campaign outcome into a short
rolling_summary string on the cheap model tier. Run once after the
interview is done (summarizer_node in pipeline_graph.py) and again
after each operate cycle to keep context small.

Runs on Gemini's cheap/fast tier — short, structured prompt so token cost
stays minimal even across weeks-long campaigns.
"""

import json
import logging

from src.campaigns.llm_client import call_llm

logger = logging.getLogger(__name__)


def _build_summary_prompt(state: dict) -> str:
    re_data = state.get("real_estate_data") or {}
    plan = state.get("campaign_plan") or {}
    decisions = state.get("decisions_log") or []
    diagnosis = state.get("latest_diagnosis") or {}

    lines = ["Summarise the following campaign session in plain English. Be concise (3–5 bullet points max).\n"]

    if re_data:
        lines.append(f"Real estate project data:\n{json.dumps(re_data, ensure_ascii=False)}\n")
    if plan.get("tone"):
        lines.append(f"Campaign tone: {plan.get('tone', '')}")
    if diagnosis.get("status"):
        lines.append(f"Latest campaign status: {diagnosis['status']}")
    if decisions:
        last = decisions[-1]
        lines.append(f"Last operate decision: {last.get('decision')} — {last.get('rationale', '')[:200]}")

    return "\n".join(lines)


def make_rolling_summary(state: dict) -> str:
    """
    Generate a 3–5 bullet rolling summary for long-term memory.

    Falls back to a structured string if the LLM call fails, so it
    never blocks the pipeline.
    """
    prompt = _build_summary_prompt(state)
    system = (
        "You are a concise note-taker. Produce 3–5 bullet points summarising "
        "the key facts about this real estate campaign session. Be factual and brief."
    )

    try:
        raw, provider = call_llm(
            prompt, system, "summarizer", allow_fallback=True, fast=True,
        )
        logger.info("summarizer: generated rolling_summary via %s", provider)
        return raw.strip()
    except Exception as e:
        logger.warning("summarizer: LLM call failed (%s); using structured fallback", e)
        re_data = state.get("real_estate_data") or {}
        compound = re_data.get("compound_name", "Unknown")
        location = re_data.get("location", "Unknown")
        price = re_data.get("starting_price", "Unknown")
        return (
            f"• Compound: {compound}\n"
            f"• Location: {location}\n"
            f"• Starting price: {price}\n"
            f"• Interview completed, campaign built."
        )
