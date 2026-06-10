"""AutoMark AI — Streamlit front-end with human-in-the-loop reviews."""

import base64
import json
import os
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
        "meta_publish_result": None,
        "meta_publish_error": None,
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


def _render_ad_preview(bundle: dict):
    """Render a styled mock ad preview card for Facebook and Instagram."""
    creative = bundle.get("creative", {})
    product = bundle.get("product", {})
    campaign = bundle.get("campaign", {})

    page_name = f"AutoMark — {product.get('type', 'Brand')}"
    copies = creative.get("copies", [""])
    headlines = creative.get("headlines", [""])
    cta_label = creative.get("cta", "Learn More")
    copy_text = copies[0] if copies else ""
    headline_text = headlines[0] if headlines else ""

    # Resolve preview image: use uploaded file if available, else first generated image
    preview_img_html = ""
    image_path = st.session_state.get("image_path")
    gen_images = creative.get("generated_images", [])

    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            ext = Path(image_path).suffix.lstrip(".") or "jpeg"
            preview_img_html = (
                f'<img src="data:image/{ext};base64,{b64}" '
                f'style="width:100%;border-radius:4px;display:block;margin:10px 0;">'
            )
        except Exception:
            pass

    if not preview_img_html and gen_images:
        try:
            preview_img_html = (
                f'<img src="data:image/png;base64,{gen_images[0]}" '
                f'style="width:100%;border-radius:4px;display:block;margin:10px 0;">'
            )
        except Exception:
            pass

    if not preview_img_html:
        preview_img_html = (
            '<div style="width:100%;height:180px;background:#e4e6ea;border-radius:4px;'
            'display:flex;align-items:center;justify-content:center;'
            'color:#65676b;font-size:14px;margin:10px 0;">No image available</div>'
        )

    card_css = """
    <style>
    .ad-card {
        border:1px solid #dddfe2; border-radius:8px; padding:12px 16px;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        max-width:420px; background:#fff;
    }
    .ad-card .header { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
    .ad-card .avatar {
        width:40px; height:40px; border-radius:50%; background:#1877f2;
        display:flex; align-items:center; justify-content:center;
        color:#fff; font-weight:700; font-size:16px; flex-shrink:0;
    }
    .ad-card .page-name { font-weight:600; font-size:14px; color:#050505; }
    .ad-card .sponsored { font-size:12px; color:#65676b; }
    .ad-card .copy-text { font-size:14px; color:#050505; margin-bottom:4px; line-height:1.5; }
    .ad-card .ad-footer {
        background:#f0f2f5; border-top:1px solid #dddfe2; margin:8px -16px -12px;
        padding:10px 16px; border-radius:0 0 8px 8px;
        display:flex; justify-content:space-between; align-items:center;
    }
    .ad-card .headline { font-weight:600; font-size:14px; color:#050505; }
    .ad-card .cta-btn {
        background:#e7e9eb; border:1px solid #ccd0d5; border-radius:6px;
        padding:6px 12px; font-size:14px; font-weight:600; color:#050505;
        white-space:nowrap;
    }
    </style>
    """

    initial = (page_name[0] if page_name else "A").upper()
    card_html = f"""
    {card_css}
    <div class="ad-card">
      <div class="header">
        <div class="avatar">{initial}</div>
        <div>
          <div class="page-name">{page_name}</div>
          <div class="sponsored">Sponsored · <span style="color:#1877f2">&#9679;</span></div>
        </div>
      </div>
      <div class="copy-text">{copy_text[:200]}</div>
      {preview_img_html}
      <div class="ad-footer">
        <div>
          <div class="headline">{headline_text[:40]}</div>
        </div>
        <div class="cta-btn">{cta_label}</div>
      </div>
    </div>
    """

    # Instagram preview (slightly different styling)
    ig_card_html = f"""
    <div class="ad-card" style="border-radius:0;border:1px solid #dbdbdb;">
      <div class="header">
        <div class="avatar" style="background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);">{initial}</div>
        <div>
          <div class="page-name" style="font-size:13px;">{page_name}</div>
          <div class="sponsored" style="font-size:11px;">Sponsored</div>
        </div>
      </div>
      {preview_img_html}
      <div style="padding:8px 0;">
        <div style="font-size:13px;color:#262626;margin-bottom:4px;">
          <b>{page_name}</b> {copy_text[:150]}
        </div>
        <div style="font-size:12px;color:#8e8e8e;margin-bottom:8px;">{headline_text}</div>
        <div style="background:#e0e0e0;border-radius:4px;padding:8px;text-align:center;
             font-size:13px;font-weight:600;color:#262626;">{cta_label}</div>
      </div>
    </div>
    """

    st.subheader("Ad Preview")
    tab_fb, tab_ig = st.tabs(["Facebook", "Instagram"])
    with tab_fb:
        col, _ = st.columns([1, 1])
        with col:
            st.markdown(card_html, unsafe_allow_html=True)
    with tab_ig:
        col, _ = st.columns([1, 1])
        with col:
            st.markdown(ig_card_html, unsafe_allow_html=True)


