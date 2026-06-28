"""AutoMark AI — FastAPI backend with SSE streaming and human-in-the-loop.

Phase 0 + 1: supervisor routing, approval modes.
Phase 2: compliance gate (runs inside the graph; /publish checks compliance_result).
Phase 3: research squad (runs inside the graph; no new endpoints).
Phase 4: /report, /operate, /approval endpoints + CampaignScheduler startup.
Phase 5: client memory injection at /start; /session/{id}/memory endpoint.
"""

import asyncio
import json
import logging
import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import sys
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


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
# Session store                                                        #
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
        # Phase 1: approval mode
        "approval_mode": None,
        "feature_flags": {},
        # Phase 4: operate state
        "operate_enabled": False,
        # Phase 5: client memory reference
        "client_memory_ref": None,
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
    if not data:
        return data
    safe = dict(data)
    if "images" in safe:
        safe["images"] = [f"<image_{i}>" for i in range(len(safe["images"]))]
    if "image_history" in safe:
        safe["image_history"] = [f"<image_{i}>" for i in range(len(safe["image_history"]))]
    return safe


# ------------------------------------------------------------------ #
# Scheduler (Phase 4)                                                  #
# ------------------------------------------------------------------ #

_scheduler = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _scheduler
    from AutoMarkAi.backend.workers.scheduler import CampaignScheduler
    _scheduler = CampaignScheduler(_sessions, _get_graph, demo_mode=True)
    await _scheduler.start()
    logger.info("Campaign scheduler started")
    yield
    await _scheduler.stop()
    logger.info("Campaign scheduler stopped")


# ------------------------------------------------------------------ #
# App                                                                  #
# ------------------------------------------------------------------ #

app = FastAPI(
    title="AutoMark AI",
    version="2.0.0",
    description="Real estate Meta ad campaign generator API — advanced multi-agent",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ #
# Graph runner                                                         #
# ------------------------------------------------------------------ #

def _advance_sync(session: dict, input_) -> None:
    from AutoMarkAi.backend.agent_logger import set_thread, log_session_end
    set_thread(session["thread_id"])

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
        # Phase 3 research progress events
        if chunk.get("audience_plan") and "audience_plan" not in seen:
            seen.add("audience_plan")
            push({"event": "progress", "stage": "research", "message": "Audience plan ready"})
        if chunk.get("competitor_findings") and "competitor_findings" not in seen:
            seen.add("competitor_findings")
            push({"event": "progress", "stage": "research", "message": "Competitor analysis done"})
        if chunk.get("demand_windows") and "demand_windows" not in seen:
            seen.add("demand_windows")
            push({"event": "progress", "stage": "research", "message": "Demand windows identified"})
        # Phase 5 memory progress
        if chunk.get("rolling_summary") and "rolling_summary" not in seen:
            seen.add("rolling_summary")
            push({"event": "progress", "stage": "memory", "message": "Session summary ready"})
        # Standard build events
        if chunk.get("campaign_plan") and "campaign_plan" not in seen:
            seen.add("campaign_plan")
            push({"event": "progress", "stage": "planning", "message": "Campaign plan ready"})
        if chunk.get("creative_output") and "creative_output" not in seen:
            seen.add("creative_output")
            push({"event": "progress", "stage": "creative", "message": "Creative content generated"})
        if chunk.get("media_output") and "media_output" not in seen:
            seen.add("media_output")
            push({"event": "progress", "stage": "media_buying", "message": "Media buying strategy ready"})
        # Phase 2 compliance event
        if chunk.get("compliance_result") and "compliance_result" not in seen:
            seen.add("compliance_result")
            cr = chunk["compliance_result"]
            push({
                "event": "progress",
                "stage": "compliance",
                "message": "HOUSING compliance: " + ("passed ✓" if cr.get("passed") else "violations found"),
            })
        if chunk.get("campaign_bundle") and "campaign_bundle" not in seen:
            seen.add("campaign_bundle")
            push({"event": "progress", "stage": "bundle_ready", "message": "Campaign bundle assembled"})

    if last_interrupt is None:
        session["ui_stage"] = "done"
        state_snap = graph.get_state(config)
        session["final_state"] = state_snap.values if state_snap else {}
        log_session_end(session["thread_id"], "done")
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
    answer: str


class PhotoSelectBody(BaseModel):
    selected_indices: list[int]


class TextDecisionBody(BaseModel):
    copy_index: int = 0
    headline_index: int = 0
    copy_text: str = ""
    headline_text: str = ""


class PublishBody(BaseModel):
    make_sponsored_ad: bool = True
    make_organic_post: bool = True


class ModeBody(BaseModel):
    approval_mode: str = "full_manual"
    feature_flags: dict = {}


class ApprovalBody(BaseModel):
    decision: str = "approved"   # "approved" | "rejected"
    feedback: str = ""


# ------------------------------------------------------------------ #
# Endpoints                                                            #
# ------------------------------------------------------------------ #

@app.post("/session", summary="Create a new campaign session", tags=["Session"])
async def create_session():
    sid = await _new_session()
    return {"session_id": sid}


_ASSET_TYPES = ("logo", "brochure", "floor_plans", "master_plan", "price_list")


@app.post("/session/{session_id}/upload-asset", summary="Upload a client asset", tags=["Session"])
async def upload_asset(
    session_id: str,
    asset_type: str = Form(...),
    file: UploadFile = File(...),
):
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
    budget: float = Form(...),
    language: str = Form("en"),
    approval_mode: str = Form("full_manual"),
    images: list[UploadFile] = File([]),
):
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

    _VALID_MODES = ("full_manual", "guided", "autopilot")
    if approval_mode not in _VALID_MODES:
        raise HTTPException(400, f"Invalid approval_mode '{approval_mode}'. Allowed: {_VALID_MODES}")
    effective_mode = session.get("approval_mode") or approval_mode
    session["approval_mode"] = effective_mode

    # Phase 5: inject client memory if already known
    client_ref = session.get("client_memory_ref") or ""
    client_memory_context = ""
    if client_ref:
        from AutoMarkAi.backend.memory.client_store import build_context_snippet, recall
        mem = recall(client_ref)
        client_memory_context = build_context_snippet(mem, language)

    from AutoMarkAi.backend.agent_logger import log_session_start
    log_session_start(
        thread_id=session_id,
        budget=float(budget),
        language=language,
        approval_mode=effective_mode,
        image_count=len(image_paths),
    )

    await _advance(session, {
        "image_paths": image_paths,
        "logo_path": session.get("logo_path") or "",
        "asset_paths": session.get("asset_paths") or {},
        "marketing_type": "real_estate",
        "language": language,
        "budget": float(budget),
        "goal": "",
        "approval_mode": effective_mode,
        "feature_flags": session.get("feature_flags") or {},
        "campaign_phase": "discovery",
        "client_memory_ref": client_ref,
        "rolling_summary": client_memory_context,
        "control_mode": "advantage_plus",  # default: Meta AI-first
        "errors": [],
        "llm_used": {},
    })
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.get("/session/{session_id}/stream", summary="SSE stream of pipeline events", tags=["Session"])
async def stream_events(session_id: str):
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
    s = _get_session(session_id)
    return {
        "session_id": session_id,
        "stage": s["ui_stage"],
        "data": _safe_data(s["interrupt_data"]),
    }


