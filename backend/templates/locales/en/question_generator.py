"""English question-generator prompts — adaptive, one question at a time.

The model receives the product image, the goal, and the conversation so far, and
returns the single most useful NEXT question. Output is JSON: {"question": "..."}.
"""

_BASE = (
    "You will receive a {kind} image, a campaign goal, and the conversation so far "
    "(questions already asked and their answers).\n"
    "Ask the SINGLE most useful NEXT question that, together with what you already "
    "know, will help a copywriter craft a high-converting ad.\n"
    "Build on the previous answers — go deeper, fill gaps, never repeat what's known.\n"
    "Across the whole interview, aim to cover: {coverage}.\n"
    "The question must be specific to THIS {kind} (use what you see in the image), "
    "open-ended (not yes/no), and easy for the owner to answer.\n"
    'Return ONLY a JSON object: {{"question": "<your question>"}}. No markdown, no extra text.'
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
    "Ask question {index} of {total}. "
    'Return ONLY {{"question": "<the single next question>"}}.'
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
