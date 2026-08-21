"""
src/config.py — AutoMark AI (unified)

Single settings object for all three modules: CRM, Campaigns, Analytics.
Every module imports `settings` from here — never read os.environ directly.

Loaded from the repo-root .env, resolved relative to this file so the app and
the tests behave the same regardless of the working directory.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/config.py -> repo root is one level up.
ROOT_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = ROOT_DIR / ".env"

_DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/automark"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ══════════════════════════════════════════════════════════════════════
    # Shared
    # ══════════════════════════════════════════════════════════════════════

    # ── Database (one PostgreSQL + pgvector database for all modules) ──────
    # The campaign module historically used POSTGRES_URL; it is accepted as an
    # alias below so existing .env files keep working.
    DATABASE_URL: str = _DEFAULT_DATABASE_URL
    POSTGRES_URL: str = ""          # legacy alias — folded into DATABASE_URL
    DB_ECHO: bool = False

    # ── Auth (app-wide identity) ───────────────────────────────────────────
    JWT_SECRET: str = "automark-dev-secret-CHANGE-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24 * 7

    # ── Gemini / Google AI ─────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MODEL_FALLBACK: str = ""
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"
    GEMINI_TTS_MODEL: str = ""

    # ── LangSmith / LangChain tracing ──────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = ""

    # ── Application ────────────────────────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"     # "console" (human-readable) | "json"
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:3000"

    # ══════════════════════════════════════════════════════════════════════
    # CRM module
    # ══════════════════════════════════════════════════════════════════════

    HUBSPOT_ACCESS_TOKEN: str = ""
    HUBSPOT_BASE_URL: str = "https://api.hubapi.com"

    MESSENGER_VERIFY_TOKEN: str = ""
    MESSENGER_ACCESS_TOKEN: str = ""
    MESSENGER_APP_SECRET: str = ""
    MESSENGER_PAGE_ID: str = ""

    FB_COMMENTS_VERIFY_TOKEN: str = ""
    FB_COMMENTS_ACCESS_TOKEN: str = ""
    FB_COMMENTS_APP_SECRET: str = ""
    FB_COMMENTS_PAGE_ID: str = ""

    VAPI_API_KEY: str = ""
    VAPI_WEBHOOK_SECRET: str = ""

    # RAG
    RERANKER_BACKEND: str = "gemini"        # gemini | cross-encoder
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.30
    KNOWLEDGE_BASE_PATH: str = str(ROOT_DIR / "src" / "crm" / "knowledge_base")
    EMBEDDING_DIM: int = 768                # pgvector HNSW max = 2000

    # Memory
    MAX_CONVERSATION_HISTORY: int = 20
    SUMMARIZATION_MESSAGE_THRESHOLD: int = 20
    MAX_AGENT_ITERATIONS: int = 6

    # Handoff escalation email
    GMAIL_SENDER: str = ""
    GMAIL_APP_PASSWORD: str = ""
    GMAIL_RECIPIENT: str = ""
    RESEND_API_KEY: str = ""

    # ══════════════════════════════════════════════════════════════════════
    # Campaigns module
    # ══════════════════════════════════════════════════════════════════════

    META_ACCESS_TOKEN: str = ""
    META_AD_ACCOUNT_ID: str = ""
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_PAGE_ID: str = ""
    META_SIMULATION_MODE: bool = True
    MAKE_ORGANIC_POST: bool = False
    MAKE_SPONSORED_PAUSED_AD: bool = True
    # Ad Library API for competitor research; falls back to META_ACCESS_TOKEN.
    META_AD_LIBRARY_TOKEN: str = ""

    MIN_QUESTIONS: int = 3
    MAX_QUESTIONS: int = 6
    ENABLE_FOLLOW_UPS: bool = True
    MAX_REGENERATIONS_ALLOWED: int = 3
    NUM_GENERATED_IMAGES: int = 4
    ENABLE_WEB_SEARCH: bool = False
    AGENT_LOGGING: bool = False
    # Hour (UTC 0–23) at which the daily campaign diagnosis fires.
    LIFECYCLE_DIAGNOSIS_HOUR: int = 9

    # ══════════════════════════════════════════════════════════════════════
    # Analytics module
    # ══════════════════════════════════════════════════════════════════════

    UPLOAD_DIR: str = str(ROOT_DIR / "uploads")
    MAX_UPLOAD_MB: int = 200
    ANALYTICS_ROW_SAMPLE: int = 10_000

    # ── Derived URLs ───────────────────────────────────────────────────────

    @property
    def effective_database_url(self) -> str:
        """The one database URL.

        DATABASE_URL is canonical. The campaign module's legacy POSTGRES_URL is
        honoured only when DATABASE_URL was left at its default — so an old
        deployment that sets just POSTGRES_URL keeps working, while an explicit
        DATABASE_URL is never silently overridden by a stale alias.
        """
        explicit = self.DATABASE_URL.strip() != _DEFAULT_DATABASE_URL
        if self.POSTGRES_URL.strip() and not explicit:
            return self.POSTGRES_URL.strip()
        return self.DATABASE_URL.strip()

    @property
    def sync_database_url(self) -> str:
        """psycopg2 URL — used by the sync (campaigns + analytics) engine."""
        url = self.effective_database_url
        if url.startswith("postgresql+"):
            url = "postgresql://" + url.split("://", 1)[1]
        return url.replace("postgres://", "postgresql://", 1)

    @property
    def async_database_url(self) -> str:
        """asyncpg URL — used by the async (CRM) engine."""
        url = self.sync_database_url
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def cors_origin_list(self) -> list[str]:
        if self.DEBUG:
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

# ─────────────────────────────────────────────────────────────────────────────
# Propagate into the process environment so the LangChain / Gemini / LangSmith
# SDKs pick these up without further plumbing.
# ─────────────────────────────────────────────────────────────────────────────

if settings.GEMINI_API_KEY:
    os.environ.setdefault("GOOGLE_API_KEY", settings.GEMINI_API_KEY)

os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.LANGCHAIN_TRACING_V2 else "false"
os.environ.setdefault("LANGCHAIN_ENDPOINT", settings.LANGCHAIN_ENDPOINT)
if settings.LANGCHAIN_API_KEY:
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGCHAIN_API_KEY)
os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGCHAIN_PROJECT)

# Campaign/analytics modules still read a few of these via os.getenv in
# third-party code paths — keep them in sync.
os.environ.setdefault("DATABASE_URL", settings.sync_database_url)
os.environ.setdefault("POSTGRES_URL", settings.sync_database_url)
