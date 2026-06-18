"""LLM client — Groq for ALL text (including vision→text), Gemini ONLY for image generation.

Text generation (`call_llm`) and image-understanding (`call_llm_vision`) both run
on Groq. Gemini is used exclusively for `generate_ad_images` / `enhance_ad_image`.
"""

import base64
import io
import json
import logging
import os
import re

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

# Text + vision run on Groq; only image generation uses Gemini.
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"

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


def _image_to_data_url(image_path: str, max_dim: int = 1024) -> str:
    """Load an image, downscale it to keep the request small, and return a
    base64 `data:` URL suitable for Groq's vision API (which caps base64
    payloads at ~4 MB)."""
    img = Image.open(image_path)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def call_llm_vision(image_path: str, prompt: str, system_prompt: str) -> str:
    """
    Multimodal (image + text) call via Groq's vision model. Used to analyze the
    product photo and produce text (questions / campaign plan).

    Returns:
        Raw response text.
    """
    data_url = _image_to_data_url(image_path)
    resp = _groq_client.chat.completions.create(
        model=GROQ_VISION_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    )
    logger.info("vision call complete for %s provider=groq", image_path)
    return resp.choices[0].message.content


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