@app.post("/session/{session_id}/answer", summary="Answer campaign target or interview question", tags=["Human-in-the-loop"])
async def submit_answer(session_id: str, body: AnswerBody):
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
    from langgraph.types import Command
    session = _get_session(session_id)
    _assert_stage(session, "photo_select")
    await _advance(session, Command(resume={"selected_indices": body.selected_indices}))
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.post("/session/{session_id}/text-decision", summary="Choose & edit the ad copy + headline", tags=["Human-in-the-loop"])
async def text_decision(session_id: str, body: TextDecisionBody):
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


@app.post("/session/{session_id}/approval", summary="Resolve an Approval Gateway item", tags=["Human-in-the-loop"])
async def resolve_approval(session_id: str, body: ApprovalBody):
    """
    Resolve an approval-gate interrupt (stage == 'approval').

    Body: {"decision": "approved" | "rejected", "feedback": "optional text"}
    On rejection, feedback is passed back to the relevant agent for revision.
    """
    from langgraph.types import Command
    session = _get_session(session_id)
    if session["ui_stage"] != "approval":
        raise HTTPException(
            409,
            f"Stage is '{session['ui_stage']}', expected 'approval'",
        )
    await _advance(session, Command(resume={
        "decision": body.decision,
        "feedback": body.feedback,
    }))
    return {"stage": session["ui_stage"], "data": _safe_data(session["interrupt_data"])}


