"""Campaign-target + real estate interview (CHANGE 3).

Flow (all generation happens in non-interrupting nodes so it never replays on
resume — same checkpoint-safe pattern as the review nodes):

    target_gen_node    → analyse the units, produce RANKED campaign-target
                         options (one recommended). No interrupt.
    target_ask_node    → interrupt to let the user pick a target; stores the
                         chosen goal as state["goal"].
    question_gen_node  → decide what to ask next: the next FIXED interview
                         question, an optional LLM follow-up, or done.
    question_ask_node  → interrupt to collect that answer and store it.
    route_after_gen    → ask another question or move on to the orchestrator.

The interview alternates a curated FIXED_QUESTIONS list with at most one
LLM-generated follow-up after each fixed question (the follow-up only fires when
the user's answer was vague/incomplete or revealed something worth exploring).
"""

import logging
import os

from langgraph.types import interrupt

from AutoMarkAi.backend.llm_client import (
    _parse_json_with_retry,
    analyze_visual,
    call_llm,
)
from AutoMarkAi.backend.i18n import get_question_prompts, get_target_prompts
from AutoMarkAi.backend.real_estate_utils import get_price_tier

logger = logging.getLogger(__name__)

# Follow-ups can be globally disabled for a faster, fully-scripted interview.
ENABLE_FOLLOW_UPS = os.getenv("ENABLE_FOLLOW_UPS", "true").lower() == "true"


