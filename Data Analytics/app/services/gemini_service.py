"""Gemini API service — uses LangChain's ChatGoogleGenerativeAI."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException

_API_KEY = os.getenv("GEMINI_API_KEY", "")
_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class GeminiService:
    """Wrapper around ChatGoogleGenerativeAI with text and JSON generation."""

    def __init__(self, model_name: str = _MODEL_NAME):
        self.model_name = model_name

    def _get_llm(self, temperature: float, max_tokens: int) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=_API_KEY,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    def _build_messages(self, prompt: str, system_instruction: Optional[str]) -> list:
        messages = []
        if system_instruction:
            messages.append(SystemMessage(content=system_instruction))
        messages.append(HumanMessage(content=prompt))
        return messages

    def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 16384,
        system_instruction: Optional[str] = None,
    ) -> str:
        llm = self._get_llm(temperature, max_tokens)
        response = llm.invoke(self._build_messages(prompt, system_instruction))
        return response.content.strip()

    def generate_json(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 16384,
        system_instruction: Optional[str] = None,
    ) -> Any:
        full_prompt = (
            prompt
            + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown fences, no explanation, no preamble."
        )
        llm = self._get_llm(temperature, max_tokens)
        messages = self._build_messages(full_prompt, system_instruction)

        # Primary: native LangChain JsonOutputParser
        try:
            chain = llm | JsonOutputParser()
            return chain.invoke(messages)
        except (OutputParserException, Exception):
            pass

        # Fallback: manual extraction from raw text
        raw = llm.invoke(messages).content
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(text: str) -> Any:
        cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            for start_char, end_char in [('{', '}'), ('[', ']')]:
                start = cleaned.find(start_char)
                if start == -1:
                    continue
                pos = len(cleaned)
                while pos > start:
                    pos = cleaned.rfind(end_char, start, pos)
                    if pos == -1:
                        break
                    try:
                        return json.loads(cleaned[start:pos + 1])
                    except json.JSONDecodeError:
                        pass
            raise ValueError(f"Could not extract valid JSON from response: {text[:500]}")


_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
