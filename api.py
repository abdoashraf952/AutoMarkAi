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
        from streamlit_graph import get_streamlit_graph
        _graph = get_streamlit_graph()
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
        "image_path": None,
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

class AnswersBody(BaseModel):
    answers: dict[str, str]  # {"0": "...", "1": "...", "2": "...", "3": "..."}


class ImageDecisionBody(BaseModel):
    action: str               # "approve" | "regenerate"
    approved: list[bool] = []
    feedback: dict = {}       # {0: "what to change"}


class PickImageBody(BaseModel):
    chosen_index: int         # 0-based index from image_history


class TextDecisionBody(BaseModel):
    action: str               # "approve" | "edit"
    feedback: str = ""        # required when action == "edit"


class PublishBody(BaseModel):
    make_sponsored_ad: bool = True
    make_organic_post: bool = True


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


@app.post("/session/{session_id}/start", summary="Upload image and start the pipeline", tags=["Session"])
async def start_session(
    session_id: str,
    goal: str = Form(..., description="Campaign goal, e.g. 'get WhatsApp leads for luxury watch'"),
    budget: float = Form(..., description="Total campaign budget in USD"),
    image_mode: str = Form("use_original", description="'use_original' or 'enhance_with_ai'"),
    marketing_type: str = Form("product", description="'product', 'business', or 'service'"),
    language: str = Form("en", description="'en' for English, 'ar' for Egyptian Arabic"),
    image: UploadFile = File(..., description="Product photo (jpg/png/webp)"),
):
    """
    Uploads the product image and starts the LangGraph pipeline.
    Blocks until the graph produces its first interrupt (question_generator_node).

    Returns: current stage ('questions') + the generated questions.
    """
    session = _get_session(session_id)
    suffix = Path(image.filename or "image").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await image.read())
        session["image_path"] = tmp.name

    await _advance(session, {
        "image_path": session["image_path"],
        "image_mode": image_mode,
        "marketing_type": marketing_type,
        "language": language,
        "budget": float(budget),
        "goal": goal,
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


@app.post("/session/{session_id}/answers", summary="Submit answers to product questions", tags=["Human-in-the-loop"])
async def submit_answers(session_id: str, body: AnswersBody):
    """
    Resume the graph after the 'questions' interrupt.
    Triggers orchestrator → creative + media buying fan-out → image generation → image review interrupt.

    Body: {"answers": {"0": "...", "1": "...", "2": "...", "3": "..."}}
    Returns: stage ('image_review') + image data reference.
    """
    from langgraph.types import Command
    session = _get_session(session_id)
    _assert_stage(session, "questions")
    await _advance(session, Command(resume={"answers": body.answers}))
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.post("/session/{session_id}/image-decision", summary="Approve or regenerate the ad image", tags=["Human-in-the-loop"])
async def image_decision(session_id: str, body: ImageDecisionBody):
    """
    Resume the graph after the 'image_review' interrupt.

    To approve:     {"action": "approve"}
    To regenerate:  {"action": "regenerate", "feedback": {"0": "make it darker"}}

    If can_regenerate is false (use_original mode), the image is always approved.
    Returns: next stage ('text_review' on approval, 'image_review' again on regenerate,
             or 'max_regenerations_exceeded' if limit hit).
    """
    from langgraph.types import Command
    session = _get_session(session_id)
    _assert_stage(session, "image_review")

    data = session["interrupt_data"]
    n = len(data.get("images", [])) or 1
    can_regen = data.get("can_regenerate", True)

    if body.action == "approve" or not can_regen:
        payload = {"approved": [True] * n, "feedback": {}}
    else:
        payload = {
            "approved": body.approved or [False] * n,
            "feedback": body.feedback or {"0": "regenerate"},
        }
    await _advance(session, Command(resume=payload))
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.post("/session/{session_id}/pick-image", summary="Pick from previously generated images", tags=["Human-in-the-loop"])
async def pick_image(session_id: str, body: PickImageBody):
    """
    Resume after 'max_regenerations_exceeded' by selecting a previously generated image.

    Body: {"chosen_index": 0}   (0-based index into image_history)
    Returns: stage ('text_review').
    """
    from langgraph.types import Command
    session = _get_session(session_id)
    _assert_stage(session, "max_regenerations_exceeded")
    await _advance(session, Command(resume={"chosen_index": body.chosen_index}))
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.post("/session/{session_id}/text-decision", summary="Approve or request changes to ad copy", tags=["Human-in-the-loop"])
async def text_decision(session_id: str, body: TextDecisionBody):
    """
    Resume the graph after the 'text_review' interrupt.

    To approve:       {"action": "approve"}
    To request edit:  {"action": "edit", "feedback": "Make tone more urgent"}

    Returns: stage ('done' on approve, 'image_review' on edit — copy is regenerated).
    """
    from langgraph.types import Command
    session = _get_session(session_id)
    _assert_stage(session, "text_review")
    await _advance(session, Command(resume={
        "approved": body.action == "approve",
        "feedback": body.feedback,
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

    from meta_client import get_meta_client
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