# ------------------------------------------------------------------ #
# Curated fixed interview (CHANGE 3)                                  #
# ------------------------------------------------------------------ #
FIXED_QUESTIONS = [
    # ---------------------------------------------------------------- #
    # 1. Advertiser type — affects copy voice, trust signals, license  #
    # ---------------------------------------------------------------- #
    {
        "key": "advertiser_type",
        "data_field": "advertiser_type",
        "type": "single_select_with_other",
        "question_en": "Who's advertising — a developer, brokerage, or individual agent?",
        "question_ar": "بتعلن لصالح مين؟",
        "options_en": [
            {"label": "Real Estate Developer", "value": "developer"},
            {"label": "Brokerage / Sales Office", "value": "brokerage"},
            {"label": "Individual Agent", "value": "agent"},
        ],
        "options_ar": [
            {"label": "مطور عقاري", "value": "developer"},
            {"label": "شركة وساطة / مكتب مبيعات", "value": "brokerage"},
            {"label": "وكيل منفرد", "value": "agent"},
        ],
        "recommended": "developer",
    },
    # ---------------------------------------------------------------- #
    # 2. Compound / project name                                       #
    # ---------------------------------------------------------------- #
    {
        "key": "compound_name",
        "data_field": "compound_name",
        "type": "free_text",
        "question_en": "What's the name of the compound or project you're advertising?",
        "question_ar": "إيه اسم الكمبوند أو المشروع اللي عايز تعلن عنه؟",
        "options_en": None,
        "options_ar": None,
        "recommended": None,
    },
    # ---------------------------------------------------------------- #
    # 3. Location — drives geo-radius targeting                        #
    # ---------------------------------------------------------------- #
    {
        "key": "location",
        "data_field": "location",
        "type": "single_select_with_other",
        "question_en": "Where is it located?",
        "question_ar": "فين موقعه؟",
        "options_en": [
            {"label": "New Cairo", "value": "new_cairo"},
            {"label": "6th of October", "value": "6th_october"},
            {"label": "Sheikh Zayed", "value": "sheikh_zayed"},
            {"label": "North Coast", "value": "north_coast"},
            {"label": "New Administrative Capital", "value": "new_capital"},
            {"label": "Ain Sokhna", "value": "ain_sokhna"},
            {"label": "Mostakbal City", "value": "mostakbal_city"},
        ],
        "options_ar": [
            {"label": "القاهرة الجديدة", "value": "new_cairo"},
            {"label": "٦ أكتوبر", "value": "6th_october"},
            {"label": "الشيخ زايد", "value": "sheikh_zayed"},
            {"label": "الساحل الشمالي", "value": "north_coast"},
            {"label": "العاصمة الإدارية الجديدة", "value": "new_capital"},
            {"label": "العين السخنة", "value": "ain_sokhna"},
            {"label": "مدينة المستقبل", "value": "mostakbal_city"},
        ],
        "recommended": None,
    },
    # ---------------------------------------------------------------- #
    # 4. Unit types — creative + audience framing                      #
    # ---------------------------------------------------------------- #
    {
        "key": "unit_types",
        "data_field": "unit_types",
        "type": "multi_select_with_other",
        "question_en": "What types of units are available?",
        "question_ar": "إيه أنواع الوحدات المتاحة؟",
        "options_en": [
            {"label": "Apartment", "value": "apartment"},
            {"label": "Villa", "value": "villa"},
            {"label": "Duplex", "value": "duplex"},
            {"label": "Townhouse", "value": "townhouse"},
            {"label": "Twin House", "value": "twin_house"},
            {"label": "Penthouse", "value": "penthouse"},
            {"label": "Studio", "value": "studio"},
            {"label": "Chalet", "value": "chalet"},
        ],
        "options_ar": [
            {"label": "شقة", "value": "apartment"},
            {"label": "فيلا", "value": "villa"},
            {"label": "دوبلكس", "value": "duplex"},
            {"label": "تاون هاوس", "value": "townhouse"},
            {"label": "توين هاوس", "value": "twin_house"},
            {"label": "بنتهاوس", "value": "penthouse"},
            {"label": "استوديو", "value": "studio"},
            {"label": "شاليه", "value": "chalet"},
        ],
        "recommended": None,
    },
    # ---------------------------------------------------------------- #
    # 5. Delivery status — urgency angle, payment framing              #
    # ---------------------------------------------------------------- #
    {
        "key": "unit_status",
        "data_field": "unit_status",
        "type": "single_select_with_other",
        "question_en": "Are the units off-plan (under construction) or ready to move in?",
        "question_ar": "الوحدات تحت الإنشاء (أوف بلان) ولا جاهزة للاستلام؟",
        "options_en": [
            {"label": "Off-Plan (Under Construction)", "value": "off_plan"},
            {"label": "Ready to Move In", "value": "ready"},
            {"label": "Partially Delivered", "value": "partial"},
        ],
        "options_ar": [
            {"label": "تحت الإنشاء (أوف بلان)", "value": "off_plan"},
            {"label": "جاهزة للاستلام", "value": "ready"},
            {"label": "تسليم جزئي", "value": "partial"},
        ],
        "recommended": None,
    },
    # ---------------------------------------------------------------- #
    # 6. Starting price — drives price-tier smart defaults             #
    # ---------------------------------------------------------------- #
    {
        "key": "starting_price",
        "data_field": "starting_price",
        "type": "free_text",
        "question_en": "What's the starting price? (in EGP)",
        "question_ar": "إيه أقل سعر؟ (بالجنيه المصري)",
        "options_en": None,
        "options_ar": None,
        "recommended": None,
    },
    # ---------------------------------------------------------------- #
    # 7. Payment plan — the #1 hook in Egyptian real estate            #
    # ---------------------------------------------------------------- #
    {
        "key": "payment_plan",
        "data_field": "payment_plan",
        "type": "free_text",
        "question_en": "What are the payment terms? (e.g. 10% down, 8 years, delivery 2027)",
        "question_ar": "إيه نظام السداد؟ (مثلاً: مقدم ١٠٪، تقسيط ٨ سنين، استلام ٢٠٢٧)",
        "options_en": None,
        "options_ar": None,
        "recommended": None,
    },
    # ---------------------------------------------------------------- #
    # 8. Amenities — the message-match that does the targeting         #
    # ---------------------------------------------------------------- #
    {
        "key": "amenities",
        "data_field": "amenities",
        "type": "multi_select_with_other",
        "question_en": "What amenities and features does the compound offer?",
        "question_ar": "إيه الخدمات والمميزات اللي بيوفرها الكمبوند؟",
        "options_en": [
            {"label": "Swimming Pool", "value": "pool"},
            {"label": "Gym & Fitness Club", "value": "gym"},
            {"label": "Clubhouse", "value": "clubhouse"},
            {"label": "Gated Security", "value": "security"},
            {"label": "Underground Parking", "value": "parking"},
            {"label": "International School", "value": "school"},
            {"label": "Commercial Area", "value": "commercial"},
            {"label": "Green Spaces & Landscapes", "value": "green"},
            {"label": "Kids' Area", "value": "kids"},
            {"label": "Sports Courts", "value": "sports"},
        ],
        "options_ar": [
            {"label": "حمام سباحة", "value": "pool"},
            {"label": "جيم ونادي رياضي", "value": "gym"},
            {"label": "كلوب هاوس", "value": "clubhouse"},
            {"label": "أمن وبوابات", "value": "security"},
            {"label": "جراج أرضي", "value": "parking"},
            {"label": "مدرسة دولية", "value": "school"},
            {"label": "منطقة تجارية", "value": "commercial"},
            {"label": "مساحات خضراء وحدائق", "value": "green"},
            {"label": "منطقة أطفال", "value": "kids"},
            {"label": "ملاعب رياضية", "value": "sports"},
        ],
        "recommended": None,
    },
    # ---------------------------------------------------------------- #
    # 9. Target buyer — angle + tone, cross-checked against price tier #
    # ---------------------------------------------------------------- #
    {
        "key": "target_buyer",
        "data_field": "target_buyer",
        "type": "single_select_with_other",
        "question_en": "Who is the main buyer you're targeting?",
        "question_ar": "مين المشتري اللي بتستهدفه؟",
        "options_en": [
            {"label": "End-User (Owner-Occupier)", "value": "end_user"},
            {"label": "Real Estate Investor", "value": "investor"},
            {"label": "First-Time Buyer", "value": "first_time"},
            {"label": "Upgrader (Moving to Better Home)", "value": "upgrader"},
        ],
        "options_ar": [
            {"label": "مستخدم نهائي (سكن)", "value": "end_user"},
            {"label": "مستثمر عقاري", "value": "investor"},
            {"label": "مشتري لأول مرة", "value": "first_time"},
            {"label": "محسّن السكن (انتقال لأحسن)", "value": "upgrader"},
        ],
        "recommended": "end_user",
    },
    # ---------------------------------------------------------------- #
    # 10. Offer / promotion — the lead magnet                          #
    # ---------------------------------------------------------------- #
    {
        "key": "offer",
        "data_field": "offer",
        "type": "single_select_with_other",
        "question_en": "Do you currently have a special offer running?",
        "question_ar": "عندك عرض حالي؟",
        "options_en": [
            {"label": "5% Down Payment", "value": "5_percent_down"},
            {"label": "Zero Down Payment", "value": "zero_down"},
            {"label": "Limited Units Available", "value": "limited_units"},
            {"label": "Free Club Membership", "value": "free_membership"},
            {"label": "Discount on Cash", "value": "cash_discount"},
            {"label": "Furnished Units", "value": "furnished"},
            {"label": "No current offer", "value": "no_offer"},
        ],
        "options_ar": [
            {"label": "مقدم ٥٪", "value": "5_percent_down"},
            {"label": "بدون مقدم", "value": "zero_down"},
            {"label": "وحدات محدودة", "value": "limited_units"},
            {"label": "عضوية نادي مجانية", "value": "free_membership"},
            {"label": "خصم على الكاش", "value": "cash_discount"},
            {"label": "وحدات مفروشة", "value": "furnished"},
            {"label": "مفيش عرض حالياً", "value": "no_offer"},
        ],
        "recommended": None,
    },
    # ---------------------------------------------------------------- #
    # 11. Lead destination — conversion location                       #
    # ---------------------------------------------------------------- #
    {
        "key": "lead_destination",
        "data_field": "lead_destination",
        "type": "single_select_with_other",
        "question_en": "Where should interested people reach you?",
        "question_ar": "العميل المهتم يتواصل معاك إزاي؟",
        "options_en": [
            {"label": "WhatsApp", "value": "whatsapp"},
            {"label": "Phone Call", "value": "phone"},
            {"label": "Facebook Instant Form", "value": "instant_form"},
            {"label": "Landing Page", "value": "landing_page"},
        ],
        "options_ar": [
            {"label": "واتساب", "value": "whatsapp"},
            {"label": "مكالمة تليفون", "value": "phone"},
            {"label": "فورم فيسبوك", "value": "instant_form"},
            {"label": "صفحة هبوط", "value": "landing_page"},
        ],
        "recommended": "whatsapp",
    },
    # ---------------------------------------------------------------- #
    # 12. Campaign duration — daily budget = total ÷ duration          #
    # ---------------------------------------------------------------- #
    {
        "key": "campaign_duration",
        "data_field": "campaign_duration",
        "type": "single_select_with_other",
        "question_en": "How long should the campaign run?",
        "question_ar": "الحملة تشتغل لمدة قد إيه؟",
        "options_en": [
            {"label": "1 week", "value": "7"},
            {"label": "2 weeks", "value": "14"},
            {"label": "1 month", "value": "30"},
            {"label": "3 months", "value": "90"},
        ],
        "options_ar": [
            {"label": "أسبوع", "value": "7"},
            {"label": "أسبوعين", "value": "14"},
            {"label": "شهر", "value": "30"},
            {"label": "٣ شهور", "value": "90"},
        ],
        "recommended": "14",
    },
]

