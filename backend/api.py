"""AutoMark AI — FastAPI backend with SSE streaming and human-in-the-loop."""

import asyncio
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Make the backend importable regardless of how uvicorn is launched: both
# `uvicorn AutoMarkAi.backend.api:app` (from the project root) and
# `uvicorn api:app` (from this backend/ folder) work. The deferred
# `from AutoMarkAi.backend...` imports below resolve only when the project root
# (the parent of the AutoMarkAi/ repo) is on sys.path, so ensure it is.
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AutoMark AI", version="1.0.0", description="Meta ad campaign generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Next.js origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ #
# Graph singleton                                                      #
# ------------------------------------------------------------------ #

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from AutoMarkAi.backend.pipeline_graph import get_pipeline_graph
        _graph = get_pipeline_graph()
    return _graph


# ------------------------------------------------------------------ #
# Session store (in-memory; swap for Redis in production)             #
# ------------------------------------------------------------------ #

_sessions: dict[str, dict] = {}
_uploaded_files: dict[str, str] = {}


async def _new_session() -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = {
        "thread_id": sid,
        "ui_stage": "setup",
        "interrupt_data": {},
        "image_paths": [],
        "logo_path": None,
        "asset_paths": {},
        # Phase 1: approval mode + feature flags.
        # None here so /start's form param wins when /mode was never called.
        # /mode sets this explicitly; /start's effective_mode falls back to its form param.
        "approval_mode": None,
        "feature_flags": {},
        "final_state": None,
        "publish_result": None,
        "publish_error": None,
        "event_queue": asyncio.Queue(),
        "_seen": set(),
    }
    return sid


