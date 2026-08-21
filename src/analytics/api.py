"""
src/analytics/api.py — AutoMark AI

REST + SSE interface to the analytics pipeline, mounted by src/main.py under
/api/analytics.

The analytics module was originally Streamlit-only, with the LangGraph calls
inlined in the UI. This module exposes that same pipeline over HTTP so the
Next.js frontend can drive it, and so analyses become per-user records rather
than per-browser-session state.

The graph is synchronous (LangGraph nodes and pandas both block), so a run is
executed on a worker thread and progress is pushed to the client over SSE —
the same pattern the campaign module uses, so the frontend reuses its SSE
client.

Flow
----
    POST /sessions                      create a session
    POST /sessions/{id}/upload          upload a CSV/Excel file
    POST /sessions/{id}/analyze         start the pipeline (returns immediately)
    GET  /sessions/{id}/stream          SSE progress + completion
    GET  /sessions/{id}/result          full result once finished
    POST /sessions/{id}/chat            ask a follow-up question
    GET  /sessions/{id}/chat            chat history
    GET  /analyses                      the caller's past analyses
    GET  /analyses/{analysis_id}        one past analysis
    GET  /crm-tables                    CRM tables available to analyse
    POST /sessions/{id}/load-crm-table  analyse a CRM table instead of a file
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.config import settings
from src.shared.auth import require_user

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}

# Human-readable progress, keyed by the `current_step` value each node writes
# into state (not the node's name — the nodes report the step they finished).
_STEP_LABELS = {
    "start": "Starting",
    "data_loaded": "Dataset loaded",
    "profiled": "Profiled columns and data quality",
    "business_analyzed": "Detected the business domain",
    "kpis_discovered": "Discovered KPIs",
    "insights_generated": "Generated insights",
    "visualizations_recommended": "Recommended visualizations",
    "report_generated": "Wrote the executive report",
    "complete": "Finishing up",
    "error": "Failed",
}


# ─────────────────────────────────────────────────────────────────────────────
# In-process session store
# ─────────────────────────────────────────────────────────────────────────────
# Mirrors the campaign module: run state lives in memory, finished analyses are
# persisted to PostgreSQL and read back through the repository.

_sessions: dict[str, dict] = {}


def _new_session(user_id: str) -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = {
        "session_id": sid,
        "user_id": user_id,
        "status": "idle",          # idle | running | done | error
        "file_name": None,
        "file_path": None,
        "file_size_bytes": 0,
        "state": None,             # final graph state dict
        "analysis_id": None,
        "error": None,
        "event_queue": asyncio.Queue(),
    }
    return sid


def _get_session(session_id: str, user: dict) -> dict:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, f"Session '{session_id}' not found")
    if session["user_id"] != user["user_id"]:
        raise HTTPException(403, "This session belongs to another user")
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

def _persist(state_dict: dict, session_id: str, user_id: str) -> Optional[str]:
    """Write a finished run to PostgreSQL. Returns the analysis id, or None."""
    from src.analytics.database import AnalyticsRepository
    from src.analytics.schemas.state import AnalyticsState
    from src.shared.db import sync_session

    try:
        state = AnalyticsState(**state_dict)
        with sync_session() as db:
            repo = AnalyticsRepository(db)
            repo.get_or_create_session(session_id, user_id=user_id)
            analysis = repo.create_analysis(state)
            repo.update_analysis(analysis.id, state)
            if state.kpis:
                repo.save_kpis(analysis.id, state.kpis)
            if state.insights:
                repo.save_insights(analysis.id, state.insights)
            return analysis.id
    except Exception as exc:  # persistence must never fail the run
        logger.warning("analytics: could not persist analysis — %s", exc)
        return None


def _serialise(state: dict | None) -> dict:
    """Convert a graph state dict into a JSON-safe response payload."""
    if not state:
        return {}
    from src.analytics.schemas.state import AnalyticsState

    model = AnalyticsState(**state)
    return {
        "session_id": model.session_id,
        "analysis_id": model.analysis_id,
        "file_name": model.file_name,
        "file_size_bytes": model.file_size_bytes,
        "business_domain": model.business_domain,
        "domain_confidence": model.domain_confidence,
        "domain_reasoning": model.domain_reasoning,
        "dataset_summary": model.dataset_summary.model_dump(mode="json")
        if model.dataset_summary
        else None,
        "profiling_result": model.profiling_result.model_dump(mode="json")
        if model.profiling_result
        else None,
        "kpis": [k.model_dump(mode="json") for k in model.kpis],
        "insights": [i.model_dump(mode="json") for i in model.insights],
        "visualizations": model.visualization_recommendations,
        "executive_report": model.executive_report,
        "report_generated_at": model.report_generated_at,
        "current_step": model.current_step,
        "error_message": model.error_message,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_graph_sync(initial_state: dict, push) -> dict:
    """Stream the graph on this worker thread, pushing progress as it goes."""
    from src.analytics.graph.workflow import get_analytics_graph

    graph = get_analytics_graph()
    final: dict = dict(initial_state)
    seen: set[str] = set()

    for chunk in graph.stream(initial_state, stream_mode="values"):
        final = chunk
        step = chunk.get("current_step")
        if step and step not in seen:
            seen.add(step)
            push(
                {
                    "event": "progress",
                    "step": step,
                    "message": _STEP_LABELS.get(step, step.replace("_", " ").title()),
                }
            )
    return final


async def _run_analysis(session: dict, initial_state: dict) -> None:
    """Execute a pipeline run and drive the session's SSE queue."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = session["event_queue"]

    def push(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    session["status"] = "running"
    session["error"] = None
    push({"event": "started", "session_id": session["session_id"]})

    try:
        final = await asyncio.to_thread(_run_graph_sync, initial_state, push)

        if final.get("error_message"):
            session["status"] = "error"
            session["error"] = final["error_message"]
            session["state"] = final
            push({"event": "error", "message": final["error_message"]})
            return

        analysis_id = await asyncio.to_thread(
            _persist, final, session["session_id"], session["user_id"]
        )
        if analysis_id:
            final["analysis_id"] = analysis_id
            session["analysis_id"] = analysis_id

        session["state"] = final
        session["status"] = "done"
        push({"event": "complete", "analysis_id": analysis_id})

    except Exception as exc:
        logger.exception("analytics: pipeline failed")
        session["status"] = "error"
        session["error"] = str(exc)
        push({"event": "error", "message": str(exc)})


# ─────────────────────────────────────────────────────────────────────────────
# Session endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/sessions", summary="Create an analytics session", tags=["Analytics"])
async def create_session(user: dict = Depends(require_user)) -> dict:
    return {"session_id": _new_session(user["user_id"])}


@router.post(
    "/sessions/{session_id}/upload",
    summary="Upload a CSV or Excel dataset",
    tags=["Analytics"],
)
async def upload_dataset(
    session_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
) -> dict:
    session = _get_session(session_id, user)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            400, f"Unsupported file type '{suffix}'. Upload a .csv, .xlsx, or .xls file."
        )

    # Namespace by session so two users uploading "data.csv" cannot collide.
    dest_dir = UPLOAD_DIR / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(file.filename).name

    size = 0
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    with dest.open("wb") as fh:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                fh.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    413, f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit"
                )
            fh.write(chunk)

    session.update(
        file_name=dest.name,
        file_path=str(dest),
        file_size_bytes=size,
        status="idle",
        state=None,
        analysis_id=None,
    )
    return {"file_name": dest.name, "file_size_bytes": size}