TOTAL_FIXED = len(FIXED_QUESTIONS)


def _first_image(state: dict) -> str | None:
    paths = state.get("image_paths") or []
    return paths[0] if paths else None


# ------------------------------------------------------------------ #
# Campaign target — the one fixed question (asked first)              #
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
    if clean and not any(o["recommended"] for o in clean):
        clean[0]["recommended"] = True
    return clean


def target_gen_node(state: dict) -> dict:
    """Produce ranked campaign-target options. No interrupt → never replayed."""
    language = state.get("language", "en")
    marketing_type = state.get("marketing_type", "real_estate")
    system, user_template, fallback = get_target_prompts(language, marketing_type)

    options: list[dict] = []
    try:
        prompt = user_template.format(budget=state.get("budget", 0))
        raw = analyze_visual(_first_image(state), prompt, system)
        options = _normalize_options(_parse_json_with_retry(raw))
    except Exception as e:
        logger.warning("target_gen_node failed (%s) — using fallback options", e)

    if not options:
        options = [dict(o) for o in fallback]

    logger.info("target_gen_node produced %d campaign-target options", len(options))
    return {"campaign_target_options": options}


def target_ask_node(state: dict) -> dict:
    """Interrupt so the user picks a campaign target; store it as the goal.

    In 'guided' or 'autopilot' approval_mode the recommended option is
    auto-selected without interrupting the user (fewer stops per the DoD).
    In 'full_manual' mode (the default) it behaves exactly as before.
    """
    options = list(state.get("campaign_target_options") or [])
    mode = state.get("approval_mode", "full_manual")

    if mode in ("guided", "autopilot"):
        # Auto-pick the recommended option; no interrupt needed.
        rec = next((o for o in options if o.get("recommended")), options[0] if options else None)
        goal = (rec.get("goal", "") if rec else "").strip()
        logger.info("target_ask_node: auto-selected goal (approval_mode=%s): %s", mode, goal)
        return {"goal": goal, "errors": []}

    result = interrupt({"stage": "campaign_target", "options": options})

    if isinstance(result, dict):
        goal = result.get("goal") or result.get("answer") or ""
    else:
        goal = str(result)
    goal = (goal or "").strip()
    if not goal and options:
        rec = next((o for o in options if o.get("recommended")), options[0])
        goal = rec.get("goal", "")

    logger.info("target_ask_node stored campaign goal")
    return {"goal": goal, "errors": []}


