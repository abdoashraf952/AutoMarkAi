"""English question-generator prompts — real estate.

Two prompt families live here:

1. CAMPAIGN TARGET (the one fixed question, always asked first) — the model
   analyses the real estate project and returns a ranked, multiple-choice list
   of campaign goals with exactly one marked recommended.

2. FOLLOW-UP DECISION — after each fixed interview answer, the model decides
   whether ONE short follow-up question would add value before the next topic.

Since marketing_type is always "real_estate", every export is a plain string
(no longer a dict keyed by marketing_type).
"""

# ------------------------------------------------------------------ #
# 1. Campaign target — ranked multiple-choice                         #
# ------------------------------------------------------------------ #
TARGET_SYSTEM = (
    "You help an Egyptian real estate agency choose the single best GOAL for a "
    "Meta ad campaign promoting a compound/project.\n"
    "You will receive photos of the units and the budget.\n"
    "Return a ranked, multiple-choice list of campaign goals, BEST first.\n"
    "Choose from these real-estate goal types (plain language, no jargon):\n"
    "  - Lead Generation (people leave their phone/WhatsApp for the sales team)\n"
    "  - Brand Awareness (more people discover the compound and its features)\n"
    "  - Website Traffic (people visit a page to see units, prices, and details)\n"
    "  - Project Launch Event (people register for a launch, site visit, or open house)\n"
    "Pick the 4 most relevant for THIS project, ranked by what will work best.\n"
    "Mark EXACTLY ONE as recommended (the strongest fit, ranked first — usually "
    "Lead Generation for Egyptian real estate).\n"
    "Return ONLY this JSON (no markdown, no extra text):\n"
    "{{\n"
    '  "options": [\n'
    '    {{"label": "<short friendly goal name>", "description": "<one plain sentence on what happens>", '
    '"goal": "<a natural-language campaign goal sentence to feed the planner>", "recommended": true}},\n'
    "    ... 4 options total, ranked best first, exactly one recommended ...\n"
    "  ]\n"
    "}}"
)

TARGET_USER_TEMPLATE = (
    "Budget: ${budget}\n\n"
    "Analyse the unit photos and recommend the best campaign goal. "
    "Return ONLY the ranked JSON options described in the system message."
)

# Index-aligned fallback if the model fails. Best/recommended first.
TARGET_FALLBACK_OPTIONS = [
    {"label": "Lead Generation", "description": "People leave their phone number or WhatsApp to be contacted by your sales team.",
     "goal": "generate qualified leads for the real estate project", "recommended": True},
    {"label": "Brand Awareness", "description": "More people learn about your compound and its unique features.",
     "goal": "build awareness for the compound so more people know about it", "recommended": False},
    {"label": "Website Traffic", "description": "People visit your website or landing page to see unit details and pricing.",
     "goal": "drive traffic to the project page for detailed information", "recommended": False},
    {"label": "Project Launch Event", "description": "People register for a launch event, site visit, or open house.",
     "goal": "get registrations for the project launch event or site visit", "recommended": False},
]

# ------------------------------------------------------------------ #
# 2. Follow-up decision — one optional question after a fixed answer  #
# ------------------------------------------------------------------ #
FOLLOW_UP_SYSTEM = (
    "You are a real estate media buyer assistant. You've been collecting information "
    "about a real estate compound to create a Meta ad campaign. After the user answered "
    "the latest question, decide if ONE quick follow-up question would add meaningful "
    "value before moving to the next topic.\n"
    "Rules:\n"
    "- Only ask a follow-up if the user's answer was vague, incomplete, or revealed "
    "something worth exploring (e.g. they mentioned construction status, a unique feature, etc.).\n"
    "- The follow-up must be SHORT, specific, and easy to answer.\n"
    "- Do NOT ask a follow-up just for the sake of it — brevity is respected.\n"
    "- Never ask about marketing jargon (CPL, CTR, ROAS, etc.).\n"
    "- Never repeat information already known from previous answers.\n"
    'Return ONLY this JSON: {{"follow_up": true|false, "question": "<follow-up question or empty>"}}\n'
    "If follow_up is false, question must be an empty string."
)

FOLLOW_UP_USER_TEMPLATE = (
    "Conversation so far (real estate interview):\n"
    "{qa_context}\n\n"
    "The user just answered the topic '{topic}'.\n"
    'Decide and return ONLY {{"follow_up": <bool>, "question": "<follow-up or empty>"}}.'
)

# ------------------------------------------------------------------ #
# Legacy exports kept so i18n.get_question_prompts() still resolves.   #
# The real-estate interview uses FIXED_QUESTIONS in the node instead.  #
# ------------------------------------------------------------------ #
SYSTEM = FOLLOW_UP_SYSTEM
USER_TEMPLATE = FOLLOW_UP_USER_TEMPLATE
FALLBACK_QUESTIONS = [
    "What makes this compound stand out from nearby projects?",
    "Who is the ideal buyer — investors or end-users, families or young couples?",
    "What is the delivery date or construction status?",
    "Which amenities or facilities are the biggest selling points?",
]
