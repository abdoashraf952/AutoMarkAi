"""LLM client with Gemini primary and Groq fallback, plus Imagen 3 image generation."""

import base64
import json
import logging
import os
import re

import google.generativeai as genai
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
from groq import Groq
from PIL import Image

try:
    from google import genai as genai_new
    from google.genai import types as genai_types
    _imagen_client = genai_new.Client(api_key=os.getenv("GEMINI_API_KEY"))
except ImportError:
    genai_new = None
    genai_types = None
    _imagen_client = None

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"
IMAGEN_MODEL = "imagen-4.0-fast-generate-001"

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
    Call primary LLM for text generation, falling back to secondary on errors.
    Primary is controlled by PRIMARY_TEXT_LLM env var (gemini or groq).
    """
    primary = os.getenv("PRIMARY_TEXT_LLM", "gemini").lower()

    def try_gemini():
        model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system_prompt)
        response = model.generate_content(prompt)
        logger.info("node=%s provider=gemini", node_name)
        return response.text, "gemini"

    def try_groq():
        resp = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        logger.info("node=%s provider=groq", node_name)
        return resp.choices[0].message.content, "groq"

    if primary == "groq":
        try:
            return try_groq()
        except Exception as e:
            if not allow_fallback:
                raise RuntimeError(f"Groq failed and fallback disabled: {e}") from e
            logger.warning("node=%s Groq error %s — falling back to Gemini", node_name, type(e).__name__)
            try:
                return try_gemini()
            except Exception as e2:
                raise RuntimeError(f"Both Groq and Gemini failed for node {node_name}: {e2}") from e2
    else:
        try:
            return try_gemini()
        except (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable) as e:
            if not allow_fallback:
                raise RuntimeError(f"Gemini failed and fallback disabled: {e}") from e
            logger.warning("node=%s Gemini error %s — falling back to Groq", node_name, type(e).__name__)
            try:
                return try_groq()
            except Exception as e2:
                raise RuntimeError(f"Both Gemini and Groq failed for node {node_name}: {e2}") from e2


def call_llm_vision(image_path: str, prompt: str, system_prompt: str) -> str:
    """
    Gemini-only multimodal call. Passes PIL Image directly to the SDK.

    Returns:
        Raw response text.
    """
    img = Image.open(image_path)
    model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system_prompt)
    response = model.generate_content([img, prompt])
    logger.info("vision call complete for %s", image_path)
    return response.text


def generate_ad_images(prompt: str, n: int = 3) -> list[str]:
    """
    Generate n ad images using Imagen 4 via the google-genai SDK.

    Args:
        prompt: Detailed visual description for the image generation model.
        n:      Number of images to generate (1–4).

    Returns:
        List of n base64-encoded PNG strings.

    Raises:
        RuntimeError if google-genai is not installed or the API call fails.
    """
    if _imagen_client is None:
        raise RuntimeError(
            "google-genai is not installed. Run: pip install google-genai>=1.0.0"
        )
    try:
        response = _imagen_client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt,
            config=genai_types.GenerateImagesConfig(number_of_images=n),
        )
        return [
            base64.b64encode(img.image.image_bytes).decode("utf-8")
            for img in response.generated_images
        ]
    except Exception as e:
        raise RuntimeError(f"Imagen generation failed: {e}") from e