# ------------------------------------------------------------------ #
# Real estate interview — fixed questions + LLM follow-ups            #
# ------------------------------------------------------------------ #
def _localized(q: dict, language: str) -> tuple[str, list | None]:
    """Return (question_text, options) for the active language."""
    if language == "ar":
        return q["question_ar"], q.get("options_ar")
    return q["question_en"], q.get("options_en")


def _build_fixed_payload(q: dict, idx: int, language: str, state: dict) -> dict:
    """Build the interrupt payload for a fixed question at index `idx`."""
    question_text, raw_options = _localized(q, language)

    # Price-tier smart default may override the recommended offer (CHANGE 8).
    recommended = q.get("recommended")
    if q["key"] == "offer":
        starting = (state.get("real_estate_data") or {}).get("starting_price")
        if starting:
            recommended = get_price_tier(starting).get("recommended_offer", recommended)

    options = None
    if raw_options:
        options = [
            {"label": o["label"], "value": o["value"], "recommended": o["value"] == recommended}
            for o in raw_options
        ]

    return {
        "stage": "questions",
        "question": question_text,
        "question_type": q["type"],
        "options": options,
        "allow_other": True,
        "index": idx,
        "total_fixed": TOTAL_FIXED,
        "is_follow_up": False,
        "data_field": q["data_field"],
        "key": q["key"],
    }


def _build_follow_up_payload(question_text: str, idx: int) -> dict:
    return {
        "stage": "questions",
        "question": question_text,
        "question_type": "free_text",
        "options": None,
        "allow_other": True,
        "index": idx,
        "total_fixed": TOTAL_FIXED,
        "is_follow_up": True,
        "data_field": None,
        "key": "follow_up",
    }


def _qa_context(state: dict) -> str:
    """Render the interview so far for the follow-up decision LLM."""
    data = state.get("real_estate_data") or {}
    follow_ups = state.get("follow_up_log") or []
    if not data and not follow_ups:
        return "(no answers yet)"
    lines = []
    for k, v in data.items():
        lines.append(f"- {k}: {v}")
    for fu in follow_ups:
        lines.append(f"- follow-up Q: {fu.get('q')} → {fu.get('a')}")
    return "\n".join(lines)


