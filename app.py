"""AutoMark AI — Streamlit front-end with human-in-the-loop reviews."""

import base64
import json
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


# ------------------------------------------------------------------ #
# Graph + config helpers                                               #
# ------------------------------------------------------------------ #

@st.cache_resource
def _get_graph():
    """Cache the compiled graph (and its MemorySaver) for the lifetime of the process."""
    from streamlit_graph import get_streamlit_graph
    return get_streamlit_graph()


def _config() -> dict:
    return {"configurable": {"thread_id": st.session_state["thread_id"]}}


def _advance(input_) -> Optional[object]:
    """
    Stream the graph from input_ until it interrupts or completes.

    Args:
        input_: Initial state dict, or langgraph.types.Command(resume=...).

    Returns:
        The Interrupt object if the graph paused, or None if it completed.
    """
    graph = _get_graph()
    last_interrupt = None
    for chunk in graph.stream(input_, _config(), stream_mode="values"):
        if "__interrupt__" in chunk:
            interrupts = chunk["__interrupt__"]
            if interrupts:
                last_interrupt = interrupts[0]
    return last_interrupt


def _set_interrupt(interrupt_obj):
    """Store the interrupt payload and update ui_stage from it."""
    if interrupt_obj is None:
        st.session_state["ui_stage"] = "done"
        state_snap = _get_graph().get_state(_config())
        st.session_state["final_state"] = state_snap.values if state_snap else {}
    else:
        data = interrupt_obj.value if hasattr(interrupt_obj, "value") else interrupt_obj
        st.session_state["interrupt_data"] = data
        stage = data.get("stage", "questions")
        st.session_state["ui_stage"] = stage


# ------------------------------------------------------------------ #
# Session initialisation                                               #
# ------------------------------------------------------------------ #

def _init():
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "ui_stage": "setup",
        "interrupt_data": {},
        "image_path": None,
        "final_state": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ------------------------------------------------------------------ #
# Stage renderers                                                      #
# ------------------------------------------------------------------ #

def _stage_setup():
    st.header("Campaign Setup")

    uploaded = st.file_uploader(
        "Upload product image", type=["jpg", "jpeg", "png", "webp"]
    )
    budget = st.number_input("Budget (USD)", min_value=1.0, value=500.0, step=50.0)
    goal = st.text_input(
        "Campaign goal",
        placeholder="e.g. get WhatsApp leads for luxury watch",
    )

    if st.button("Generate Campaign", disabled=not (uploaded and goal)):
        suffix = Path(uploaded.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.read())
            image_path = tmp.name

        st.session_state["image_path"] = image_path

        initial_state = {
            "image_path": image_path,
            "budget": float(budget),
            "goal": goal,
            "errors": [],
            "llm_used": {},
        }

        with st.spinner("Analyzing product image and generating questions…"):
            interrupt_obj = _advance(initial_state)

        _set_interrupt(interrupt_obj)
        st.rerun()


def _stage_questions():
    st.header("Product Questions")
    st.write("Answer these questions so we can tailor your campaign:")

    questions: list[str] = st.session_state["interrupt_data"].get("questions", [])
    answers: dict[str, str] = {}

    for i, q in enumerate(questions):
        answers[str(i)] = st.text_input(f"**Q{i + 1}:** {q}", key=f"q_{i}")

    all_answered = all(v.strip() for v in answers.values())

    if st.button("Submit Answers", disabled=not all_answered):
        from langgraph.types import Command
        with st.spinner("Building campaign plan and generating ad content…"):
            interrupt_obj = _advance(Command(resume={"answers": answers}))

        _set_interrupt(interrupt_obj)
        st.rerun()


def _stage_image_review():
    st.header("Review Generated Images")
    st.write("Approve each image or provide feedback for regeneration.")

    images: list[str] = st.session_state["interrupt_data"].get("images", [])

    approved_list: list[bool] = []
    feedback_dict: dict = {}

    if not images:
        st.warning("No images were generated (image generation may have failed or quota exceeded).")
        if st.button("Skip to Text Review"):
            from langgraph.types import Command
            _set_interrupt(_advance(Command(resume={"approved": [], "feedback": {}})))
            st.rerun()
        return

    cols = st.columns(len(images))
    for idx, (col, b64_img) in enumerate(zip(cols, images)):
        with col:
            try:
                st.image(base64.b64decode(b64_img), caption=f"Image {idx + 1}", use_container_width=True)
            except Exception:
                st.error(f"Could not display image {idx + 1}")
            approved = st.checkbox(f"Approve Image {idx + 1}", key=f"img_ok_{idx}", value=True)
            approved_list.append(approved)
            if not approved:
                fb = st.text_area(
                    f"Feedback for Image {idx + 1}",
                    key=f"img_fb_{idx}",
                    height=80,
                    placeholder="Describe what to change…",
                )
                if fb.strip():
                    feedback_dict[idx] = fb.strip()

    if st.button("Submit Image Review"):
        from langgraph.types import Command
        with st.spinner("Processing image review…"):
            interrupt_obj = _advance(
                Command(resume={"approved": approved_list, "feedback": feedback_dict})
            )
        _set_interrupt(interrupt_obj)
        st.rerun()