def _get_session(session_id: str) -> dict:
    s = _sessions.get(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return s


def _assert_stage(session: dict, expected: str) -> None:
    if session["ui_stage"] != expected:
        raise HTTPException(
            status_code=409,
            detail=f"Stage is '{session['ui_stage']}', expected '{expected}'",
        )


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _safe_data(data: dict) -> dict:
    """Strip heavy base64 blobs from interrupt_data for JSON responses."""
    if not data:
        return data
    safe = dict(data)
    if "images" in safe:
        safe["images"] = [f"<image_{i}>" for i in range(len(safe["images"]))]
    if "image_history" in safe:
        safe["image_history"] = [f"<image_{i}>" for i in range(len(safe["image_history"]))]
    return safe


# ------------------------------------------------------------------ #
# Graph runner                                                         #
# ------------------------------------------------------------------ #

def _advance_sync(session: dict, input_) -> None:
    """
    Run graph.stream() until the next interrupt or completion.
    Pushes SSE events into the session's asyncio.Queue via the main event loop.
    Must be called via asyncio.to_thread().
    """
    graph = _get_graph()
    config = _config(session["thread_id"])
    queue: asyncio.Queue = session["event_queue"]
    loop: asyncio.AbstractEventLoop = session["_loop"]

    def push(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    last_interrupt = None

    for chunk in graph.stream(input_, config, stream_mode="values"):
        if "__interrupt__" in chunk:
            interrupts = chunk["__interrupt__"]
            if interrupts:
                last_interrupt = interrupts[0]
            continue

        seen = session["_seen"]
        if chunk.get("questions") and "questions" not in seen:
            seen.add("questions")
            push({"event": "progress", "stage": "questions_ready", "message": "Product questions generated"})
        if chunk.get("campaign_plan") and "campaign_plan" not in seen:
            seen.add("campaign_plan")
            push({"event": "progress", "stage": "planning", "message": "Campaign plan ready"})
        if chunk.get("creative_output") and "creative_output" not in seen:
            seen.add("creative_output")
            push({"event": "progress", "stage": "creative", "message": "Creative content generated"})
        if chunk.get("media_output") and "media_output" not in seen:
            seen.add("media_output")
            push({"event": "progress", "stage": "media_buying", "message": "Media buying strategy ready"})
        if chunk.get("campaign_bundle") and "campaign_bundle" not in seen:
            seen.add("campaign_bundle")
            push({"event": "progress", "stage": "bundle_ready", "message": "Campaign bundle assembled"})

    if last_interrupt is None:
        session["ui_stage"] = "done"
        state_snap = graph.get_state(config)
        session["final_state"] = state_snap.values if state_snap else {}
        push({"event": "done", "stage": "done"})
    else:
        data = last_interrupt.value if hasattr(last_interrupt, "value") else last_interrupt
        session["interrupt_data"] = data
        stage = data.get("stage", "questions")
        session["ui_stage"] = stage
        push({"event": "interrupt", "stage": stage, "data": _safe_data(data)})


async def _advance(session: dict, input_) -> None:
    session["_loop"] = asyncio.get_event_loop()
    await asyncio.to_thread(_advance_sync, session, input_)


# ------------------------------------------------------------------ #
# Request / response schemas                                           #
# ------------------------------------------------------------------ #

class AnswerBody(BaseModel):
    answer: str  # the answer to the single question currently being asked


class PhotoSelectBody(BaseModel):
    selected_indices: list[int]  # which uploaded photos to use in the ad


class TextDecisionBody(BaseModel):
    copy_index: int = 0       # which of the generated copies the user chose
    headline_index: int = 0   # which of the generated headlines the user chose
    copy_text: str = ""        # final copy text (manually edited or same as chosen)
    headline_text: str = ""    # final headline text (manually edited or same as chosen)


class PublishBody(BaseModel):
    make_sponsored_ad: bool = True
    make_organic_post: bool = True


class ModeBody(BaseModel):
    approval_mode: str = "full_manual"   # "full_manual" | "guided" | "autopilot"
    feature_flags: dict = {}


# ------------------------------------------------------------------ #
# Endpoints                                                            #
# ------------------------------------------------------------------ #

@app.post("/session", summary="Create a new campaign session", tags=["Session"])
async def create_session():
    """
    Creates a new empty session and returns its ID.
    Pass session_id to all subsequent requests.
    """
    sid = await _new_session()
    return {"session_id": sid}


_ASSET_TYPES = ("logo", "brochure", "floor_plans", "master_plan", "price_list")


@app.post("/session/{session_id}/upload-asset", summary="Upload a client asset (logo/brochure/…)", tags=["Session"])
async def upload_asset(
    session_id: str,
    asset_type: str = Form(..., description="'logo', 'brochure', 'floor_plans', 'master_plan', or 'price_list'"),
    file: UploadFile = File(...),
):
    """
    Upload a real estate marketing asset before starting the pipeline (CHANGE 4).
    The logo is stored separately; everything else goes into asset_paths.
    `floor_plans` may be uploaded multiple times (accumulated into a list).
    """
    session = _get_session(session_id)
    if asset_type not in _ASSET_TYPES:
        raise HTTPException(400, f"Unknown asset_type '{asset_type}'. Allowed: {_ASSET_TYPES}")

    suffix = Path(file.filename or "asset").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        path = tmp.name

    if asset_type == "logo":
        session["logo_path"] = path
    elif asset_type == "floor_plans":
        session["asset_paths"].setdefault("floor_plans", []).append(path)
    else:
        session["asset_paths"][asset_type] = path

    return {"ok": True, "asset_type": asset_type, "filename": file.filename}


@app.post("/session/{session_id}/mode", summary="Set approval mode and feature flags", tags=["Session"])
async def set_mode(session_id: str, body: ModeBody):
    """
    Set the approval mode and feature flags for this session.

    Must be called before /start so the mode is applied from the first node.
    The mode can also be updated mid-session (takes effect at the next gate).

    approval_mode values:
      full_manual  — all gates interrupt the user (default; original behaviour)
      guided       — campaign-target auto-picked; photo & copy gates still interrupt
      autopilot    — entire build auto-approved; user only acts to publish
    """
    _VALID_MODES = ("full_manual", "guided", "autopilot")
    if body.approval_mode not in _VALID_MODES:
        raise HTTPException(400, f"Invalid approval_mode. Allowed: {_VALID_MODES}")
    session = _get_session(session_id)
    session["approval_mode"] = body.approval_mode
    session["feature_flags"] = body.feature_flags
    return {"ok": True, "approval_mode": body.approval_mode, "feature_flags": body.feature_flags}


@app.post("/session/{session_id}/start", summary="Start the pipeline with unit photos", tags=["Session"])
async def start_session(
    session_id: str,
    budget: float = Form(..., description="Total campaign budget in USD"),
    language: str = Form("en", description="'en' for English, 'ar' for Egyptian Arabic"),
    approval_mode: str = Form("full_manual", description="'full_manual' | 'guided' | 'autopilot'"),
    images: list[UploadFile] = File([], description="Unit photos (jpg/png/webp). At least one required."),
):
    """
    Starts the LangGraph real estate pipeline. The user uploads MULTIPLE unit
    photos (at least one — real estate ads must show the actual units). The
    marketing type is always 'real_estate'.

    The campaign goal is chosen by the user from the AI-ranked campaign-target
    options (the first interrupt, stage 'campaign_target').

    Blocks until the graph produces its first interrupt.
    Returns: current stage ('campaign_target') + the ranked options.
    """
    session = _get_session(session_id)

    image_paths: list[str] = []
    for img in images:
        if img.filename:
            suffix = Path(img.filename).suffix or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await img.read())
                image_paths.append(tmp.name)

    if not image_paths:
        raise HTTPException(400, "At least one unit photo is required.")

    session["image_paths"] = image_paths

    # /start can also set the approval_mode directly (convenience alternative to
    # calling /mode first).  The session-level value takes precedence if /mode
    # was already called; otherwise we use what was passed here.
    _VALID_MODES = ("full_manual", "guided", "autopilot")
    if approval_mode not in _VALID_MODES:
        raise HTTPException(400, f"Invalid approval_mode '{approval_mode}'. Allowed: {_VALID_MODES}")
    effective_mode = session.get("approval_mode") or approval_mode
    session["approval_mode"] = effective_mode

    await _advance(session, {
        "image_paths": image_paths,
        "logo_path": session.get("logo_path") or "",
        "asset_paths": session.get("asset_paths") or {},
        "marketing_type": "real_estate",  # hardcoded — no longer user-selectable
        "language": language,
        "budget": float(budget),
        "goal": "",
        "approval_mode": effective_mode,
        "feature_flags": session.get("feature_flags") or {},
        "campaign_phase": "discovery",
        "errors": [],
        "llm_used": {},
    })
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.get("/session/{session_id}/stream", summary="SSE stream of pipeline events", tags=["Session"])
async def stream_events(session_id: str):
    """
    Server-Sent Events endpoint. Connect with EventSource in Next.js to receive
    live progress events as the graph runs.

    Event types:
      - progress  → intermediate node completion
      - interrupt → graph paused waiting for human input
      - done      → pipeline complete
      - ping      → keepalive (every 25s of inactivity)
    """
    session = _get_session(session_id)
    queue: asyncio.Queue = session["event_queue"]

    async def generator() -> AsyncGenerator[str, None]:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("event") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield 'data: {"event": "ping"}\n\n'

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/session/{session_id}/state", summary="Get current stage and interrupt data", tags=["Session"])
async def get_state(session_id: str):
    """Returns the current stage and the latest interrupt payload (without base64 images)."""
    s = _get_session(session_id)
    return {
        "session_id": session_id,
        "stage": s["ui_stage"],
        "data": _safe_data(s["interrupt_data"]),
    }


@app.post("/session/{session_id}/answer", summary="Answer the campaign target or a product question", tags=["Human-in-the-loop"])
async def submit_answer(session_id: str, body: AnswerBody):
    """
    Resume the graph after a 'campaign_target' or 'questions' interrupt.

    - On 'campaign_target': send the chosen option's `goal` text as `answer`.
      It becomes the campaign goal and the adaptive interview begins.
    - On 'questions': send the answer to the CURRENT question. The interview is
      adaptive and dynamically sized — each answer is used to decide whether (and
      what) to ask next, bounded by MIN_QUESTIONS/MAX_QUESTIONS.

    Body: {"answer": "..."}
    Returns: next stage ('questions' with the next question, or a later stage when
             the interview is complete) + the interrupt data.
    """
    from langgraph.types import Command
    session = _get_session(session_id)
    if session["ui_stage"] not in ("questions", "campaign_target"):
        raise HTTPException(
            status_code=409,
            detail=f"Stage is '{session['ui_stage']}', expected 'questions' or 'campaign_target'",
        )
    await _advance(session, Command(resume={"answer": body.answer}))
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.post("/session/{session_id}/select-photos", summary="Pick which uploaded photos to use", tags=["Human-in-the-loop"])
async def select_photos(session_id: str, body: PhotoSelectBody):
    """
    Resume the graph after the 'photo_select' interrupt by choosing which of the
    uploaded unit photos to include in the ad (CHANGE 2).

    Body: {"selected_indices": [0, 2, 3]}
    Returns: next stage ('text_review').
    """
    from langgraph.types import Command
    session = _get_session(session_id)
    _assert_stage(session, "photo_select")
    await _advance(session, Command(resume={"selected_indices": body.selected_indices}))
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.post("/session/{session_id}/text-decision", summary="Choose & edit the ad copy + headline", tags=["Human-in-the-loop"])
async def text_decision(session_id: str, body: TextDecisionBody):
    """
    Resume the graph after the 'text_review' interrupt.

    The user picks ONE of the generated copies and ONE of the headlines, and may
    edit either text manually. The chosen (possibly edited) copy/headline become
    the primary creative used in the campaign.

    Body: {"copy_index": 0, "headline_index": 1,
           "copy_text": "final copy…", "headline_text": "final headline…"}
    Returns: stage ('done').
    """
    from langgraph.types import Command
    session = _get_session(session_id)
    _assert_stage(session, "text_review")
    await _advance(session, Command(resume={
        "copy_index": body.copy_index,
        "headline_index": body.headline_index,
        "copy_text": body.copy_text,
        "headline_text": body.headline_text,
    }))
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.post("/session/{session_id}/publish", summary="Publish campaign to Meta", tags=["Publish"])
async def publish(session_id: str, body: PublishBody = PublishBody()):
    """
    Triggers the Meta publish sequence (requires stage == 'done').
    Creates a PAUSED sponsored ad and/or an organic page post.

    In META_SIMULATION_MODE=true, both are always simulated regardless of body flags.
    Returns: {success, simulation_mode, result: {campaign, ad_set, creative, ad, post}, errors}
    """
    session = _get_session(session_id)
    if session["ui_stage"] != "done":
        raise HTTPException(409, f"Stage is '{session['ui_stage']}', must be 'done' to publish")

    bundle = (session.get("final_state") or {}).get("campaign_bundle")
    if not bundle:
        raise HTTPException(400, "No campaign bundle found — pipeline may not have completed")

    from AutoMarkAi.backend.meta_client import get_meta_client
    load_dotenv(override=True)
    client = get_meta_client()
    sim = os.getenv("META_SIMULATION_MODE", "true").lower() == "true"

    make_ad = True if sim else body.make_sponsored_ad
    make_post = True if sim else body.make_organic_post

    result: dict = {}
    errors: list[str] = []

    if make_ad:
        try:
            campaign = await asyncio.to_thread(client.create_campaign, bundle)
            ad_set = await asyncio.to_thread(client.create_ad_set, bundle, campaign["id"])
            creative = await asyncio.to_thread(client.create_ad_creative, bundle)
            ad = await asyncio.to_thread(client.create_ad, bundle, ad_set["id"], creative["id"])
            result.update(campaign=campaign, ad_set=ad_set, creative=creative, ad=ad)
        except Exception as e:
            errors.append(f"Ad creation failed: {e}")

    if make_post:
        try:
            post = await asyncio.to_thread(client.publish_post, bundle)
            result["post"] = post
        except Exception as e:
            errors.append(f"Organic post failed: {e}")

    session["publish_result"] = result or None
    session["publish_error"] = "\n\n".join(errors) if errors else None

    return {"success": bool(result), "simulation_mode": sim, "result": result, "errors": errors}


@app.get("/session/{session_id}/result", summary="Get final bundle and publish result", tags=["Publish"])
async def get_result(session_id: str):
    """
    Returns the complete campaign bundle (without base64 images) and publish result.
    Call after stage == 'done'.
    """
    s = _get_session(session_id)
    bundle = dict((s.get("final_state") or {}).get("campaign_bundle") or {})
    creative = dict(bundle.get("creative") or {})
    images = creative.pop("generated_images", [])
    creative["generated_images_count"] = len(images)
    bundle["creative"] = creative
    return {
        "session_id": session_id,
        "stage": s["ui_stage"],
        "bundle": bundle,
        "publish_result": s.get("publish_result"),
        "publish_error": s.get("publish_error"),
    }


@app.get("/session/{session_id}/images", summary="Get generated ad images as base64", tags=["Session"])
async def get_images(session_id: str):
    """
    Returns all generated images as base64-encoded strings.
    Checks interrupt_data first (during image_review), then falls back to the final bundle.
    Use the index values here when calling /pick-image.
    """
    s = _get_session(session_id)
    data = s.get("interrupt_data") or {}
    images = data.get("images") or data.get("image_history") or []
    if not images:
        bundle = (s.get("final_state") or {}).get("campaign_bundle") or {}
        images = bundle.get("creative", {}).get("generated_images", [])
    return {
        "count": len(images),
        "images": [{"index": i, "data": img} for i, img in enumerate(images)],
    }


@app.post("/upload-image", summary="Pre-upload a product image", tags=["Utilities"])
async def upload_image(image: UploadFile = File(...)):
    """
    Standalone image upload — useful for pre-uploading before creating a session.
    Returns a file_id you can reference later. The actual image is saved to a temp file.
    """
    suffix = Path(image.filename or "image").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await image.read())
        path = tmp.name
    file_id = str(uuid.uuid4())
    _uploaded_files[file_id] = path
    return {"file_id": file_id, "filename": image.filename, "path": path}


@app.get("/health", summary="Health check", tags=["Utilities"])
async def health():
    return {"status": "ok"}
