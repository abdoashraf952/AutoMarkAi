"""English question-generator prompts.

Two prompt families live here:

1. CAMPAIGN TARGET (the one fixed question, always asked first) — the model
   analyses the product/business/service and returns a ranked, multiple-choice
   list of campaign goals with exactly one marked recommended.

2. ADAPTIVE FOLLOW-UPS — the model receives the conversation so far and returns
   the single most useful NEXT question, OR signals that no further question
   would add meaningful value. Output is JSON.
"""

# ------------------------------------------------------------------ #
# 1. Campaign target — ranked multiple-choice (Edit 2)                #
# ------------------------------------------------------------------ #
_TARGET_BASE = (
    "You help a non-marketer choose the single best GOAL for their ad campaign.\n"
    "You will receive a {kind} (image when available) and the budget.\n"
    "Return a ranked, multiple-choice list of campaign goals, BEST first.\n"
    "Choose from these real goal types (use plain language, no jargon):\n"
    "  - Messages/chats (people message on WhatsApp or Messenger)\n"
    "  - Sales/orders (people buy online)\n"
    "  - Leads/sign-ups (people leave their details)\n"
    "  - Website visits (people visit a page to learn more)\n"
    "  - Get known (more people discover the {kind})\n"
    "Pick the 4 most relevant for THIS {kind}, ranked by what will work best.\n"
    "Mark EXACTLY ONE as recommended (the strongest fit, ranked first).\n"
    "Return ONLY this JSON (no markdown, no extra text):\n"
    "{{\n"
    '  "options": [\n'
    '    {{"label": "<short friendly goal name>", "description": "<one plain sentence on what happens>", '
    '"goal": "<a natural-language campaign goal sentence to feed the planner>", "recommended": true}},\n'
    "    ... 4 options total, ranked best first, exactly one recommended ...\n"
    "  ]\n"
    "}}"
)

TARGET_SYSTEM: dict[str, str] = {
    "product": _TARGET_BASE.format(kind="product"),
    "business": _TARGET_BASE.format(kind="business"),
    "service": _TARGET_BASE.format(kind="service"),
}

_TARGET_USER = (
    "Budget: ${budget}\n\n"
    "Analyse what you can see and recommend the best campaign goal. "
    "Return ONLY the ranked JSON options described in the system message."
)

TARGET_USER_TEMPLATE: dict[str, str] = {
    "product": _TARGET_USER,
    "business": _TARGET_USER,
    "service": _TARGET_USER,
}

# Index-aligned fallback if the model fails. Best/recommended first.
TARGET_FALLBACK_OPTIONS: dict[str, list[dict]] = {
    "product": [
        {"label": "Sales & orders", "description": "People buy your product online.",
         "goal": "drive online sales and orders for this product", "recommended": True},
        {"label": "Messages & chats", "description": "People message you on WhatsApp or Messenger.",
         "goal": "get WhatsApp and Messenger messages from interested buyers", "recommended": False},
        {"label": "Website visits", "description": "People visit your page to learn more.",
         "goal": "drive traffic to the product page so people can learn more", "recommended": False},
        {"label": "Get known", "description": "More people discover your product.",
         "goal": "build awareness so more people discover this product", "recommended": False},
    ],
    "business": [
        {"label": "Messages & chats", "description": "People message you on WhatsApp or Messenger.",
         "goal": "get WhatsApp and Messenger messages from nearby customers", "recommended": True},
        {"label": "Visits & calls", "description": "People come in or call you.",
         "goal": "get more visits and calls to the business", "recommended": False},
        {"label": "Leads & sign-ups", "description": "People leave their details so you can follow up.",
         "goal": "collect leads and sign-ups from interested customers", "recommended": False},
        {"label": "Get known", "description": "More people discover your business.",
         "goal": "build local awareness so more people discover this business", "recommended": False},
    ],
    "service": [
        {"label": "Messages & chats", "description": "People message you on WhatsApp or Messenger.",
         "goal": "get WhatsApp and Messenger enquiries from people who need this service", "recommended": True},
        {"label": "Leads & sign-ups", "description": "People leave their details so you can follow up.",
         "goal": "collect leads and sign-ups from people who need this service", "recommended": False},
        {"label": "Website visits", "description": "People visit your page to learn more.",
         "goal": "drive traffic to the service page so people can learn more", "recommended": False},
        {"label": "Get known", "description": "More people discover your service.",
         "goal": "build awareness so more people discover this service", "recommended": False},
    ],
}