def _stage_text_review():
    st.header("Review Ad Copy")

    data = st.session_state["interrupt_data"]

    st.subheader("Ad Copies")
    for i, copy in enumerate(data.get("copies", []), 1):
        st.write(f"{i}. {copy}")

    st.subheader("Headlines")
    for i, h in enumerate(data.get("headlines", []), 1):
        st.write(f"{i}. {h}")

    st.subheader("Call to Action")
    st.markdown(f"**{data.get('cta', '')}**")

    decision = st.radio("Your decision:", ["Approve", "Request Changes"], index=0, horizontal=True)
    feedback = ""
    if decision == "Request Changes":
        feedback = st.text_area(
            "Describe the changes needed:",
            placeholder="e.g. Make the tone more urgent and shorten the copies",
            height=100,
        )

    can_submit = decision == "Approve" or bool(feedback.strip())
    if st.button("Submit", disabled=not can_submit):
        from langgraph.types import Command
        with st.spinner("Processing…"):
            interrupt_obj = _advance(
                Command(resume={"approved": decision == "Approve", "feedback": feedback})
            )
        _set_interrupt(interrupt_obj)
        st.rerun()


def _stage_done():
    st.header("Campaign Bundle Ready")

    state = st.session_state.get("final_state") or {}
    bundle = state.get("campaign_bundle") or {}

    if not bundle:
        st.error("Pipeline completed but no bundle was found. Check the logs.")
        return

    product = bundle.get("product", {})
    campaign = bundle.get("campaign", {})
    creative = bundle.get("creative", {})
    media = bundle.get("media", {})

    # --- Summary metrics ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Product", product.get("type", "N/A"))
    col2.metric("Platform", campaign.get("platform", "N/A").title())
    col3.metric("Objective", campaign.get("objective", "N/A"))
    col4.metric("Daily Budget", f"${media.get('daily_budget_usd', 0):.2f}")

    st.divider()

    # --- Generated images ---
    gen_images: list[str] = creative.get("generated_images", [])
    if gen_images:
        st.subheader("Generated Ad Images")
        img_cols = st.columns(len(gen_images))
        for col, b64_img in zip(img_cols, gen_images):
            try:
                col.image(base64.b64decode(b64_img), use_container_width=True)
            except Exception:
                col.warning("Could not display image")

    # --- Creative copy ---
    st.subheader("Ad Copies")
    for i, c in enumerate(creative.get("copies", []), 1):
        st.write(f"{i}. {c}")

    st.subheader("Headlines")
    for i, h in enumerate(creative.get("headlines", []), 1):
        st.write(f"{i}. {h}")

    st.write(f"**CTA:** {creative.get('cta', '')}")

    # --- Audience & media ---
    with st.expander("Media Buying Details"):
        audience = media.get("audience", {})
        st.write(f"**Age range:** {audience.get('age_min', 'N/A')}–{audience.get('age_max', 'N/A')}")
        st.write(f"**Interests:** {', '.join(audience.get('interests', []))}")
        st.write(f"**Bid strategy:** {media.get('bid_strategy', 'N/A')}")
        st.write(f"**Estimated reach:** {media.get('estimated_reach', {})}")
        split = media.get("budget_split", {})
        if split:
            st.write("**Budget split:**")
            for platform, share in split.items():
                st.write(f"  - {platform.title()}: {share:.0%}")

    st.divider()

    # --- Download ---
    bundle_for_download = dict(bundle)
    creative_copy = dict(bundle_for_download.get("creative", {}))
    creative_copy.pop("generated_images", None)
    bundle_for_download["creative"] = creative_copy

    st.download_button(
        "Download Campaign Bundle (JSON)",
        data=json.dumps(bundle, indent=2),
        file_name="campaign_bundle.json",
        mime="application/json",
    )

    if st.button("Start New Campaign"):
        for key in ["thread_id", "ui_stage", "interrupt_data", "image_path", "final_state"]:
            st.session_state.pop(key, None)
        st.rerun()


# ------------------------------------------------------------------ #
# Progress sidebar                                                     #
# ------------------------------------------------------------------ #

_STAGES = ["setup", "questions", "image_review", "text_review", "done"]
_STAGE_LABELS = {
    "setup": "1. Setup",
    "questions": "2. Product Questions",
    "image_review": "3. Image Review",
    "text_review": "4. Copy Review",
    "done": "5. Complete",
}


def _sidebar():
    current = st.session_state.get("ui_stage", "setup")
    current_idx = _STAGES.index(current) if current in _STAGES else 0

    with st.sidebar:
        st.title("Progress")
        for i, stage in enumerate(_STAGES):
            if i < current_idx:
                icon = "✅"
            elif stage == current:
                icon = "▶"
            else:
                icon = "○"
            st.write(f"{icon} {_STAGE_LABELS[stage]}")

        if current != "setup":
            st.divider()
            if st.button("Restart"):
                for key in ["thread_id", "ui_stage", "interrupt_data", "image_path", "final_state"]:
                    st.session_state.pop(key, None)
                st.rerun()


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def main():
    st.set_page_config(
        page_title="AutoMark AI",
        page_icon="📣",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("AutoMark AI — Meta Ad Campaign Generator")

    _init()
    _sidebar()

    stage = st.session_state["ui_stage"]

    if stage == "setup":
        _stage_setup()
    elif stage == "questions":
        _stage_questions()
    elif stage == "image_review":
        _stage_image_review()
    elif stage == "text_review":
        _stage_text_review()
    elif stage == "done":
        _stage_done()
    else:
        st.error(f"Unknown stage: {stage!r}")


if __name__ == "__main__":
    main()