@router.post(
    "/sessions/{session_id}/analyze",
    summary="Run the analytics pipeline",
    tags=["Analytics"],
)
async def analyze(session_id: str, user: dict = Depends(require_user)) -> dict:
    session = _get_session(session_id, user)

    if not session["file_path"]:
        raise HTTPException(409, "Upload a dataset before running the analysis")
    if session["status"] == "running":
        raise HTTPException(409, "An analysis is already running for this session")

    initial_state = {
        "session_id": session_id,
        "file_name": session["file_name"],
        "file_path": session["file_path"],
        "file_size_bytes": session["file_size_bytes"],
        "user_query": "Analyze this dataset",
        "is_follow_up": False,
        "chat_history": [],
        "kpis": [],
        "insights": [],
        "visualization_recommendations": [],
        "current_step": "start",
        "error_message": None,
    }

    asyncio.create_task(_run_analysis(session, initial_state))
    return {"status": "running", "session_id": session_id}


@router.get(
    "/sessions/{session_id}/stream",
    summary="SSE stream of pipeline progress",
    tags=["Analytics"],
)
async def stream(
    session_id: str,
    token: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """SSE progress stream.

    The browser's EventSource cannot set an Authorization header, so this
    endpoint also accepts the JWT as a `?token=` query parameter. The header is
    preferred when both are present.
    """
    from src.shared.auth import decode_token, extract_user

    user = extract_user(authorization) or (decode_token(token) if token else None)
    if not user:
        raise HTTPException(401, "Authentication required")

    session = _get_session(session_id, user)
    queue: asyncio.Queue = session["event_queue"]

    async def event_source() -> AsyncGenerator[str, None]:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"     # comment frame; keeps proxies happy
                continue

            yield f"data: {json.dumps(event)}\n\n"
            if event.get("event") in ("complete", "error"):
                break

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/sessions/{session_id}/state",
    summary="Current session status",
    tags=["Analytics"],
)
async def session_state(session_id: str, user: dict = Depends(require_user)) -> dict:
    session = _get_session(session_id, user)
    return {
        "session_id": session_id,
        "status": session["status"],
        "file_name": session["file_name"],
        "analysis_id": session["analysis_id"],
        "error": session["error"],
    }


