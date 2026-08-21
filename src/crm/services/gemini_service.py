"""
app/services/gemini_service.py — AutoMark AI CRM Agent (ORCAST)

Gemini intelligence layer via LangChain (ChatGoogleGenerativeAI) for all
text and tool-calling work, so every call is traced in LangSmith.

Multimodal helpers (audio, image, PDF, TTS) use the raw google-generativeai
SDK — LangChain doesn't yet handle binary media payloads natively.

Public API:
    generate_text()          — plain text generation (primary + fallback model)
    generate_with_tools()    — function-calling via LangChain bind_tools()
    get_chat_model()         — returns a configured ChatGoogleGenerativeAI
    transcribe_audio()       — audio bytes → plain text   (raw SDK)
    describe_image()         — image bytes → plain text   (raw SDK)
    extract_pdf_text()       — PDF bytes  → text          (raw SDK)
    synthesize_speech()      — text → audio bytes         (raw SDK, Messenger only)
"""

from __future__ import annotations

import base64
import io
import struct
import wave
from datetime import datetime, timezone
from typing import Any, Optional

import google.generativeai as genai
import httpx
import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from src.config import settings

logger = structlog.get_logger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# UnifiedMessage — platform-agnostic normalised message
# ─────────────────────────────────────────────────────────────────────────────

class UnifiedMessage(BaseModel):
    """Normalised message handed to the ORCAST graph.
    `content` is always plain text regardless of original media type."""

    user_id: str
    source: str
    input_type: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Multimodal prompts (text prompts live in app/graph/prompts.py)
# ─────────────────────────────────────────────────────────────────────────────

_VISION_PROMPT = (
    "You are analysing an image sent by a customer in a chat. "
    "Describe the content concisely and extract any relevant information "
    "(product names, error messages, visible text). Under 150 words."
)

_AUDIO_PROMPT = (
    "Transcribe this audio message exactly. "
    "Return ONLY the transcription, no other text."
)

_PDF_PROMPT = (
    "Extract all readable text from this document, preserving the original "
    "structure as plain text. Return ONLY the extracted text."
)


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Wrap raw PCM bytes in a WAV container. Messenger requires a file format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# GeminiService
# ─────────────────────────────────────────────────────────────────────────────

