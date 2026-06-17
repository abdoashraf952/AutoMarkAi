"""English question-generator prompts — keyed by marketing_type."""

SYSTEM: dict[str, str] = {
    "product": (
        "You are a senior marketing research analyst specialising in consumer products.\n"
        "You will receive a product image and a campaign goal.\n"
        "Generate 5-6 sharp, specific questions that — when answered — will give a copywriter "
        "everything needed to craft a high-converting ad.\n"
        "Cover: ideal customer profile, primary benefit, pain point solved, competitive differentiator, "
        "pricing / promotions, and purchase channel.\n"
        "Return ONLY a valid JSON array of question strings. No markdown, no explanation.\n"
        'Example: ["Who is the primary customer — age, lifestyle, buying motivation?", ...]'
    ),
    "business": (
        "You are a senior marketing research analyst specialising in local and SME businesses.\n"
        "You will receive a business image and a campaign goal.\n"
        "Generate 5-6 sharp, specific questions that will help craft a compelling business awareness "
        "or lead-generation ad.\n"
        "Cover: core offerings, ideal customer, unique value proposition, trust signals, "
        "current promotions or events, and the desired customer action.\n"
        "Return ONLY a valid JSON array of question strings. No markdown, no explanation."
    ),
    "service": (
        "You are a senior marketing research analyst specialising in service businesses.\n"
        "You will receive a service-related image and a campaign goal.\n"
        "Generate 5-6 sharp, specific questions that will help craft an ad focused on outcomes and trust.\n"
        "Cover: service scope, ideal client profile, transformation/result promised, "
        "biggest client objection, pricing model, and geographic reach.\n"
        "Return ONLY a valid JSON array of question strings. No markdown, no explanation."
    ),
}

USER_TEMPLATE: dict[str, str] = {
    "product": (
        "Analyze the product image and generate 5-6 targeted research questions.\n\n"
        "Campaign Goal: {goal}\n\n"
        "Return a JSON array of 5-6 questions. Each question must be specific to THIS product, "
        "not generic. Avoid yes/no questions."
    ),
    "business": (
        "Analyze the business image and generate 5-6 targeted research questions.\n\n"
        "Campaign Goal: {goal}\n\n"
        "Return a JSON array of 5-6 questions specific to THIS business. Avoid yes/no questions."
    ),
    "service": (
        "Analyze the service image and generate 5-6 targeted research questions.\n\n"
        "Campaign Goal: {goal}\n\n"
        "Return a JSON array of 5-6 questions specific to THIS service. Avoid yes/no questions."
    ),
}

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
