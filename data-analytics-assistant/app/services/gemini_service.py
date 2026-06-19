"""Gemini API service wrapper — uses the current google-genai SDK."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from google import genai
from google.genai import types as genai_types

_API_KEY = os.getenv("GEMINI_API_KEY", "")
_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _get_client() -> genai.Client:
    return genai.Client(api_key=_API_KEY)


class GeminiService:
    """Thin wrapper around the Google Gemini Generative AI API (google-genai SDK)."""

    def __init__(self, model_name: str = _MODEL_NAME):
        self.model_name = model_name

    def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        system_instruction: Optional[str] = None,
    ) -> str:
        """Send a prompt and return the text response."""
        client = _get_client()

        config = genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        return response.text.strip()

    def generate_json(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        system_instruction: Optional[str] = None,
    ) -> Any:
        """Send a prompt, extract JSON from the response, and parse it."""
        full_prompt = (
            prompt
            + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown fences, no explanation, no preamble."
        )
        raw = self.generate(
            full_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            system_instruction=system_instruction,
        )
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Strip markdown fences and parse JSON."""
        cleaned = re.sub(r"```(?:json)?\s*", "", text)
        cleaned = cleaned.replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            for start_char, end_char in [('{', '}'), ('[', ']')]:
                start = cleaned.find(start_char)
                end = cleaned.rfind(end_char)
                if start != -1 and end != -1:
                    try:
                        return json.loads(cleaned[start:end + 1])
                    except json.JSONDecodeError:
                        continue
            raise ValueError(f"Could not extract valid JSON from response: {text[:500]}")


# Singleton
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
