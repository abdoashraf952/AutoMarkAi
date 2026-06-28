"""
config.py — AutoMark AI CRM Agent (ORCAST)

Centralised application settings loaded from environment variables / .env.
Every other module imports `settings` from here — never read os.environ directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file so tests can be run from any directory.
_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Gemini (google-generativeai) ────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = ""
    GEMINI_MODEL_FALLBACK: str = ""
    GEMINI_EMBEDDING_MODEL: str = ""
    GEMINI_TTS_MODEL: str = ""

    # ── Database (PostgreSQL + pgvector) ────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/automark"

    # ── HubSpot ──────────────────────────────────────────────────────────────
    HUBSPOT_ACCESS_TOKEN: str = ""
    HUBSPOT_BASE_URL: str = "https://api.hubapi.com"

    # ── Messenger App ─────────────────────────────────────────────────────────
    MESSENGER_VERIFY_TOKEN: str = ""
    MESSENGER_ACCESS_TOKEN: str = ""
    MESSENGER_APP_SECRET: str = ""
    MESSENGER_PAGE_ID: str = ""

    # ── Facebook Page Comments App ────────────────────────────────────────────
    FB_COMMENTS_VERIFY_TOKEN: str = ""
    FB_COMMENTS_ACCESS_TOKEN: str = ""
    FB_COMMENTS_APP_SECRET: str = ""
    FB_COMMENTS_PAGE_ID: str = ""

    # ── Vapi Voice ───────────────────────────────────────────────────────────
    VAPI_API_KEY: str = ""
    VAPI_WEBHOOK_SECRET: str = ""

    # ── LangSmith / LangChain tracing ───────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = ""

    # ── RAG ──────────────────────────────────────────────────────────────────
    RERANKER_BACKEND: str = "gemini"  # gemini | cross-encoder
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.30
    KNOWLEDGE_BASE_PATH: str = "./knowledge_base"
    EMBEDDING_DIM: int = 768  # pgvector HNSW max = 2000; keep at 768 for index support

    # ── Memory ───────────────────────────────────────────────────────────────
    MAX_CONVERSATION_HISTORY: int = 20
    SUMMARIZATION_MESSAGE_THRESHOLD: int = 20

    # ── Email notifications (handoff escalation emails) ───────────────────────
    GMAIL_SENDER: str = ""        # Gmail address used to send notifications
    GMAIL_APP_PASSWORD: str = ""  # Google App Password (not your account password)
    GMAIL_RECIPIENT: str = ""     # Email address that receives handoff alerts
    RESEND_API_KEY: str = ""      # Resend.com API key (re_xxx) — works over HTTPS, no firewall issues

    # ── Application ──────────────────────────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"   # "console" (human-readable) | "json" (production)
    DEBUG: bool = False
    MAX_AGENT_ITERATIONS: int = 6


settings = Settings()

# ─────────────────────────────────────────────────────────────────────────────
# Propagate settings into the process environment so the LangChain / Gemini /
# LangSmith SDKs pick them up automatically without further plumbing.
# ─────────────────────────────────────────────────────────────────────────────

if settings.GEMINI_API_KEY:
    os.environ.setdefault("GOOGLE_API_KEY", settings.GEMINI_API_KEY)

os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.LANGCHAIN_TRACING_V2 else "false"
os.environ.setdefault("LANGCHAIN_ENDPOINT", settings.LANGCHAIN_ENDPOINT)
if settings.LANGCHAIN_API_KEY:
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGCHAIN_API_KEY)
os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGCHAIN_PROJECT)