# ------------------------------------------------------------------ #
# 2. Adaptive follow-up questions — dynamic count (Edit 5)            #
# ------------------------------------------------------------------ #
_BASE = (
    "You will receive a {kind} (image when available), the chosen campaign goal, and the "
    "conversation so far (questions already asked and their answers).\n"
    "Your job: decide whether ONE more question would add MEANINGFUL value, and if so, ask it.\n"
    "Ask basic, essential questions first; only go deeper with a follow-up when the previous "
    "answers genuinely call for it. Never ask a question whose answer you can already infer, "
    "and never repeat what's known.\n"
    "Across the interview, aim to cover (only as needed): {coverage}.\n"
    "Respect the allowed question range stated in the user message:\n"
    "- If fewer than the minimum have been asked, you must ask another (done=false).\n"
    "- If the maximum has been reached, you must stop (done=true).\n"
    "- Otherwise, stop (done=true) only when more questions would add little value.\n"
    "Each question must be specific to THIS {kind}, open-ended (not yes/no), and easy for the "
    "owner to answer in plain words.\n"
    'Return ONLY this JSON: {{"done": <true|false>, "question": "<next question, or empty if done>"}}. '
    "No markdown, no extra text."
)

SYSTEM: dict[str, str] = {
    "product": _BASE.format(
        kind="product",
        coverage="ideal customer, primary benefit, pain point solved, competitive "
        "differentiator, pricing/promotions, and purchase channel",
    ),
    "business": _BASE.format(
        kind="business",
        coverage="core offerings, ideal customer, unique value proposition, trust "
        "signals, current promotions/events, and the desired customer action",
    ),
    "service": _BASE.format(
        kind="service",
        coverage="service scope, ideal client, transformation/result promised, the "
        "biggest client objection, pricing model, and geographic reach",
    ),
}

_USER = (
    "Campaign Goal: {goal}\n\n"
    "{qa_context}\n\n"
    "So far {answered} question(s) have been answered (allowed range: {min_q}–{max_q}).\n"
    'Decide and return ONLY {{"done": <bool>, "question": "<next question or empty>"}}.'
)

USER_TEMPLATE: dict[str, str] = {
    "product": _USER,
    "business": _USER,
    "service": _USER,
}

# Used when generation fails for a given index (index-aligned with the interview).
FALLBACK_QUESTIONS: dict[str, list[str]] = {
    "product": [
        "Who is the ideal customer — describe their age, lifestyle, and buying motivation?",
        "What is the single most important benefit this product delivers?",
        "What pain point or frustration does this product solve?",
        "How does it stand out from similar products already on the market?",
        "What is the price range, and are there any current promotions or bundles?",
        "Where can customers buy it — website, store, delivery platform?",
    ],
    "business": [
        "What are your main products or services, and who is your ideal customer?",
        "What makes your business different from competitors in the same area or category?",
        "What is the most common reason a customer chooses you over others?",
        "Do you have any current offers, events, or seasonal promotions running?",
        "What action do you want customers to take — visit in person, call, book online, or order?",
        "What are the top 2-3 objections a new customer might have before choosing you?",
    ],
    "service": [
        "What specific service do you provide, and what does a typical engagement include?",
        "Who is your ideal client — what situation are they in when they need you most?",
        "What result or transformation can clients realistically expect after working with you?",
        "What is the biggest hesitation or fear clients have before hiring you, and how do you address it?",
        "What is your pricing model — flat fee, packages, hourly, or subscription?",
        "Do you work locally, remotely, or both — and what geographic areas do you serve?",
    ],
}