@app.post("/session/{session_id}/publish", summary="Publish campaign to Meta", tags=["Publish"])
async def publish(session_id: str, body: PublishBody = PublishBody()):
    session = _get_session(session_id)
    if session["ui_stage"] != "done":
        raise HTTPException(409, f"Stage is '{session['ui_stage']}', must be 'done' to publish")

    final = session.get("final_state") or {}
    bundle = final.get("campaign_bundle")
    if not bundle:
        raise HTTPException(400, "No campaign bundle found — pipeline may not have completed")

    # Phase 2: block publish if compliance gate failed
    compliance = final.get("compliance_result") or {}
    if compliance and not compliance.get("passed", True):
        violations = compliance.get("violations", [])
        raise HTTPException(
            422,
            f"Campaign failed HOUSING compliance check. Fix these violations before publishing: "
            + "; ".join(violations),
        )

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

    # Phase 4: after successful publish, enable operate loop
    if result and not errors:
        session["operate_enabled"] = True

        # Store campaign / ad-set IDs into the graph state so diagnose_node
        # and act_node can call the Meta Insights / Management APIs on resume.
        campaign_id = (result.get("campaign") or {}).get("id", "")
        adset_id = (result.get("ad_set") or {}).get("id", "")
        if campaign_id or adset_id:
            graph = _get_graph()
            cfg = _config(session["thread_id"])
            await asyncio.to_thread(
                graph.update_state,
                cfg,
                {
                    "meta_campaign_id": campaign_id,
                    "meta_adset_id": adset_id,
                    "campaign_phase": "operate",
                    "control_mode": "advantage_plus",
                },
            )

        # Persist session summary to long-term memory (Phase 5)
        client_ref = final.get("client_memory_ref") or ""
        if client_ref:
            re_data = final.get("real_estate_data") or {}
            from AutoMarkAi.backend.memory.client_store import merge as mem_merge
            await asyncio.to_thread(mem_merge, client_ref, {
                "compound_name": re_data.get("compound_name", ""),
                "location": re_data.get("location", ""),
                "price_tier": (final.get("campaign_plan") or {}).get("price_tier", {}).get("tier", ""),
                "outcome": "published",
                "performance_notes": "",
            })

    return {"success": bool(result), "simulation_mode": sim, "result": result, "errors": errors}


@app.get("/session/{session_id}/report", summary="Get latest campaign diagnosis and decisions", tags=["Operate"])
async def get_report(session_id: str):
    """
    Phase 4: Returns the latest diagnosis + decisions log in plain language.
    No jargon in the default view — CPL and rates are available but not foregrounded.
    """
    s = _get_session(session_id)
    final = (s.get("final_state") or {})
    diagnosis = final.get("latest_diagnosis") or {}
    decisions = final.get("decisions_log") or []
    snapshots = final.get("metric_snapshots") or []

    # Plain-language summary for the frontend
    return {
        "session_id": session_id,
        "operate_enabled": s.get("operate_enabled", False),
        "control_mode": final.get("control_mode", "advantage_plus"),
        "learning_state": final.get("learning_state", "learning"),
        "diagnosis": diagnosis,
        "decisions": decisions[-5:] if decisions else [],  # last 5 decisions
        "metric_count": len(snapshots),
        "compliance": final.get("compliance_result") or {},
    }


@app.post("/session/{session_id}/operate", summary="Trigger an immediate operate cycle", tags=["Operate"])
async def trigger_operate(session_id: str):
    """
    Phase 4: Manually trigger one operate cycle (diagnosis → decision → act).
    Useful for demo purposes — normally the scheduler fires this automatically.
    """
    session = _get_session(session_id)
    if not session.get("operate_enabled") and session["ui_stage"] != "done":
        raise HTTPException(
            409,
            "Campaign must be published (stage=done) before triggering operate cycle",
        )

    global _scheduler
    if _scheduler is None:
        raise HTTPException(503, "Scheduler not running")

    result = await _scheduler.trigger_session(session_id)
    return result


@app.get("/session/{session_id}/result", summary="Get final bundle and publish result", tags=["Publish"])
async def get_result(session_id: str):
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


@app.get("/session/{session_id}/memory", summary="Get client long-term memory for this session", tags=["Session"])
async def get_memory(session_id: str):
    """
    Phase 5: Return the stored long-term client memory for this session's client.
    """
    s = _get_session(session_id)
    client_ref = s.get("client_memory_ref") or (s.get("final_state") or {}).get("client_memory_ref") or ""
    if not client_ref:
        return {"session_id": session_id, "client_ref": None, "memory": {}}

    from AutoMarkAi.backend.memory.client_store import recall
    memory = await asyncio.to_thread(recall, client_ref)
    return {"session_id": session_id, "client_ref": client_ref, "memory": memory}


@app.post("/upload-image", summary="Pre-upload a product image", tags=["Utilities"])
async def upload_image(image: UploadFile = File(...)):
    suffix = Path(image.filename or "image").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await image.read())
        path = tmp.name
    file_id = str(uuid.uuid4())
    _uploaded_files[file_id] = path
    return {"file_id": file_id, "filename": image.filename, "path": path}


@app.get("/health", summary="Health check", tags=["Utilities"])
async def health():
    return {
        "status": "ok",
        "scheduler_running": _scheduler is not None,
    }