def _decide_follow_up(state: dict, topic: str, language: str) -> str:
    """Ask the LLM whether one short follow-up adds value. Returns the question
    text, or "" when no follow-up is warranted."""
    if not ENABLE_FOLLOW_UPS:
        return ""
    system, user_template, _ = get_question_prompts(language, state.get("marketing_type", "real_estate"))
    try:
        prompt = user_template.format(qa_context=_qa_context(state), topic=topic)
        raw, _ = call_llm(prompt, system, "follow_up", allow_fallback=True)
        parsed = _parse_json_with_retry(raw)
        if isinstance(parsed, dict) and parsed.get("follow_up"):
            q = str(parsed.get("question") or "").strip()
            return q
    except Exception as e:
        logger.warning("_decide_follow_up failed (%s) — skipping follow-up", e)
    return ""


def question_gen_node(state: dict) -> dict:
    """Decide the next question (fixed / follow-up / done). No interrupt."""
    language = state.get("language", "en")
    fixed_idx = state.get("current_fixed_q_index", 0)

    # First entry into the interview → present the first fixed question.
    if not state.get("pending_answered"):
        payload = _build_fixed_payload(FIXED_QUESTIONS[0], 0, language, state)
        return {
            "pending_question": payload,
            "current_fixed_q_index": 0,
            "is_follow_up": False,
            "pending_answered": False,
            "questions_done": False,
        }

    # An answer just came in.
    if state.get("last_answer_was_follow_up"):
        # We already inserted a follow-up for this topic → advance to next fixed.
        next_idx = fixed_idx + 1
    else:
        # Just answered a fixed question → maybe insert one follow-up.
        topic = FIXED_QUESTIONS[fixed_idx]["key"] if fixed_idx < TOTAL_FIXED else ""
        follow_up_q = _decide_follow_up(state, topic, language)
        if follow_up_q:
            payload = _build_follow_up_payload(follow_up_q, fixed_idx)
            logger.info("question_gen_node: inserting follow-up after '%s'", topic)
            return {
                "pending_question": payload,
                "is_follow_up": True,
                "pending_answered": False,
                "questions_done": False,
            }
        next_idx = fixed_idx + 1

    if next_idx >= TOTAL_FIXED:
        logger.info("question_gen_node: interview complete (%d fixed questions)", TOTAL_FIXED)
        return {"questions_done": True}

    payload = _build_fixed_payload(FIXED_QUESTIONS[next_idx], next_idx, language, state)
    logger.info("question_gen_node: presenting fixed question %d/%d", next_idx + 1, TOTAL_FIXED)
    return {
        "pending_question": payload,
        "current_fixed_q_index": next_idx,
        "is_follow_up": False,
        "pending_answered": False,
        "questions_done": False,
    }


def _value_for(answer: str, options: list | None) -> str | None:
    """Map a chosen label back to its option value (None if no match)."""
    if not options:
        return None
    for o in options:
        if o.get("label") == answer or o.get("value") == answer:
            return o.get("value")
    return None


def _parse_int(text: str, default: int) -> int:
    digits = "".join(ch for ch in str(text) if ch.isdigit())
    return int(digits) if digits else default


def question_ask_node(state: dict) -> dict:
    """Interrupt to collect the answer for the pending question and store it."""
    pending = dict(state.get("pending_question") or {})
    result = interrupt(pending)

    if isinstance(result, dict):
        answer = result.get("answer", "")
    else:
        answer = str(result)
    answer = (answer or "").strip()

    updates: dict = {"pending_answered": True, "errors": []}

    if pending.get("is_follow_up"):
        log = list(state.get("follow_up_log") or [])
        log.append({"q": pending.get("question", ""), "a": answer})
        updates["follow_up_log"] = log
        updates["last_answer_was_follow_up"] = True
        logger.info("question_ask_node: stored follow-up answer")
        return updates

    # Fixed question → store into real_estate_data + derive machine fields.
    data = dict(state.get("real_estate_data") or {})
    data_field = pending.get("data_field")
    if data_field:
        data[data_field] = answer
    updates["real_estate_data"] = data
    updates["last_answer_was_follow_up"] = False

    key = pending.get("key")
    options = pending.get("options")
    if key == "campaign_duration":
        val = _value_for(answer, options)
        updates["campaign_duration_days"] = _parse_int(val or answer, 14)
    elif key == "lead_destination":
        val = _value_for(answer, options)
        updates["lead_destination"] = (val or answer or "whatsapp").lower()

    logger.info("question_ask_node: stored fixed answer for '%s'", key)
    return updates


def route_after_gen(state: dict) -> str:
    """After question_gen_node: ask the question or move on to the orchestrator."""
    if state.get("questions_done"):
        return "orchestrator_node"
    return "question_ask_node"
