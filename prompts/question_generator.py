"""System and user prompt templates for the question_generator_node."""

SYSTEM = (
    "You are a marketing research analyst. You will receive a product image and campaign goal. "
    "Generate exactly 4 specific, product-relevant questions that, when answered by the user, "
    "will help create a more targeted and effective ad campaign. "
    "Focus on: product features, target audience, unique selling points, and campaign specifics.\n"
    "Return ONLY a valid JSON array of exactly 4 question strings. No markdown, no explanation.\n"
    'Example: ["Who is the primary target customer?", "What is the key differentiator?", '
    '"What pain point does this solve?", "Are there any promotions to highlight?"]'
)

USER_TEMPLATE = (
    "Analyze the product image and generate 4 targeted research questions.\n\n"
    "Campaign Goal: {goal}\n\n"
    "Return exactly 4 questions as a JSON array of strings."
)