@router.get(
    "/sessions/{session_id}/result",
    summary="Full analysis result",
    tags=["Analytics"],
)
async def result(session_id: str, user: dict = Depends(require_user)) -> dict:
    session = _get_session(session_id, user)
    if session["status"] == "running":
        raise HTTPException(409, "Analysis still running")
    if not session["state"]:
        raise HTTPException(404, "No analysis has been run for this session")
    return _serialise(session["state"])


# ─────────────────────────────────────────────────────────────────────────────
# Chart previews
# ─────────────────────────────────────────────────────────────────────────────
# The Streamlit UI aggregated the dataframe with pandas and drew charts inline.
# The React UI needs the same aggregation, so it happens here and only the
# reduced series crosses the wire — never the raw dataset.

_MAX_CATEGORIES = 15
_MAX_PIE_SLICES = 8
_MAX_SCATTER_POINTS = 500
_MAX_CHARTS = 6

# Recommendation types that are not plottable series. "card" is a single
# headline number — the Overview tab already shows those as stat tiles, and a
# one-value bar chart would be the wrong form for it.
_NON_PLOTTABLE = {"card", "kpi", "table", "matrix", "gauge", "slicer", "text"}

# How each recommended type maps onto the chart forms the frontend can draw.
_TYPE_MAP = {
    "bar": "bar", "clustered": "bar", "column": "bar", "stacked": "bar",
    "waterfall": "bar", "combo": "bar", "histogram": "bar",
    "line": "line", "area": "line",
    "pie": "pie", "donut": "donut",
    "scatter": "scatter",
}


def _build_charts(file_path: str, recommendations: list[dict]) -> list[dict]:
    """Aggregate the dataset into plot-ready series.

    The recommender does not guarantee which of x_axis/y_axis holds the measure
    and which holds the dimension — it commonly returns the measure in x_axis
    for horizontal bars. So the axes are resolved by dtype rather than trusted
    positionally: the numeric column is the measure, the other is the grouping
    dimension.
    """
    import pandas as pd

    from src.analytics.agents.data_loader import get_cached_dataframe

    df = get_cached_dataframe(file_path)
    if df is None:
        return []

    charts: list[dict] = []
    for rec in recommendations:
        if len(charts) >= _MAX_CHARTS:
            break

        raw_type = str(rec.get("chart_type", "")).lower().strip()
        if raw_type in _NON_PLOTTABLE:
            continue
        chart_type = _TYPE_MAP.get(raw_type)
        if chart_type is None:
            continue

        title = rec.get("title") or rec.get("chart_name") or ""

        # Candidate columns, from the declared axes plus any measures/dimensions.
        axes = [rec.get("x_axis"), rec.get("y_axis")]
        axes += list(rec.get("measures") or [])
        axes += list(rec.get("dimensions") or [])
        cols = [c for c in axes if isinstance(c, str) and c in df.columns]
        # de-duplicate, preserve order
        cols = list(dict.fromkeys(cols))
        if not cols:
            continue

        numeric = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
        non_numeric = [c for c in cols if c not in numeric]

        try:
            if chart_type == "scatter" and len(numeric) >= 2:
                xc, yc = numeric[0], numeric[1]
                sample = df[[xc, yc]].dropna()
                if len(sample) > _MAX_SCATTER_POINTS:
                    sample = sample.sample(_MAX_SCATTER_POINTS, random_state=0)
                charts.append({
                    "type": "scatter", "title": title, "x": xc, "y": yc,
                    "points": [{"x": float(a), "y": float(b)}
                               for a, b in zip(sample[xc], sample[yc])],
                })
                continue

            # Everything else is dimension → aggregated measure.
            if not non_numeric:
                continue
            dim = non_numeric[0]
            measure = numeric[0] if numeric else None

            if measure is None:
                agg = df.groupby(dim).size().reset_index(name="count")
                measure = "count"
            else:
                agg = df.groupby(dim)[measure].sum().reset_index()

            if chart_type == "line":
                agg = agg.sort_values(dim)
            else:
                agg = agg.sort_values(measure, ascending=False)

            limit = _MAX_PIE_SLICES if chart_type in ("pie", "donut") else _MAX_CATEGORIES
            agg = agg.head(limit)
            if agg.empty:
                continue

            charts.append({
                "type": chart_type, "title": title, "x": dim, "y": measure,
                "points": [{"label": str(a), "value": float(b)}
                           for a, b in zip(agg[dim], agg[measure])],
            })

        except Exception as exc:  # a bad recommendation must not break the tab
            logger.debug("analytics: skipped chart '%s' — %s", title, exc)
            continue

    return charts