def _do_publish(bundle: dict):
    """Run the full Meta publish sequence and store result in session_state."""
    from meta_client import get_meta_client

    client = get_meta_client()
    try:
        with st.spinner("Creating campaign on Meta…"):
            campaign = client.create_campaign(bundle)
        with st.spinner("Creating ad set…"):
            ad_set = client.create_ad_set(bundle, campaign["id"])
        with st.spinner("Creating ad creative…"):
            creative = client.create_ad_creative(bundle)
        with st.spinner("Creating ad…"):
            ad = client.create_ad(bundle, ad_set["id"], creative["id"])

        st.session_state["meta_publish_result"] = {
            "campaign": campaign,
            "ad_set": ad_set,
            "creative": creative,
            "ad": ad,
        }
        st.session_state["meta_publish_error"] = None
    except Exception as e:
        st.session_state["meta_publish_error"] = str(e)
        st.session_state["meta_publish_result"] = None


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

    # --- Ad Preview Card ---
    _render_ad_preview(bundle)

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

    st.divider()

    # --- Publish to Meta ---
    st.subheader("Publish to Meta")

    publish_result = st.session_state.get("meta_publish_result")
    publish_error = st.session_state.get("meta_publish_error")

    if publish_result:
        is_sim = os.getenv("META_SIMULATION_MODE", "true").lower() == "true"
        mode_tag = " *(simulated)*" if is_sim else ""
        st.success(f"Campaign published successfully{mode_tag}!")

        r = publish_result
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Campaign ID", r["campaign"]["id"])
            st.metric("Campaign Status", r["campaign"]["status"])
            st.metric("Ad Set ID", r["ad_set"]["id"])
        with col2:
            st.metric("Creative ID", r["creative"]["id"])
            st.metric("Ad ID", r["ad"]["id"])
            st.metric("Ad Status", r["ad"]["status"])

        with st.expander("Full publish response"):
            st.json(publish_result)

    elif publish_error:
        st.error(f"Publish failed: {publish_error}")
        if st.button("Retry Publish"):
            st.session_state["meta_publish_error"] = None
            _do_publish(bundle)
            st.rerun()
    else:
        if st.button("Publish Campaign to Meta", type="primary"):
            _do_publish(bundle)
            st.rerun()

    st.divider()

    if st.button("Start New Campaign"):
        for key in [
            "thread_id", "ui_stage", "interrupt_data", "image_path", "final_state",
            "meta_publish_result", "meta_publish_error",
        ]:
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

    # Simulation mode banner — visible on every page
    if os.getenv("META_SIMULATION_MODE", "true").lower() == "true":
        st.info(
            "🟡 **Running in demo mode** — connect Meta credentials in `.env` "
            "and set `META_SIMULATION_MODE=false` to go live.",
            icon="ℹ️",
        )

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
