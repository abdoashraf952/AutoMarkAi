"""LLM client — provider split:

- Text generation (`call_llm`)           → Groq (llama-3.3-70b-versatile)
- Image understanding (`call_llm_vision`) → Gemini (gemini-2.5-flash, multimodal)
- Image generation (`generate_ad_images`/`enhance_ad_image`) → Gemini image model
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

# Text runs on Groq; image understanding + image generation run on Gemini.
GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


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


def call_llm(
    prompt: str,
    system_prompt: str,
    node_name: str,
    allow_fallback: bool = True,
) -> tuple[str, str]:
    """
    Text generation via Groq. Gemini is reserved exclusively for image
    generation, so there is no Gemini fallback for text any more.

    The `allow_fallback` argument is kept for call-site compatibility but no
    longer switches providers (there is no second text provider).

    Returns:
        (response_text, "groq")
    """
    try:
        resp = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        logger.info("node=%s provider=groq", node_name)
        return resp.choices[0].message.content, "groq"
    except Exception as e:
        raise RuntimeError(f"Groq text generation failed for node {node_name}: {e}") from e


def call_llm_vision(image_path: str, prompt: str, system_prompt: str) -> str:
    """
    Multimodal (image + text) call via Gemini. Used to analyze the product photo
    and produce text (questions / campaign plan). Image understanding is Gemini's
    job; the PIL Image is passed directly to the SDK.

    Returns:
        Raw response text.
    """
    img = Image.open(image_path)
    model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system_prompt)
    response = model.generate_content([img, prompt])
    logger.info("vision call complete for %s provider=gemini", image_path)
    return response.text


def _gemini_image_call(contents, n: int) -> list[str]:
    """Call gemini-3.1-flash-image n times and collect base64-encoded image results."""
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
    Generate n ad images using Gemini 3.1 Flash Image (Nano Banana 2).

    Args:
        prompt: Detailed visual description for the image generation model.
        n:      Number of images to generate (1–4).

    Returns:
        List of n base64-encoded PNG strings.
    """
    try:
        return _gemini_image_call(prompt, n)
    except Exception as e:
        raise RuntimeError(f"Gemini image generation failed: {e}") from e


def enhance_ad_image(image_path: str, prompt: str, n: int = 1) -> list[str]:
    """
    Enhance a user-supplied photo into an ad-ready image using Gemini 3.1 Flash Image.

    The original photo is passed alongside the prompt so the model preserves the
    subject/product while applying ad-ready styling, background, and composition.

    Args:
        image_path: Absolute path to the user's uploaded image file.
        prompt:     Detailed instruction for how the image should be enhanced.
        n:          Number of enhanced variants to produce (1–4).

    Returns:
        List of n base64-encoded PNG strings.
    """
    img = Image.open(image_path)
    try:
        return _gemini_image_call([img, prompt], n)
    except Exception as e:
        raise RuntimeError(f"Gemini image enhancement failed: {e}") from e