@router.get(
    "/sessions/{session_id}/charts",
    summary="Aggregated, plot-ready chart data",
    tags=["Analytics"],
)
async def charts(session_id: str, user: dict = Depends(require_user)) -> dict:
    session = _get_session(session_id, user)
    if not session["state"]:
        raise HTTPException(409, "Run an analysis first")

    recommendations = session["state"].get("visualization_recommendations") or []
    data = await asyncio.to_thread(
        _build_charts, session["file_path"], recommendations
    )
    return {"charts": data}


# ─────────────────────────────────────────────────────────────────────────────
# Chat
# ─────────────────────────────────────────────────────────────────────────────

class ChatBody(BaseModel):
    query: str


@router.post(
    "/sessions/{session_id}/chat",
    summary="Ask a follow-up question about the dataset",
    tags=["Analytics"],
)
async def chat(
    session_id: str, body: ChatBody, user: dict = Depends(require_user)
) -> dict:
    session = _get_session(session_id, user)
    if not session["state"]:
        raise HTTPException(409, "Run an analysis before asking questions")
    if not body.query.strip():
        raise HTTPException(400, "Query cannot be empty")

    def _follow_up() -> dict:
        from src.analytics.graph.workflow import get_analytics_graph

        updated = {
            **session["state"],
            "follow_up_query": body.query,
            "is_follow_up": True,
        }
        return get_analytics_graph().invoke(updated)

    final = await asyncio.to_thread(_follow_up)
    session["state"] = final

    history = final.get("chat_history") or []
    answer = ""
    for message in reversed(history):
        role = message.get("role") if isinstance(message, dict) else message.role
        if role == "assistant":
            answer = (
                message.get("content") if isinstance(message, dict) else message.content
            )
            break

    # Persist the exchange alongside the analysis.
    await asyncio.to_thread(
        _save_chat, session_id, session["user_id"], body.query, answer,
        session.get("analysis_id"),
    )

    return {"answer": answer, "chat_history": _chat_payload(history)}


def _chat_payload(history: list[Any]) -> list[dict]:
    out = []
    for message in history:
        if isinstance(message, dict):
            out.append(message)
        else:
            out.append(message.model_dump(mode="json"))
    return out


def _save_chat(
    session_id: str, user_id: str, query: str, answer: str, analysis_id: Optional[str]
) -> None:
    from src.analytics.database import AnalyticsRepository
    from src.analytics.schemas.chat import ChatMessage
    from src.shared.db import sync_session

    try:
        with sync_session() as db:
            repo = AnalyticsRepository(db)
            repo.get_or_create_session(session_id, user_id=user_id)
            repo.save_message(
                session_id, ChatMessage(role="user", content=query), analysis_id
            )
            repo.save_message(
                session_id, ChatMessage(role="assistant", content=answer), analysis_id
            )
    except Exception as exc:
        logger.warning("analytics: could not persist chat message — %s", exc)


@router.get(
    "/sessions/{session_id}/chat", summary="Chat history", tags=["Analytics"]
)
async def chat_history(session_id: str, user: dict = Depends(require_user)) -> dict:
    _get_session(session_id, user)

    def _load() -> list[dict]:
        from src.analytics.database import AnalyticsRepository
        from src.shared.db import sync_session

        with sync_session() as db:
            return [
                m.model_dump(mode="json")
                for m in AnalyticsRepository(db).get_chat_history(session_id)
            ]

    return {"messages": await asyncio.to_thread(_load)}