class GeminiService:

    # ── LangChain chat model factory ─────────────────────────────────────────

    def get_chat_model(
        self,
        model_name: str = "",
        temperature: float = 0.3,
    ) -> ChatGoogleGenerativeAI:
        """Return a configured ChatGoogleGenerativeAI instance."""
        return ChatGoogleGenerativeAI(
            model=model_name or settings.GEMINI_MODEL,
            temperature=temperature,
            google_api_key=settings.GEMINI_API_KEY,
        )

    # ── Text generation ──────────────────────────────────────────────────────

    async def generate_text(self, prompt: str, temperature: float = 0.3) -> str:
        """
        Generate plain text. Falls back to GEMINI_MODEL_FALLBACK on error.
        All calls are traced via LangSmith (ChatGoogleGenerativeAI).
        """
        for model_name in (settings.GEMINI_MODEL, settings.GEMINI_MODEL_FALLBACK):
            try:
                llm = self.get_chat_model(model_name, temperature)
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                return (response.content or "").strip()
            except Exception as exc:
                logger.warning("gemini_service.generate_text.error", model=model_name, error=str(exc))
        return ""

    # ── Tool-calling generation ───────────────────────────────────────────────

    async def generate_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """
        Generate a response that may include LangChain tool calls.

        Parameters
        ----------
        messages      : [{"role": "user"|"model"|"assistant", "content": str}]
        tools         : list of LangChain BaseTool / StructuredTool objects
        system_prompt : optional system instruction prepended to messages
        temperature   : generation temperature

        Returns
        -------
        {"text": str, "function_calls": [{"name": str, "args": dict}, ...]}
        """
        lc_messages: list = []
        if system_prompt:
            lc_messages.append(SystemMessage(content=system_prompt))
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            lc_messages.append(
                HumanMessage(content=content) if role in ("user", "human")
                else AIMessage(content=content)
            )

        for model_name in (settings.GEMINI_MODEL, settings.GEMINI_MODEL_FALLBACK):
            try:
                llm = self.get_chat_model(model_name, temperature)
                bound = llm.bind_tools(tools) if tools else llm
                response = await bound.ainvoke(lc_messages)
                function_calls = [
                    {"name": tc["name"], "args": dict(tc.get("args", {}) or {})}
                    for tc in (response.tool_calls or [])
                ]
                return {"text": (response.content or "").strip(), "function_calls": function_calls}
            except Exception as exc:
                logger.warning("gemini_service.generate_with_tools.error", model=model_name, error=str(exc))

        return {"text": "", "function_calls": []}

    # ── Multimodal helpers (raw google-generativeai SDK) ─────────────────────
    # LangChain doesn't handle raw binary audio/image/PDF payloads natively.
    # These produce plain text that the graph can embed or store normally.

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        # Messenger wraps voice notes in an MP4 container but they are audio-only.
        # Gemini rejects video/* MIME types for audio content — normalise to audio/*.
        _VIDEO_TO_AUDIO = {"video/mp4": "audio/mp4", "video/mpeg": "audio/mpeg", "video/webm": "audio/webm"}
        mime_type = _VIDEO_TO_AUDIO.get(mime_type, mime_type)
        try:
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            response = await model.generate_content_async([
                {"mime_type": mime_type, "data": audio_bytes},
                _AUDIO_PROMPT,
            ])
            return (response.text or "").strip()
        except Exception as exc:
            logger.error("gemini_service.transcribe_audio.error", error=str(exc))
            return ""

    async def describe_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        try:
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            response = await model.generate_content_async([
                {"mime_type": mime_type, "data": image_bytes},
                _VISION_PROMPT,
            ])
            return (response.text or "").strip()
        except Exception as exc:
            logger.error("gemini_service.describe_image.error", error=str(exc))
            return ""

    async def extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Fallback for scanned/image-based PDFs that PyPDFLoader can't parse."""
        try:
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            response = await model.generate_content_async([
                {"mime_type": "application/pdf", "data": pdf_bytes},
                _PDF_PROMPT,
            ])
            return (response.text or "").strip()
        except Exception as exc:
            logger.error("gemini_service.extract_pdf_text.error", error=str(exc))
            return ""

    async def synthesize_speech(self, text: str) -> Optional[tuple[bytes, str]]:
        """
        Text → (audio_bytes, mime_type) via GEMINI_TTS_MODEL REST API.
        Gemini returns PCM (audio/L16) — we wrap it in a WAV container so
        Messenger's Send API accepts it. Returns None on failure.
        """
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models"
            f"/{settings.GEMINI_TTS_MODEL}:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": "Kore"}
                    }
                },
            },
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url, json=payload, params={"key": settings.GEMINI_API_KEY}
                )
                resp.raise_for_status()
            for candidate in resp.json().get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline = part.get("inlineData", {})
                    audio_b64 = inline.get("data", "")
                    if not audio_b64:
                        continue
                    raw = base64.b64decode(audio_b64)
                    mime = inline.get("mimeType", "audio/L16;rate=24000")
                    if "L16" in mime or "pcm" in mime.lower():
                        rate = 24000
                        if "rate=" in mime:
                            try:
                                rate = int(mime.split("rate=")[1].split(";")[0].strip())
                            except ValueError:
                                pass
                        raw = _pcm_to_wav(raw, sample_rate=rate)
                        mime = "audio/wav"
                    return raw, mime
            return None
        except Exception as exc:
            logger.error("gemini_service.synthesize_speech.error", error=str(exc))
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

gemini_service = GeminiService()