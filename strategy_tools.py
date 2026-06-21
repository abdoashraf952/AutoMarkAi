"""Deterministic tools for the Strategist agent (strategy_node).

These are plain Python helpers (no LLM) so the *facts* — peak-time references,
timezones, and the Meta schedule format — are reliable and explainable. The LLM
reasons over them; it doesn't invent them. The only non-deterministic tool here
is `web_search`, which is opt-in via the ENABLE_WEB_SEARCH env var.
"""

import logging
import os
from datetime import date

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Optional web search (opt-in via ENABLE_WEB_SEARCH)                   #
# ------------------------------------------------------------------ #

def web_search_enabled() -> bool:
    """True when ENABLE_WEB_SEARCH is set to a truthy value in the environment."""
    return os.getenv("ENABLE_WEB_SEARCH", "false").strip().lower() in ("1", "true", "yes", "on")


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Best-effort DuckDuckGo search (no API key). Returns [] if disabled or unavailable.

    Never raises — the strategy pipeline must keep working even if search fails.
    """
    if not web_search_enabled():
        return []
    try:
        try:
            from ddgs import DDGS            # newer package name
        except ImportError:
            from duckduckgo_search import DDGS  # older package name
        with DDGS() as ddgs:
            rows = list(ddgs.text(query, max_results=max_results))
        return [{"title": r.get("title", ""), "snippet": r.get("body", "")} for r in rows]
    except Exception as e:  # import error, network error, rate limit, etc.
        logger.warning("web_search unavailable (%s) — continuing without live trends", e)
        return []


def build_search_query(plan: dict) -> str:
    """Build a focused query about audience + timing for this product/service."""
    product = plan.get("product_type") or plan.get("product_description") or "product"
    return (
        f"best time to post and target audience for {product} ads "
        f"on Instagram, TikTok and Facebook {date.today().year}"
    )


def format_web_context(results: list[dict], language: str = "en") -> str:
    """Turn search rows into a compact prompt block (empty string when no results)."""
    if not results:
        return ""
    header = (
        "LIVE WEB TRENDS (recent, use as supporting signal):"
        if language != "ar"
        else "اتجاهات حديثة من الويب (استخدمها كإشارة مساعدة):"
    )
    lines = [header]
    for r in results[:5]:
        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        if title or snippet:
            lines.append(f"- {title}: {snippet}"[:300])
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Dayparting knowledge base (curated best-time guidance)              #
# ------------------------------------------------------------------ #

_DAYPARTING_REFERENCE_EN = (
    "DAYPARTING REFERENCE — general best posting windows (audience LOCAL time):\n"
    "- Gen-Z / young women (beauty, fashion, self-care): weekday 12:00-13:00 and "
    "22:00-01:00; weekend late-morning wake-up 11:00-13:00.\n"
    "- Gen-Z / young men (gaming, tech, sports): weekday evening 19:00-23:00; "
    "weekend afternoon 14:00-18:00.\n"
    "- Millennials / professionals: weekday 07:00-09:00 (commute) and 17:00-19:00; "
    "lunch 12:00-13:00.\n"
    "- Parents: early 06:00-08:00, mid-morning 09:00-11:00, after kids sleep 21:00-23:00.\n"
    "- B2B / business decision-makers: weekday 08:00-10:00 and 16:00-18:00; avoid weekends.\n"
    "- Local service customers: weekday business hours + early evening 18:00-21:00.\n"
    "- General adult consumer: weekday 12:00-13:00 and 19:00-22:00; weekend mornings.\n"
    "Platform notes: Instagram peaks late-morning & evening; TikTok peaks evening & "
    "late-night; Facebook peaks midday & early-evening.\n"
)

_DAYPARTING_REFERENCE_AR = (
    "مرجع أوقات النشر — أفضل الأوقات عموماً (بتوقيت الجمهور المحلي):\n"
    "- البنات الصغيرين (مكياج، موضة، العناية بالنفس): أيام الأسبوع 12:00-13:00 و"
    "22:00-01:00؛ في الإجازة الصبح المتأخر 11:00-13:00.\n"
    "- الشباب الصغير (جيمنج، تكنولوجيا، رياضة): بالليل 19:00-23:00؛ الإجازة بعد الضهر.\n"
    "- الموظفين والمحترفين: الصبح 07:00-09:00 وبعد الشغل 17:00-19:00؛ وقت الغدا 12:00-13:00.\n"
    "- الأمهات: بدري 06:00-08:00، وقبل الضهر 09:00-11:00، وبعد ما العيال تنام 21:00-23:00.\n"
    "- قطاع الأعمال (B2B): أيام الأسبوع 08:00-10:00 و16:00-18:00؛ بعّد عن نهاية الأسبوع.\n"
    "- عملاء الخدمات المحلية: ساعات العمل + أول الليل 18:00-21:00.\n"
    "- المستهلك العادي: 12:00-13:00 و19:00-22:00؛ وصباح الإجازات.\n"
    "ملاحظات المنصات: إنستجرام بيعلى الصبح المتأخر وبالليل؛ تيك توك بالليل والليل المتأخر؛ "
    "فيسبوك وقت الضهر وأول المغرب.\n"
)


def get_dayparting_reference(language: str = "en") -> str:
    """Return the curated best-time-to-post reference for the prompt."""
    return _DAYPARTING_REFERENCE_AR if language == "ar" else _DAYPARTING_REFERENCE_EN


# ------------------------------------------------------------------ #
# Timezone resolver (curated; offsets are approximate, ignore DST)    #
# ------------------------------------------------------------------ #

# ISO-3166-1 alpha-2 → (IANA name, representative UTC offset)
_COUNTRY_TZ: dict[str, tuple[str, str]] = {
    "EG": ("Africa/Cairo", "+02:00"),
    "SA": ("Asia/Riyadh", "+03:00"),
    "AE": ("Asia/Dubai", "+04:00"),
    "KW": ("Asia/Kuwait", "+03:00"),
    "QA": ("Asia/Qatar", "+03:00"),
    "MA": ("Africa/Casablanca", "+01:00"),
    "JO": ("Asia/Amman", "+03:00"),
    "US": ("America/New_York", "-04:00"),
    "GB": ("Europe/London", "+01:00"),
    "DE": ("Europe/Berlin", "+02:00"),
    "FR": ("Europe/Paris", "+02:00"),
    "IN": ("Asia/Kolkata", "+05:30"),
}

_LANG_DEFAULT_TZ: dict[str, tuple[str, str]] = {
    "ar": ("Africa/Cairo", "+02:00"),
    "en": ("UTC", "+00:00"),
}


def resolve_timezone(locations: list[str] | None, language: str = "en") -> tuple[str, str]:
    """Pick a primary (IANA timezone, UTC offset) from target locations or locale.

    Falls back to the language default, then UTC. Offsets are approximate and do
    not track DST — fine for an advisory schedule.
    """
    for code in (locations or []):
        hit = _COUNTRY_TZ.get(str(code).strip().upper())
        if hit:
            return hit
    return _LANG_DEFAULT_TZ.get(language, ("UTC", "+00:00"))


# ------------------------------------------------------------------ #
# Meta ad-schedule formatter                                          #
# ------------------------------------------------------------------ #

# Meta adset_schedule uses day integers 0=Sunday … 6=Saturday
_DAY_TO_META: dict[str, int] = {
    "sun": 0, "sunday": 0,
    "mon": 1, "monday": 1,
    "tue": 2, "tues": 2, "tuesday": 2,
    "wed": 3, "weds": 3, "wednesday": 3,
    "thu": 4, "thur": 4, "thurs": 4, "thursday": 4,
    "fri": 5, "friday": 5,
    "sat": 6, "saturday": 6,
}


def _hhmm_to_minutes(value: str) -> int | None:
    """'HH:MM' → minutes from midnight (0-1439), or None if unparseable."""
    try:
        h, m = str(value).strip().split(":")
        total = int(h) * 60 + int(m)
        return max(0, min(total, 1439))
    except (ValueError, AttributeError):
        return None


def _days_to_indices(days: list) -> list[int]:
    out: list[int] = []
    for d in days or []:
        idx = _DAY_TO_META.get(str(d).strip().lower())
        if idx is not None and idx not in out:
            out.append(idx)
    return sorted(out)


def to_meta_adset_schedule(peak_windows: list[dict]) -> list[dict]:
    """Convert human peak windows → Meta `adset_schedule` entries.

    Windows that cross midnight (end <= start) are split into two valid entries.
    `timezone_type: USER` means the times are in the audience's local timezone.
    """
    entries: list[dict] = []
    for win in peak_windows or []:
        days = _days_to_indices(win.get("days", []))
        start = _hhmm_to_minutes(win.get("start", ""))
        end = _hhmm_to_minutes(win.get("end", ""))
        if not days or start is None or end is None:
            continue
        if end > start:
            entries.append({"days": days, "start_minute": start, "end_minute": end,
                            "timezone_type": "USER"})
        else:  # crosses midnight → split
            entries.append({"days": days, "start_minute": start, "end_minute": 1439,
                            "timezone_type": "USER"})
            if end > 0:
                entries.append({"days": days, "start_minute": 0, "end_minute": end,
                                "timezone_type": "USER"})
    return entries


def compute_start_time(peak_windows: list[dict], offset: str, today: str | None = None) -> str:
    """Best single ad start_time (ISO 8601 with offset), from the first window."""
    today = today or date.today().isoformat()
    for win in peak_windows or []:
        if _hhmm_to_minutes(win.get("start", "")) is not None:
            return f"{today}T{str(win['start']).strip()}:00{offset}"
    return ""


# ------------------------------------------------------------------ #
# Orchestration helpers used by strategy_node / consumers             #
# ------------------------------------------------------------------ #

def finalize_schedule(strategy: dict, plan: dict, language: str = "en",
                      today: str | None = None) -> dict:
    """Post-process the LLM strategy: resolve timezone, build the Meta schedule,
    and a best start_time. Marks the schedule advisory (not enforced on Meta)."""
    persona = strategy.get("target_persona") or {}
    locations = persona.get("locations") or []
    tz_name, offset = resolve_timezone(locations, language)

    strategy["timezone"] = strategy.get("timezone") or tz_name
    strategy["timezone_offset"] = offset

    schedule = dict(strategy.get("schedule") or {})
    windows = schedule.get("peak_windows") or []
    schedule["strategy"] = schedule.get("strategy") or "dayparting"
    schedule["meta_adset_schedule"] = to_meta_adset_schedule(windows)
    schedule["best_single_start_time"] = compute_start_time(windows, offset, today)
    schedule["enforced_on_meta"] = False
    schedule["note"] = (
        "Advisory only — shown as guidance; not enforced on Meta "
        "(the campaign uses a daily budget)."
    )
    strategy["schedule"] = schedule
    return strategy


def build_strategy_context(strategy: dict | None, language: str = "en") -> str:
    """A compact context block for creative_node / media_buying_node prompts.

    Returns '' when there is no strategy yet, so callers can append safely.
    """
    if not strategy:
        return ""
    persona = strategy.get("target_persona") or {}
    channels = strategy.get("channels") or {}
    schedule = strategy.get("schedule") or {}
    windows = schedule.get("peak_windows") or []
    angles = strategy.get("messaging_angles") or []

    def _win(w: dict) -> str:
        days = ",".join(str(d) for d in (w.get("days") or []))
        return f"{w.get('label','')} [{days} {w.get('start','')}-{w.get('end','')}]".strip()

    win_str = "; ".join(_win(w) for w in windows) or "—"
    tz = strategy.get("timezone", "")

    if language == "ar":
        return (
            "ملف الجمهور والاستراتيجية (استخدمها لضبط النبرة والاستهداف):\n"
            f"- الجمهور: {persona.get('primary_segment','')} "
            f"({persona.get('gender','all')}، {persona.get('age_min','')}-{persona.get('age_max','')})\n"
            f"- الاهتمامات: {', '.join(persona.get('interests', []) or [])}\n"
            f"- القنوات: {', '.join(channels.get('primary', []) or [])}\n"
            f"- زوايا الرسالة: {', '.join(angles)}\n"
            f"- أفضل أوقات النشر ({tz}): {win_str}\n"
        )
    return (
        "TARGET AUDIENCE & STRATEGY (use this to tailor tone, targeting, timing):\n"
        f"- Audience: {persona.get('primary_segment','')} "
        f"({persona.get('gender','all')}, {persona.get('age_min','')}-{persona.get('age_max','')})\n"
        f"- Interests: {', '.join(persona.get('interests', []) or [])}\n"
        f"- Channels: {', '.join(channels.get('primary', []) or [])}\n"
        f"- Messaging angles to lean into: {', '.join(angles)}\n"
        f"- Best posting windows ({tz}): {win_str}\n"
    )
