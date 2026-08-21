"""Long-term per-client memory store — Phase 5.

Demo implementation: JSON files in a .memory/ directory next to the
backend package. Each client gets one JSON file keyed by compound_name
(normalised to a safe filename).

Production path: swap the _read/_write functions to use pgvector
with hybrid retrieval. The recall()/merge() interface stays identical,
so the demo path doesn't need to be rewritten.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_STORE_DIR = Path(__file__).resolve().parents[2] / ".client_memory"


def _client_key(client_id: str) -> str:
    """Normalise compound name to a safe file key."""
    return re.sub(r"[^a-z0-9_]+", "_", client_id.lower().strip()).strip("_") or "unknown"


def _store_path(client_id: str) -> Path:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    return _STORE_DIR / f"{_client_key(client_id)}.json"


def recall(client_id: str) -> dict:
    """
    Retrieve long-term memory for a client.

    Returns a dict with past session summaries, known compounds,
    performance baselines, and compliance notes. Empty dict if new client.
    """
    if not client_id:
        return {}
    path = _store_path(client_id)
    if not path.exists():
        logger.info("client_store.recall: new client '%s'", client_id)
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info(
            "client_store.recall: '%s' — %d past sessions",
            client_id, len(data.get("sessions", [])),
        )
        return data
    except Exception as e:
        logger.warning("client_store.recall: failed to read '%s': %s", client_id, e)
        return {}


def merge(client_id: str, summary: dict) -> None:
    """
    Persist a new session summary into the client's long-term store.

    summary should contain:
      - compound_name, location, price_tier, outcome (published/abandoned),
        decisions (list), performance_notes (plain text)
    """
    if not client_id:
        return

    existing = recall(client_id)
    sessions = existing.get("sessions", [])
    sessions.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        **summary,
    })

    # Keep at most 20 sessions; prune oldest first
    sessions = sessions[-20:]

    # Extract known compounds for quick context injection
    known_compounds = list({
        s.get("compound_name", "") for s in sessions if s.get("compound_name")
    })

    data = {
        "client_id": client_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sessions": sessions,
        "known_compounds": known_compounds,
        "total_sessions": len(sessions),
    }

    try:
        _store_path(client_id).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "client_store.merge: '%s' — %d sessions total", client_id, len(sessions)
        )
    except Exception as e:
        logger.error("client_store.merge: failed to write '%s': %s", client_id, e)


def build_context_snippet(client_memory: dict, language: str = "en") -> str:
    """
    Build a short context string injected into the orchestrator prompt
    so Mark begins the session already knowing the client.
    """
    if not client_memory or not client_memory.get("sessions"):
        return ""

    sessions = client_memory["sessions"]
    compounds = client_memory.get("known_compounds", [])
    n = client_memory.get("total_sessions", 0)

    if language == "ar":
        lines = [f"معلومات عن العميل من جلسات سابقة ({n} جلسة):"]
        if compounds:
            lines.append(f"- مشاريع سبق العمل عليها: {', '.join(compounds)}")
        last = sessions[-1]
        if last.get("performance_notes"):
            lines.append(f"- ملاحظات أداء سابقة: {last['performance_notes']}")
    else:
        lines = [f"Returning client context ({n} past session(s)):"]
        if compounds:
            lines.append(f"- Known compounds: {', '.join(compounds)}")
        last = sessions[-1]
        if last.get("performance_notes"):
            lines.append(f"- Previous performance notes: {last['performance_notes']}")

    return "\n".join(lines)
