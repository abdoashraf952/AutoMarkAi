"""LLM client — configurable provider plus image generation.

Text generation provider is selected with the LLM_PROVIDER env var:

    LLM_PROVIDER=gemini  (default)  → text model "gemini-2.5-flash"
    LLM_PROVIDER=groq               → text model "openai/gpt-oss-120b"

`call_llm` honours that choice for EVERY text LLM call in the app.

Image *understanding* (`call_llm_vision`) requires a multimodal model, so it
always runs on Gemini (the only multimodal provider configured here) regardless
of LLM_PROVIDER — a text-only model such as gpt-oss-120b cannot read an image.
When there is no image at all, `analyze_visual` falls back to the configured
text provider so the no-image flow still respects LLM_PROVIDER.

Image *generation* (`generate_ad_images` / `enhance_ad_image`) runs on the
Gemini image model and every prompt is hard-constrained to contain no humans.
"""

import base64
import json
import logging
import os
import re

import google.generativeai as genai
from dotenv import load_dotenv
from groq import Groq
from PIL import Image

# Load .env BEFORE constructing any API clients so the keys are available.
load_dotenv()

try:
    from google import genai as genai_new
    from google.genai import types as genai_types
    _imagen_client = genai_new.Client(api_key=os.getenv("GEMINI_API_KEY"))
except ImportError:
    genai_new = None
    genai_types = None
    _imagen_client = None

logger = logging.getLogger(__name__)

# --- Provider selection ----------------------------------------------------- #
# "gemini" (default) or "groq". Applies to all text generation via call_llm.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

# Text model per provider (Edit 6).
GROQ_TEXT_MODEL = "openai/gpt-oss-120b"
GEMINI_TEXT_MODEL = "gemini-2.5-flash"

# Vision (image understanding) + image generation always run on Gemini.
GEMINI_VISION_MODEL = "gemini-2.5-flash"
GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"

# Backwards-compatible alias (older imports referenced GEMINI_MODEL).
GEMINI_MODEL = GEMINI_VISION_MODEL

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- Hard image content policy (Edit 3) ------------------------------------- #
# Applied to EVERY image generation/enhancement prompt, site-wide, no matter
# what the user asks for.
NO_HUMANS_CONSTRAINT = (
    "ABSOLUTE, NON-NEGOTIABLE CONSTRAINT: The image must NOT contain any humans, "
    "people, persons, faces, hands, skin, silhouettes of people, or crowds — not "
    "in the foreground, background, reflections, or as part of any logo or artwork. "
    "Depict only the product/object itself, environments, scenery, textures, or "
    "abstract elements. If a human would normally appear, replace them with empty "
    "space, props, or the product alone. This rule overrides any other instruction."
)


def _apply_image_constraints(prompt: str) -> str:
    """Append the site-wide no-humans policy to any image prompt."""
    prompt = (prompt or "").strip()
    return f"{prompt}\n\n{NO_HUMANS_CONSTRAINT}" if prompt else NO_HUMANS_CONSTRAINT


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers that some LLMs add."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_with_retry(raw: str) -> dict:
    """Parse JSON from raw LLM text, stripping fences and retrying with regex extraction."""
    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Second attempt: extract first {...} block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Could not parse JSON from LLM response: {cleaned[:200]}")


