"""
Agent I/O Runtime Logger — AutoMark AI
========================================
Automatically logs every node's inputs and outputs to .agent_logs/ in the
repo root during normal web-app operation.  No separate script needed —
just run the app normally and open the log files after a session.

Two files are written per server start:
  .agent_logs/run_YYYYMMDD_HHMMSS.log    — human-readable, step-by-step
  .agent_logs/run_YYYYMMDD_HHMMSS.jsonl  — one JSON record per line (for scripts/grep)

Each node run produces four possible entries:
  NODE_START      — node fired; shows all non-empty inputs
  NODE_END        — node finished; shows its output delta + duration
  NODE_INTERRUPT  — node issued a human-in-the-loop pause
  NODE_ERROR      — node raised an unexpected exception

Disable without code changes:  add  AGENT_LOG=false  to .env
Tune verbosity:                 AGENT_LOG_MAX_STR=800  (default 500)
                                AGENT_LOG_MAX_LIST=12  (default 8)
"""

import contextvars
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Kill-switch ────────────────────────────────────────────────────────────────
_ENABLED = os.getenv("AGENT_LOG", "true").lower() not in ("false", "0", "no")

# ── Context variable: holds the active thread_id so wrapped nodes can tag logs ─
CURRENT_THREAD_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "agent_log_thread_id", default="unknown"
)


def set_thread(thread_id: str) -> None:
    """Call once per graph.stream() invocation to tag all entries with the session ID."""
    CURRENT_THREAD_ID.set(thread_id)


# ── Log file paths (one pair per server start) ─────────────────────────────────
_LOG_DIR = Path(__file__).resolve().parents[2] / ".agent_logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_RUN_TS   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
_LOG_PATH  = _LOG_DIR / f"run_{_RUN_TS}.log"
_JSONL_PATH = _LOG_DIR / f"run_{_RUN_TS}.jsonl"

_file_lock = threading.Lock()   # one writer at a time across threads

# ── Tuning ─────────────────────────────────────────────────────────────────────
_MAX_STR  = int(os.getenv("AGENT_LOG_MAX_STR",  "500"))
_MAX_LIST = int(os.getenv("AGENT_LOG_MAX_LIST", "8"))

# Keys whose values are raw base64 image data — always redacted
_IMAGE_DATA_KEYS = frozenset({"images", "image_history", "generated_images"})

# ── LangGraph interrupt exception (loaded once, tolerant of version differences) ─
_INTERRUPT_EXC: type | None = None
try:
    from langgraph.errors import GraphInterrupt as _GI
    _INTERRUPT_EXC = _GI
except ImportError:
    try:
        from langgraph.exceptions import GraphInterrupt as _GI2  # type: ignore
        _INTERRUPT_EXC = _GI2
    except ImportError:
        pass  # fallback: detect by class name


# ── Sanitiser ──────────────────────────────────────────────────────────────────

def _sanitize(obj: Any, _d: int = 0) -> Any:
    """Recursively strip binary data and clip long strings for safe logging."""
    if _d > 5:
        return "…"
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        return obj[:_MAX_STR] + f" …[+{len(obj)-_MAX_STR} chars]" if len(obj) > _MAX_STR else obj
    if isinstance(obj, list):
        if len(obj) > _MAX_LIST:
            head = [_sanitize(x, _d + 1) for x in obj[:_MAX_LIST]]
            head.append(f"…[{len(obj) - _MAX_LIST} more items]")
            return head
        return [_sanitize(x, _d + 1) for x in obj]
    if isinstance(obj, dict):
        out: dict = {}
        for k, v in obj.items():
            if k in _IMAGE_DATA_KEYS:
                n = len(v) if isinstance(v, list) else (1 if v else 0)
                out[k] = f"<{n} image(s) — data redacted>"
            else:
                out[k] = _sanitize(v, _d + 1)
        return out
    return repr(obj)[:_MAX_STR]


# ── Low-level write ────────────────────────────────────────────────────────────

def _write(text: str, record: dict) -> None:
    """Write one entry to both log files under the file lock."""
    if not _ENABLED:
        return
    with _file_lock:
        try:
            with _LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(text + "\n")
            with _JSONL_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("agent_logger: write failed — %s", exc)


# ── Formatting helpers ─────────────────────────────────────────────────────────

_W     = 72
_DIV   = "─" * _W
_HEAVY = "═" * _W


def _now_hms() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def _fmtval(v: Any) -> str:
    """Single-line representation, or multi-line for nested objects."""
    if isinstance(v, (dict, list)):
        compact = json.dumps(v, ensure_ascii=False)
        if len(compact) <= 110:
            return compact
        return json.dumps(v, ensure_ascii=False, indent=2)
    return str(v)


def _indent(text: str, pad: int = 6) -> str:
    p = " " * pad
    return "\n".join(p + line for line in text.splitlines())


def _kv_lines(d: dict, indent: int = 4) -> list[str]:
    """Render a dict as indented key: value lines."""
    pad = " " * indent
    lines: list[str] = []
    for k, v in d.items():
        fv = _fmtval(v)
        if "\n" in fv:
            lines.append(f"{pad}{k}:")
            lines.append(_indent(fv, indent + 2))
        else:
            lines.append(f"{pad}{k:<32}: {fv}")
    return lines