# ─────────────────────────────────────────────────────────────────────────────
# Past analyses
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analyses", summary="List the caller's analyses", tags=["Analytics"])
async def list_analyses(user: dict = Depends(require_user)) -> list[dict]:
    def _load() -> list[dict]:
        from src.analytics.database import AnalyticsRepository
        from src.shared.db import sync_session

        with sync_session() as db:
            repo = AnalyticsRepository(db)
            out = []
            for session in repo.get_user_sessions(user["user_id"]):
                for analysis in repo.get_session_analyses(session.id):
                    out.append(
                        {
                            "analysis_id": analysis.id,
                            "session_id": analysis.session_id,
                            "file_name": analysis.file_name,
                            "file_size_bytes": analysis.file_size_bytes,
                            "business_domain": analysis.business_domain,
                            "domain_confidence": analysis.domain_confidence,
                            "created_at": analysis.created_at.isoformat()
                            if analysis.created_at
                            else None,
                        }
                    )
            return out

    return await asyncio.to_thread(_load)


@router.get(
    "/analyses/{analysis_id}", summary="Get a past analysis", tags=["Analytics"]
)
async def get_analysis(analysis_id: str, user: dict = Depends(require_user)) -> dict:
    def _load() -> dict | None:
        from src.analytics.database import AnalyticsRepository
        from src.shared.db import sync_session

        with sync_session() as db:
            repo = AnalyticsRepository(db)
            if not repo.owns_analysis(analysis_id, user["user_id"]):
                return None
            analysis = repo.get_analysis(analysis_id)
            if analysis is None:
                return None
            return {
                "analysis_id": analysis.id,
                "session_id": analysis.session_id,
                "file_name": analysis.file_name,
                "file_size_bytes": analysis.file_size_bytes,
                "business_domain": analysis.business_domain,
                "domain_confidence": analysis.domain_confidence,
                "domain_reasoning": analysis.domain_reasoning,
                "dataset_summary": analysis.dataset_summary,
                "profiling_result": analysis.profiling_result,
                "executive_report": analysis.executive_report,
                "visualizations": analysis.visualizations or [],
                "kpis": [k.model_dump(mode="json") for k in repo.get_kpis(analysis_id)],
                "insights": [
                    i.model_dump(mode="json") for i in repo.get_insights(analysis_id)
                ],
                "created_at": analysis.created_at.isoformat()
                if analysis.created_at
                else None,
            }

    payload = await asyncio.to_thread(_load)
    if payload is None:
        raise HTTPException(404, "Analysis not found")
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# CRM integration — analyse the CRM's own tables
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/crm-tables", summary="CRM tables available for analysis", tags=["Analytics"]
)
async def crm_tables(user: dict = Depends(require_user)) -> list[dict]:
    from src.shared.crm_reader import CRM_TABLE_INFO, CRM_TABLE_NAMES

    return [
        {"name": name, "description": CRM_TABLE_INFO.get(name, "")}
        for name in CRM_TABLE_NAMES
    ]


class CrmTableBody(BaseModel):
    table: str


@router.post(
    "/sessions/{session_id}/load-crm-table",
    summary="Analyse a CRM table instead of an uploaded file",
    tags=["Analytics"],
)
async def load_crm_table(
    session_id: str, body: CrmTableBody, user: dict = Depends(require_user)
) -> dict:
    session = _get_session(session_id, user)

    from src.shared.crm_reader import CRM_TABLE_NAMES, load_crm_table as _load_table

    if body.table not in CRM_TABLE_NAMES:
        raise HTTPException(
            400, f"Unknown table '{body.table}'. Expected one of {CRM_TABLE_NAMES}."
        )

    def _dump() -> tuple[str, int]:
        df = _load_table(body.table, limit=settings.ANALYTICS_ROW_SAMPLE)
        dest_dir = UPLOAD_DIR / session_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"crm_{body.table}.csv"
        df.to_csv(dest, index=False)
        return str(dest), dest.stat().st_size

    try:
        path, size = await asyncio.to_thread(_dump)
    except Exception as exc:
        raise HTTPException(502, f"Could not read CRM table '{body.table}': {exc}")

    session.update(
        file_name=f"crm_{body.table}.csv",
        file_path=path,
        file_size_bytes=size,
        status="idle",
        state=None,
        analysis_id=None,
    )
    return {"file_name": session["file_name"], "file_size_bytes": size}