def _groq_text(prompt: str, system_prompt: str) -> str:
    resp = _groq_client.chat.completions.create(
        model=GROQ_TEXT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content


def _gemini_text(prompt: str, system_prompt: str) -> str:
    model = genai.GenerativeModel(GEMINI_TEXT_MODEL, system_instruction=system_prompt)
    resp = model.generate_content(prompt)
    return resp.text


def call_llm(
    prompt: str,
    system_prompt: str,
    node_name: str,
    allow_fallback: bool = True,
) -> tuple[str, str]:
    """
    Text generation via the configured provider (LLM_PROVIDER).

    The `allow_fallback` argument is kept for call-site compatibility.

    Returns:
        (response_text, provider)  where provider is "gemini" or "groq".
    """
    provider = LLM_PROVIDER if LLM_PROVIDER in ("groq", "gemini") else "gemini"
    try:
        text = _groq_text(prompt, system_prompt) if provider == "groq" else _gemini_text(prompt, system_prompt)
        logger.info("node=%s provider=%s", node_name, provider)
        return text, provider
    except Exception as e:
        raise RuntimeError(f"{provider} text generation failed for node {node_name}: {e}") from e


def call_llm_vision(image_path: str, prompt: str, system_prompt: str) -> str:
    """
    Multimodal (image + text) call. Image understanding requires a multimodal
    model, so this always runs on Gemini regardless of LLM_PROVIDER.

    Returns:
        Raw response text.
    """
    img = Image.open(image_path)
    model = genai.GenerativeModel(GEMINI_VISION_MODEL, system_instruction=system_prompt)
    response = model.generate_content([img, prompt])
    logger.info("vision call complete for %s provider=gemini", image_path)
    return response.text


def analyze_visual(
    image_path: str | None,
    prompt: str,
    system_prompt: str,
    description: str | None = None,
) -> str:
    """
    Analyze a product when an image MAY or MAY NOT be present.

    - With an image  → Gemini vision (multimodal, see call_llm_vision).
    - Without an image → the configured text provider (LLM_PROVIDER). When the
      user skipped the photo, `description` (their typed product/business/service
      description) is prepended so the model actually knows what it's working
      with before recommending a target, asking questions, or planning.

    This lets the image-optional flow (Edit 4) still produce questions, targets,
    and a campaign plan when the user skips the upload.
    """
    if image_path:
        return call_llm_vision(image_path, prompt, system_prompt)
    desc = (description or "").strip()
    if desc:
        prompt = (
            "There is no photo. The owner described what they're promoting:\n"
            f'"""{desc}"""\n'
            "Base your analysis entirely on this description.\n\n"
            f"{prompt}"
        )
    text, _ = call_llm(prompt, system_prompt, "analyze_visual_text")
    return text


def _gemini_image_call(contents, n: int) -> list[str]:
    """Call the Gemini image model n times and collect base64-encoded image results."""
    if _imagen_client is None:
        raise RuntimeError(
            "google-genai is not installed. Run: pip install google-genai>=1.0.0"
        )
    results = []
    for _ in range(n):
        response = _imagen_client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                results.append(base64.b64encode(part.inline_data.data).decode("utf-8"))
                break
    if not results:
        raise RuntimeError("Gemini image model returned no images")
    return results


def generate_ad_images(prompt: str, n: int = 3) -> list[str]:
    """
    Generate n ad images using the Gemini image model.

    The site-wide no-humans policy (NO_HUMANS_CONSTRAINT) is appended to every
    prompt before generation.

    Args:
        prompt: Detailed visual description for the image generation model.
        n:      Number of images to generate (1–4).

    Returns:
        List of n base64-encoded PNG strings.
    """
    try:
        return _gemini_image_call(_apply_image_constraints(prompt), n)
    except Exception as e:
        raise RuntimeError(f"Gemini image generation failed: {e}") from e


def enhance_ad_image(image_path: str, prompt: str, n: int = 1) -> list[str]:
    """
    Enhance a user-supplied photo into an ad-ready image using the Gemini image model.

    The original photo is passed alongside the prompt so the model preserves the
    subject/product while applying ad-ready styling. The site-wide no-humans
    policy is appended to every prompt.

    Args:
        image_path: Absolute path to the user's uploaded image file.
        prompt:     Detailed instruction for how the image should be enhanced.
        n:          Number of enhanced variants to produce (1–4).

    Returns:
        List of n base64-encoded PNG strings.
    """
    img = Image.open(image_path)
    try:
        return _gemini_image_call([img, _apply_image_constraints(prompt)], n)
    except Exception as e:
        raise RuntimeError(f"Gemini image enhancement failed: {e}") from e