# ── Public high-level API ──────────────────────────────────────────────────────

def log_session_start(thread_id: str, budget: float, language: str, **kwargs) -> None:
    """Write a banner at the beginning of a new campaign session."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    extra = (f"\n  Extra   : {kwargs}") if kwargs else ""
    text = (
        f"\n{_HEAVY}\n"
        f"  SESSION START\n"
        f"  Thread   : {thread_id}\n"
        f"  UTC time : {ts}\n"
        f"  Budget   : {budget}   Language: {language}"
        f"{extra}\n"
        f"{_HEAVY}"
    )
    _write(text, {
        "event": "SESSION_START", "ts": _now_hms(),
        "thread_id": thread_id, "budget": budget, "language": language, **kwargs,
    })


def log_session_end(thread_id: str, stage: str) -> None:
    """Write a banner when the pipeline completes (no more interrupts)."""
    text = (
        f"\n{_HEAVY}\n"
        f"  SESSION END   thread: {thread_id}   final_stage: {stage}\n"
        f"{_HEAVY}"
    )
    _write(text, {"event": "SESSION_END", "ts": _now_hms(), "thread_id": thread_id, "stage": stage})


# ── Node wrapper ───────────────────────────────────────────────────────────────

def wrap_node(name: str, fn: Callable) -> Callable:
    """
    Return a version of *fn* that logs its inputs and outputs to the run log.
    LangGraph sees exactly the same function signature — completely transparent.
    """
    if not _ENABLED:
        return fn

    def _wrapper(state: dict) -> dict:
        thread_id = CURRENT_THREAD_ID.get()
        t0 = time.perf_counter()
        ts_start = _now_hms()

        # ── NODE_START ─────────────────────────────────────────────────────────
        # Only include non-empty state fields so early nodes aren't buried in Nones
        populated = {k: v for k, v in state.items()
                     if v is not None and v != "" and v != [] and v != {}}
        san_in = _sanitize(populated)
        avail  = list(san_in.keys())

        entry_lines: list[str] = [
            f"\n{_DIV}",
            f"  [{ts_start}] ▶  {name}   (thread: {thread_id})",
            f"  Available inputs : {', '.join(avail) or '(none)'}",
            f"{_DIV}",
            "  INPUTS:",
        ]
        entry_lines.extend(_kv_lines(san_in))

        _write("\n".join(entry_lines), {
            "event": "NODE_START", "ts": ts_start,
            "thread_id": thread_id, "node": name,
            "input_keys": avail, "inputs": san_in,
        })

        # ── Run the actual node ────────────────────────────────────────────────
        try:
            result = fn(state)
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            ts_end  = _now_hms()

            san_out = _sanitize(result or {})
            exit_lines: list[str] = [
                f"  [{ts_end}] ◀  {name}   (+{elapsed}ms)",
                "  OUTPUTS:",
            ]
            exit_lines.extend(_kv_lines(san_out))
            exit_lines.append(_HEAVY)

            _write("\n".join(exit_lines), {
                "event": "NODE_END", "ts": ts_end,
                "thread_id": thread_id, "node": name,
                "duration_ms": elapsed, "outputs": san_out,
            })
            return result

        except Exception as exc:
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            ts_exc  = _now_hms()

            # Detect LangGraph interrupt (normal flow, not an error)
            is_interrupt = (
                (_INTERRUPT_EXC is not None and isinstance(exc, _INTERRUPT_EXC))
                or "interrupt" in type(exc).__name__.lower()
            )

            if is_interrupt:
                # Unpack the interrupt value
                iv = exc.args[0] if exc.args else {}
                if isinstance(iv, (list, tuple)) and iv:
                    iv = iv[0]
                san_iv = _sanitize(iv if isinstance(iv, dict) else {"value": str(iv)})
                stage  = san_iv.get("stage", "unknown") if isinstance(san_iv, dict) else "unknown"

                intr_lines: list[str] = [
                    f"  [{ts_exc}] ⏸  {name}   INTERRUPTED   (+{elapsed}ms)",
                    f"  Interrupt stage : {stage}",
                    "  INTERRUPT PAYLOAD:",
                ]
                if isinstance(san_iv, dict):
                    intr_lines.extend(_kv_lines(san_iv))
                intr_lines.append(_HEAVY)

                _write("\n".join(intr_lines), {
                    "event": "NODE_INTERRUPT", "ts": ts_exc,
                    "thread_id": thread_id, "node": name,
                    "duration_ms": elapsed, "stage": stage,
                    "interrupt_payload": san_iv,
                })
            else:
                err_lines = [
                    f"  [{ts_exc}] ✗  {name}   ERROR   (+{elapsed}ms)",
                    f"  {type(exc).__name__}: {str(exc)[:400]}",
                    _HEAVY,
                ]
                _write("\n".join(err_lines), {
                    "event": "NODE_ERROR", "ts": ts_exc,
                    "thread_id": thread_id, "node": name,
                    "duration_ms": elapsed,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                })

            raise  # always re-raise — LangGraph must handle both interrupts and errors

    _wrapper.__name__     = fn.__name__
    _wrapper.__qualname__ = fn.__qualname__
    _wrapper.__doc__      = fn.__doc__
    return _wrapper
