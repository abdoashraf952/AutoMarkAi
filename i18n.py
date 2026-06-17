"""Locale loader — returns prompt strings for the given language and marketing type."""

import importlib
import logging

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("en", "ar")
SUPPORTED_MARKETING_TYPES = ("product", "business", "service")
DEFAULT_LANGUAGE = "en"
DEFAULT_MARKETING_TYPE = "product"


def _load(module_name: str, language: str) -> object:
    """Import templates.locales.<language>.<module_name>, falling back to 'en' on error."""
    lang = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    try:
        return importlib.import_module(f"templates.locales.{lang}.{module_name}")
    except ImportError:
        if lang != DEFAULT_LANGUAGE:
            logger.warning("Locale '%s' not found for '%s', falling back to 'en'", lang, module_name)
            return importlib.import_module(f"templates.locales.en.{module_name}")
        raise


def _pick(mapping: dict | str, marketing_type: str) -> str:
    """Return the right string from a dict keyed by marketing_type, or the string itself."""
    if isinstance(mapping, dict):
        return mapping.get(marketing_type, mapping.get(DEFAULT_MARKETING_TYPE, ""))
    return mapping


# ------------------------------------------------------------------ #
# Public helpers used by nodes                                         #
# ------------------------------------------------------------------ #

def get_question_prompts(
    language: str = DEFAULT_LANGUAGE,
    marketing_type: str = DEFAULT_MARKETING_TYPE,
) -> tuple[str, str, list[str]]:
    """Return (SYSTEM, USER_TEMPLATE, FALLBACK_QUESTIONS) for the question generator."""
    mod = _load("question_generator", language)
    return (
        _pick(mod.SYSTEM, marketing_type),
        _pick(mod.USER_TEMPLATE, marketing_type),
        _pick(mod.FALLBACK_QUESTIONS, marketing_type),
    )


def get_orchestrator_prompts(
    language: str = DEFAULT_LANGUAGE,
    marketing_type: str = DEFAULT_MARKETING_TYPE,
) -> tuple[str, str]:
    """Return (SYSTEM, USER_TEMPLATE) for the orchestrator."""
    mod = _load("orchestrator", language)
    return (
        _pick(mod.SYSTEM, marketing_type),
        _pick(mod.USER_TEMPLATE, marketing_type),
    )


def get_creative_prompts(
    language: str = DEFAULT_LANGUAGE,
    marketing_type: str = DEFAULT_MARKETING_TYPE,
) -> tuple[str, str]:
    """Return (SYSTEM, USER_TEMPLATE) for the creative node."""
    mod = _load("creative", language)
    return (
        _pick(mod.SYSTEM, marketing_type),
        _pick(mod.USER_TEMPLATE, marketing_type),
    )


def get_media_buying_prompts(language: str = DEFAULT_LANGUAGE) -> tuple[str, str]:
    """Return (SYSTEM, USER_TEMPLATE) for the media buying node."""
    mod = _load("media_buying", language)
    return mod.SYSTEM, mod.USER_TEMPLATE


def get_strings(language: str = DEFAULT_LANGUAGE) -> object:
    """Return the strings module for the given language."""
    return _load("strings", language)
