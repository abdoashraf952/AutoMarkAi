"""English UI strings and labels."""

MARKETING_TYPE_LABELS = {
    "product": "Product",
    "business": "Business",
    "service": "Service",
}

MARKETING_TYPE_DESCRIPTIONS = {
    "product": "A physical or digital item you sell (e.g. gadget, clothing, food, app)",
    "business": "A business entity you want to promote (e.g. restaurant, clinic, shop)",
    "service": "A service you offer (e.g. consulting, cleaning, tutoring, design)",
}

STAGE_LABELS = {
    "setup": "1. Setup",
    "questions": "2. Product Questions",
    "image_review": "3. Image Review",
    "max_regenerations_exceeded": "3b. Choose Image",
    "text_review": "4. Copy Review",
    "done": "5. Complete",
}

SETUP_HEADER = "Campaign Setup"
QUESTIONS_HEADER = "Tell Us About Your {marketing_type}"
QUESTIONS_SUBTEXT = "Answer these questions so we can craft the perfect campaign:"
IMAGE_REVIEW_HEADER_ORIGINAL = "Review Your Photo"
IMAGE_REVIEW_HEADER_ENHANCED = "Review Enhanced Ad Image"
IMAGE_REVIEW_SUBTEXT_ORIGINAL = "Confirm your photo looks correct before we continue."
IMAGE_REVIEW_SUBTEXT_ENHANCED = "Review the AI-enhanced ad image. Approve it or request a re-enhancement."
TEXT_REVIEW_HEADER = "Review Ad Copy"
DONE_HEADER = "Campaign Ready"
MAX_REGEN_HEADER = "Maximum Regenerations Exceeded"
MAX_REGEN_SUBTEXT = "Choose one of the previously generated images to continue:"

SIMULATION_BANNER = (
    "Running in demo mode — connect Meta credentials in `.env` "
    "and set `META_SIMULATION_MODE=false` to go live."
)
