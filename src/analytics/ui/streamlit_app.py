"""
AI-Powered Data Analytics Assistant — Streamlit UI
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Repo root on sys.path so the `src` package is importable however streamlit was
# launched (e.g. `streamlit run src/analytics/ui/streamlit_app.py`).
# src/analytics/ui/streamlit_app.py -> parents[3] is the repo root.
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="AutoMark Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Environment & imports ─────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

try:
    from src.shared.crm_reader import load_crm_table, CRM_TABLE_NAMES, CRM_TABLE_INFO
    CRM_INTEGRATION = True
except ImportError:
    CRM_INTEGRATION = False

from src.analytics.database import init_db
from src.analytics.graph.workflow import get_analytics_graph
from src.analytics.schemas.state import AnalyticsState
from src.analytics.schemas.dataset import DatasetSummary, ProfilingResult
from src.analytics.schemas.kpi import KPI
from src.analytics.schemas.insight import Insight
from src.analytics.schemas.chat import ChatMessage
from src.analytics.services.storage_service import StorageService
from src.analytics.memory.checkpoint import get_checkpoint_manager, InMemoryCheckpointManager
from src.analytics.agents.data_loader import get_cached_dataframe

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

# ── DB init ───────────────────────────────────────────────────────────────────
@st.cache_resource
def _init():
    try:
        init_db()
        return True
    except Exception as e:
        st.warning(f"Database unavailable (running without persistence): {e}")
        return False

DB_AVAILABLE = _init()

# ── Session state bootstrap ───────────────────────────────────────────────────
def _boot():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "analysis_running" not in st.session_state:
        st.session_state.analysis_running = False
    if "current_file_name" not in st.session_state:
        st.session_state.current_file_name = None

_boot()

storage = StorageService()


# ── Custom CSS — Dark Gold Theme (matching AutoMark brand) ────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700;800&display=swap');

  /* ── Base ── */
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: #2d2920; color: #f0e8d0; }
  .block-container { padding: 1.5rem 2rem 2rem; max-width: 1400px; }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: #252118;
    border-right: 1px solid #4a4232;
  }
  [data-testid="stSidebar"] .stMarkdown { color: #b0a080; }

  /* ── Brand header ── */
  .brand-header {
    display: flex; align-items: center; gap: 12px;
    padding: 0 0 1.5rem;
    border-bottom: 1px solid #4a4232;
    margin-bottom: 1.5rem;
  }
  .brand-icon-wrap {
    width: 44px; height: 44px; border-radius: 10px;
    background: linear-gradient(135deg, #c9a227, #8a6d10);
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
  }
  .brand-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem; font-weight: 700;
    color: #f5e6c0; letter-spacing: -0.3px;
  }
  .brand-sub { font-size: 0.7rem; color: #6b5f45; margin-top: 2px; letter-spacing: 0.3px; text-transform: uppercase; }

  /* ── Platform label (top-center style) ── */
  .platform-label {
    text-align: center; font-size: 0.7rem; font-weight: 600;
    letter-spacing: 0.15em; color: #8a7550; text-transform: uppercase;
    margin-bottom: 0.5rem;
  }

  /* ── Metric / stat cards ── */
  .metric-card {
    background: #3a3528;
    border: 1px solid #4a4232;
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.75rem;
    transition: border-color 0.2s;
  }
  .metric-card:hover { border-color: #c9a227; }
  .metric-value {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.1rem; font-weight: 700; color: #c9a227;
    line-height: 1;
  }
  .metric-label {
    font-size: 0.73rem; color: #6b5f45; margin-top: 5px;
    text-transform: uppercase; letter-spacing: 0.6px;
  }
  .metric-sub { font-size: 0.7rem; color: #c9a227; margin-top: 3px; opacity: 0.7; }

  /* ── Highlight stat card (right panel style) ── */
  .stat-card {
    background: #17140e; border: 1px solid #4a4232;
    border-radius: 14px; padding: 1rem 1.2rem; margin-bottom: 0.6rem;
  }
  .stat-card-label { font-size: 0.7rem; color: #6b5f45; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
  .stat-card-value { font-family: 'Space Grotesk', sans-serif; font-size: 2.4rem; font-weight: 700; color: #c9a227; line-height: 1; }
  .stat-card-sub { font-size: 0.72rem; color: #8a7550; margin-top: 4px; }
  .stat-bar { height: 4px; background: #4a4232; border-radius: 2px; margin-top: 10px; overflow: hidden; }
  .stat-bar-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #c9a227, #f0c040); }

  /* ── KPI cards ── */
  .kpi-card {
    background: #3a3528;
    border: 1px solid #4a4232;
    border-left: 3px solid;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
  }
  .kpi-critical { border-left-color: #e05252; }
  .kpi-high     { border-left-color: #c9a227; }
  .kpi-medium   { border-left-color: #8a7550; }
  .kpi-low      { border-left-color: #4a7a5a; }
  .kpi-name     { font-weight: 600; font-size: 0.95rem; color: #f5e6c0; }
  .kpi-category { font-size: 0.7rem; color: #6b5f45; text-transform: uppercase; letter-spacing: 0.5px; }
  .kpi-definition { font-size: 0.83rem; color: #9c8e72; margin: 6px 0; line-height: 1.5; }
  .kpi-value    { font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; font-weight: 600; color: #c9a227; }

  /* ── Insight cards ── */
  .insight-card {
    background: #17140e; border: 1px solid #4a4232;
    border-radius: 10px; padding: 1.2rem 1.4rem; margin-bottom: 0.75rem;
  }
  .insight-type-badge {
    display: inline-block; padding: 2px 9px; border-radius: 20px;
    font-size: 0.67rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 8px;
  }
  .type-trend       { background: #3d3820; color: #c9a227; border: 1px solid #5a5020; }
  .type-opportunity { background: #253028; color: #5da870; border: 1px solid #2a5030; }
  .type-risk        { background: #3a2020; color: #e05252; border: 1px solid #502828; }
  .type-performance { background: #362e20; color: #c9a227; border: 1px solid #3a2d10; }
  .type-anomaly     { background: #352c10; color: #e09030; border: 1px solid #504018; }
  .type-benchmark   { background: #223038; color: #50a8c0; border: 1px solid #254858; }
  .insight-summary  { font-size: 0.87rem; color: #c8b898; line-height: 1.55; margin-bottom: 8px; }
  .insight-recommendation {
    background: #2d2920; border-left: 2px solid #c9a227;
    padding: 8px 12px; border-radius: 0 6px 6px 0;
    font-size: 0.82rem; color: #d4a830;
  }

  /* ── Chat ── */
  .chat-user {
    background: #3a3528; border-radius: 12px 12px 4px 12px;
    padding: 10px 14px; margin: 8px 0 8px auto;
    max-width: 80%; font-size: 0.87rem; color: #e8dfc8;
    border: 1px solid #4a4232;
  }
  .chat-assistant {
    background: #17140e; border: 1px solid #4a4232;
    border-radius: 12px 12px 12px 4px;
    padding: 12px 16px; margin: 8px auto 8px 0;
    max-width: 90%; font-size: 0.87rem; color: #c8b898; line-height: 1.6;
  }
  .chat-role { font-size: 0.68rem; font-weight: 600; color: #6b5f45; margin-bottom: 4px; letter-spacing: 0.5px; text-transform: uppercase; }

  /* ── Step pills ── */
  .step-pill {
    display: inline-block; padding: 3px 10px;
    background: #3a3528; border-radius: 20px;
    font-size: 0.72rem; color: #6b5f45; margin: 2px;
    border: 1px solid #4a4232;
  }
  .step-pill.active { background: #2a2210; color: #c9a227; border-color: #c9a227; }
  .step-pill.done   { background: #253028; color: #5da870; border-color: #1a4025; }

  /* ── Feature chips (landing page) ── */
  .feature-chip {
    display: inline-flex; align-items: center; gap: 6px;
    background: #17140e; border: 1px solid #4a4232;
    border-radius: 24px; padding: 6px 14px;
    font-size: 0.78rem; color: #c8b898;
    margin: 4px;
  }

  /* ── CTA button (landing) ── */
  .cta-button {
    display: inline-block;
    background: linear-gradient(135deg, #c9a227 0%, #e8bf45 60%, #c9a227 100%);
    color: #352c10; font-weight: 700; font-size: 1rem;
    padding: 14px 36px; border-radius: 40px;
    text-align: center; cursor: pointer;
    box-shadow: 0 4px 24px rgba(201,162,39,0.35);
    letter-spacing: 0.01em;
    border: none; text-decoration: none;
  }

  /* ── Left dataset card (like the property card in screenshot) ── */
  .dataset-card {
    background: #17140e; border: 1px solid #4a4232;
    border-radius: 16px; padding: 1.2rem; overflow: hidden;
    position: relative;
  }
  .dataset-card-thumb {
    background: linear-gradient(135deg, #4a4232, #1a1610);
    border-radius: 10px; height: 80px;
    display: flex; align-items: center; justify-content: center;
    font-size: 2.5rem; margin-bottom: 10px;
  }
  .dataset-card-title { font-weight: 700; font-size: 0.92rem; color: #f5e6c0; margin-bottom: 2px; }
  .dataset-card-meta  { font-size: 0.72rem; color: #6b5f45; }
  .dataset-card-price { color: #c9a227; font-weight: 700; font-size: 0.9rem; margin: 6px 0; }
  .live-badge {
    display: inline-flex; align-items: center; gap: 5px;
    background: #253028; border: 1px solid #1a4025;
    color: #5da870; border-radius: 20px;
    padding: 3px 10px; font-size: 0.7rem; font-weight: 600;
    margin-top: 6px;
  }
  .live-dot { width: 6px; height: 6px; background: #5da870; border-radius: 50%; display: inline-block; }

  /* ── Upload zone ── */
  [data-testid="stFileUploader"] {
    border: 2px dashed #4a4232 !important;
    border-radius: 12px !important;
    background: #2d2920 !important;
  }
  [data-testid="stFileUploader"]:hover {
    border-color: #c9a227 !important;
  }

  /* ── Tabs ── */
  .stTabs [data-baseweb="tab-list"] { background: transparent; gap: 4px; }
  .stTabs [data-baseweb="tab"] {
    background: #17140e; border-radius: 8px;
    color: #6b5f45; font-size: 0.85rem; padding: 6px 16px;
    border: 1px solid #4a4232;
  }
  .stTabs [aria-selected="true"] {
    background: #2a2210 !important; color: #c9a227 !important;
    border-color: #c9a227 !important;
  }

  /* ── Priority badges ── */
  .priority-critical { color: #e05252; font-weight: 700; }
  .priority-high     { color: #c9a227; font-weight: 700; }
  .priority-medium   { color: #8a7550; font-weight: 600; }
  .priority-low      { color: #5da870; font-weight: 600; }

  /* ── Divider ── */
  hr { border-color: #4a4232; margin: 1.5rem 0; }

  /* ── Buttons ── */
  .stButton button {
    background: linear-gradient(135deg, #c9a227, #a88420);
    color: #352c10; border: none;
    border-radius: 8px; font-weight: 600;
    transition: all 0.2s;
  }
  .stButton button:hover {
    background: linear-gradient(135deg, #e0b830, #c9a227);
    box-shadow: 0 2px 12px rgba(201,162,39,0.4);
  }
  .stDownloadButton button {
    background: #253028; color: #5da870;
    border: 1px solid #1a4025; border-radius: 8px;
  }

  /* ── Dataframe ── */
  [data-testid="stDataFrame"] { border: 1px solid #4a4232; border-radius: 8px; }

  /* ── Progress bar ── */
  [data-testid="stProgressBar"] > div > div { background: #c9a227 !important; }

  /* ── Plotly chart background ── */
  .js-plotly-plot { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _priority_class(priority: str) -> str:
    return f"priority-{priority.lower()}"

def _type_class(t: str) -> str:
    return f"type-{t.lower()}"

def _kpi_border_class(priority: str) -> str:
    return f"kpi-{priority.lower()}"

def _parse_model(obj, cls):
    if isinstance(obj, dict):
        return cls(**obj)
    return obj


def _run_analysis(file_path: str, file_name: str, session_id: str) -> dict:
    """Run the full LangGraph pipeline and return final state dict."""
    initial_state = {
        "session_id": session_id,
        "file_name": file_name,
        "file_path": file_path,
        "file_size_bytes": Path(file_path).stat().st_size,
        "user_query": "Analyze this dataset",
        "is_follow_up": False,
        "chat_history": [],
        "kpis": [],
        "insights": [],
        "visualization_recommendations": [],
        "current_step": "start",
        "error_message": None,
    }
    graph = get_analytics_graph()
    return graph.invoke(initial_state)


def _run_follow_up(state_dict: dict, query: str) -> dict:
    """Run the chat branch of the graph."""
    updated = {**state_dict, "follow_up_query": query, "is_follow_up": True}
    graph = get_analytics_graph()
    return graph.invoke(updated)


def _save_to_db(result: dict, session_id: str):
    if not DB_AVAILABLE:
        return
    try:
        state = AnalyticsState(**result)
        analysis_id = storage.create_analysis(state)
        storage.update_analysis(analysis_id, state)
        if state.kpis:
            storage.save_kpis(analysis_id, state.kpis)
        if state.insights:
            storage.save_insights(analysis_id, state.insights)
        st.session_state.analysis_result["analysis_id"] = analysis_id
    except Exception as e:
        st.warning(f"Could not persist to database: {e}")


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div class="brand-header">
      <div class="brand-icon-wrap">📊</div>
      <div>
        <div class="brand-title">AutoMark Analytics</div>
        <div class="brand-sub">AI Business Intelligence</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Upload Dataset**")
    uploaded_file = st.file_uploader(
        "Drop CSV or Excel file",
        type=["csv", "xlsx", "xls"],
        label_visibility="collapsed",
    )

    if uploaded_file:
        if uploaded_file.name != st.session_state.current_file_name:
            st.session_state.current_file_name = uploaded_file.name
            st.session_state.analysis_result = None
            st.session_state.chat_history = []

        file_path = UPLOAD_DIR / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.markdown(f"""
        <div style="background:#3a3528;border:1px solid #4a4232;border-radius:8px;padding:10px 12px;margin:8px 0;">
          <div style="font-size:0.8rem;color:#c8b898;">📄 {uploaded_file.name}</div>
          <div style="font-size:0.72rem;color:#6b5f45;margin-top:2px;">{uploaded_file.size / 1024:.1f} KB</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚀 Run Analysis", use_container_width=True):
            st.session_state.analysis_running = True
            st.session_state.analysis_result = None
            st.session_state.chat_history = []
            st.rerun()

    st.markdown("---")

    # Session info
    st.markdown(f"""
    <div style="font-size:0.72rem;color:#7a6e55;">
      <div style="color:#6b5f45;">Session</div>
      <div style="color:#7a6e55;font-family:monospace;">{st.session_state.session_id[:16]}…</div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.analysis_result:
        res = st.session_state.analysis_result
        domain = res.get("business_domain", "")
        confidence = res.get("domain_confidence", 0)
        st.markdown("---")
        st.markdown(f"""
        <div style="font-size:0.78rem;color:#9c8e72;">
          <div style="margin-bottom:4px;"><b style="color:#f5e6c0;">Domain</b></div>
          <div style="color:#c9a227;font-weight:600;">{domain}</div>
          <div style="color:#6b5f45;font-size:0.7rem;">{confidence*100:.0f}% confidence</div>
        </div>
        """, unsafe_allow_html=True)

        # Report download
        report_md = res.get("executive_report")
        if report_md:
            st.markdown("---")
            st.download_button(
                "📄 Download Report (MD)",
                data=report_md,
                file_name=f"{res.get('file_name','report').replace('.','_')}_executive_report.md",
                mime="text/markdown",
                use_container_width=True,
            )

        # Reset button
        st.markdown("")
        if st.button("🔄 New Analysis", use_container_width=True):
            st.session_state.analysis_result = None
            st.session_state.chat_history = []
            st.session_state.current_file_name = None
            st.rerun()

    # ── CRM Data Integration ──────────────────────────────────────────────────
    if CRM_INTEGRATION and DB_AVAILABLE:
        st.markdown("---")
        with st.expander("🤝 Analyze CRM Data"):
            st.markdown(
                "<div style='font-size:0.78rem;color:#9ca3af;margin-bottom:8px;'>"
                "Load a table from the shared CRM database and run the full AI analysis pipeline on it."
                "</div>",
                unsafe_allow_html=True,
            )
            crm_table = st.selectbox("CRM Table", CRM_TABLE_NAMES, key="crm_tbl_select")
            st.caption(CRM_TABLE_INFO.get(crm_table, ""))
            if st.button("📥 Load & Analyze", use_container_width=True, key="btn_load_crm"):
                try:
                    with st.spinner(f"Loading {crm_table} from CRM database…"):
                        df = load_crm_table(crm_table)
                    if df.empty:
                        st.warning("This table has no data yet.")
                    else:
                        fname = f"crm_{crm_table}.csv"
                        fpath = UPLOAD_DIR / fname
                        df.to_csv(fpath, index=False)
                        st.session_state.current_file_name = fname
                        st.session_state.crm_file_path = str(fpath)
                        st.session_state.analysis_result = None
                        st.session_state.chat_history = []
                        st.session_state.analysis_running = True
                        st.rerun()
                except Exception as exc:
                    st.error(f"CRM load failed: {exc}")


# ── Run analysis pipeline ─────────────────────────────────────────────────────

_crm_file = st.session_state.pop("crm_file_path", None)
if st.session_state.analysis_running and (uploaded_file or _crm_file):
    if _crm_file:
        file_path = _crm_file
        _file_name = Path(_crm_file).name
    else:
        file_path = str(UPLOAD_DIR / uploaded_file.name)
        _file_name = uploaded_file.name
    steps = [
        ("📂", "Loading data"),
        ("🔬", "Profiling columns"),
        ("🏢", "Analysing business context"),
        ("📈", "Discovering KPIs"),
        ("💡", "Generating insights"),
        ("📊", "Recommending visuals"),
    ]

    status_container = st.empty()
    progress_bar = st.progress(0)

    with status_container.container():
        st.markdown("### Running AI Analysis Pipeline…")
        cols = st.columns(len(steps))
        placeholders = []
        for i, (icon, label) in enumerate(steps):
            with cols[i]:
                p = st.empty()
                p.markdown(f"<div class='step-pill'>{icon} {label}</div>", unsafe_allow_html=True)
                placeholders.append(p)

    # Animate steps
    for i in range(len(steps)):
        placeholders[i].markdown(
            f"<div class='step-pill active'>⏳ {steps[i][1]}</div>",
            unsafe_allow_html=True
        )
        progress_bar.progress((i + 1) / len(steps))

    try:
        result = _run_analysis(file_path, _file_name, st.session_state.session_id)
        st.session_state.analysis_result = result
        st.session_state.chat_history = result.get("chat_history", [])

        # Mark all done
        for i, (icon, label) in enumerate(steps):
            placeholders[i].markdown(
                f"<div class='step-pill done'>✅ {label}</div>",
                unsafe_allow_html=True
            )
        progress_bar.progress(1.0)

        if result.get("error_message"):
            st.error(f"Pipeline error: {result['error_message']}")
        else:
            _save_to_db(result, st.session_state.session_id)
            # Save checkpoint
            try:
                cp = get_checkpoint_manager(use_db=DB_AVAILABLE)
                cp.save(st.session_state.session_id, "latest_analysis", result)
            except Exception:
                pass
            st.success("Analysis complete!")

    except Exception as e:
        st.error(f"Analysis failed: {e}")
        import traceback; st.code(traceback.format_exc())

    st.session_state.analysis_running = False
    st.rerun()


# ── Main content area ─────────────────────────────────────────────────────────

if not st.session_state.analysis_result:
    # ── Hero landing page — AutoMark style ───────────────────────────────────
    left_col, center_col, right_col = st.columns([1, 2.2, 1])

    # ── LEFT — Sample dataset card ───────────────────────────────────────────
    with left_col:
        st.markdown("""
        <div style="padding-top:2.5rem;">
          <div class="dataset-card">
            <div class="dataset-card-thumb">📊</div>
            <div class="dataset-card-title">Sales Performance Q4</div>
            <div class="dataset-card-meta">12,400 rows · 18 columns · Finance</div>
            <div class="dataset-card-price">Quality Score: 94/100</div>
            <div class="live-badge">
              <span class="live-dot"></span> Analysis complete
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── CENTER — Hero text + CTA ──────────────────────────────────────────────
    with center_col:
        st.markdown("""
        <div style="text-align:center;padding:2rem 1rem 1.5rem;">

          <div class="platform-label">— AutoMark AI Analytics —</div>

          <div style="
            width:64px;height:64px;border-radius:16px;margin:0 auto 1.5rem;
            background:linear-gradient(135deg,#c9a227,#8a6d10);
            display:flex;align-items:center;justify-content:center;font-size:2rem;
          ">📊</div>

          <h1 style="
            font-family:'Space Grotesk',sans-serif;
            font-size:2.6rem;font-weight:800;
            color:#f5e6c0;line-height:1.15;
            margin-bottom:0.9rem;letter-spacing:-0.02em;
          ">
            Your data analysis,<br>
            <span style="color:#c9a227;">ready to launch</span><br>
            — in under 2 minutes.
          </h1>

          <p style="font-size:0.97rem;color:#8a7550;max-width:480px;margin:0 auto 1.8rem;line-height:1.75;">
            Upload your CSV or Excel file and AutoMark AI builds a complete executive
            intelligence report for you — KPIs, insights, charts, and recommendations.
            No analytics experience needed.
          </p>

          <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:4px;margin-bottom:1.8rem;">
            <span class="feature-chip">🏢 Built for business</span>
            <span class="feature-chip">📁 Any CSV or Excel file</span>
            <span class="feature-chip">💡 AI insights that convert</span>
            <span class="feature-chip">📊 Live chart previews</span>
          </div>

          <div style="
            display:inline-block;
            background:linear-gradient(135deg,#c9a227 0%,#e8bf45 60%,#c9a227 100%);
            color:#352c10;font-weight:700;font-size:1rem;
            padding:14px 36px;border-radius:40px;
            box-shadow:0 4px 24px rgba(201,162,39,0.35);
            letter-spacing:0.01em;margin-bottom:0.6rem;
          ">Upload your dataset in the sidebar →</div>

          <div style="font-size:0.72rem;color:#7a6e55;margin-top:6px;">
            Takes about 2 minutes · Nothing is shared · Runs entirely locally
          </div>

          <div style="display:flex;justify-content:center;gap:2rem;margin-top:1.8rem;
                      border-top:1px solid #4a4232;padding-top:1.2rem;">
            <div style="text-align:center;">
              <div style="font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:700;color:#c9a227;">Gemini AI</div>
              <div style="font-size:0.68rem;color:#6b5f45;text-transform:uppercase;letter-spacing:0.5px;">Powered by</div>
            </div>
            <div style="text-align:center;">
              <div style="font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:700;color:#c9a227;">2 min</div>
              <div style="font-size:0.68rem;color:#6b5f45;text-transform:uppercase;letter-spacing:0.5px;">Avg analysis time</div>
            </div>
            <div style="text-align:center;">
              <div style="font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:700;color:#c9a227;">Zero</div>
              <div style="font-size:0.68rem;color:#6b5f45;text-transform:uppercase;letter-spacing:0.5px;">Skills needed</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── RIGHT — Stat cards (like "Campaign Live" in screenshot) ──────────────
    with right_col:
        st.markdown("""
        <div style="padding-top:2.5rem;display:flex;flex-direction:column;gap:12px;">

          <div class="stat-card">
            <div class="stat-card-label">Analysis ready</div>
            <div style="font-size:0.88rem;font-weight:600;color:#f5e6c0;margin-bottom:4px;">Sales Q4 Report</div>
            <div class="stat-card-label" style="margin-top:4px;">KPIs discovered this run</div>
            <div class="stat-card-value">8</div>
            <div class="stat-bar"><div class="stat-bar-fill" style="width:78%"></div></div>
            <div class="stat-card-sub">78% of target depth</div>
          </div>

          <div class="stat-card">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
              <span style="font-size:1rem;">🏆</span>
              <span style="font-size:0.8rem;font-weight:600;color:#f5e6c0;">Top Insight</span>
            </div>
            <div class="stat-card-label">Cost efficiency achieved</div>
            <div style="font-family:'Space Grotesk',sans-serif;font-size:1.6rem;font-weight:700;color:#c9a227;">94/100</div>
            <div class="stat-card-sub">Quality score · last analysis</div>
          </div>

        </div>
        """, unsafe_allow_html=True)

    st.stop()


# ── Results layout ────────────────────────────────────────────────────────────

result = st.session_state.analysis_result

# Parse nested models — values may already be Pydantic instances or raw dicts
def _coerce(cls, val):
    if val is None:
        return None
    return val if isinstance(val, cls) else cls(**val)

dataset_summary: Optional[DatasetSummary] = _coerce(DatasetSummary, result.get("dataset_summary"))
profiling_result: Optional[ProfilingResult] = _coerce(ProfilingResult, result.get("profiling_result"))
kpis: list[KPI] = [KPI(**k) if isinstance(k, dict) else k for k in result.get("kpis", [])]
insights: list[Insight] = [Insight(**i) if isinstance(i, dict) else i for i in result.get("insights", [])]
viz_recs = result.get("visualization_recommendations", [])

# ── Page header ───────────────────────────────────────────────────────────────
domain = result.get("business_domain", "")
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;
            padding-bottom:1rem;border-bottom:1px solid #4a4232;">
  <div>
    <div class="platform-label" style="text-align:left;margin-bottom:4px;">— AutoMark Analytics —</div>
    <h2 style="font-family:'Space Grotesk',sans-serif;font-size:1.5rem;font-weight:700;
               color:#f5e6c0;margin:0 0 4px;">
      {result.get("file_name","Dataset")}
    </h2>
    <div style="font-size:0.82rem;color:#6b5f45;">
      <span style="color:#c9a227;font-weight:600;">{domain}</span>
      &nbsp;·&nbsp; {dataset_summary.row_count:,} rows &nbsp;·&nbsp;
      {dataset_summary.column_count} columns &nbsp;·&nbsp;
      {dataset_summary.memory_usage_mb} MB
    </div>
  </div>
  <div style="font-size:0.78rem;color:#7a6e55;">{datetime.now().strftime('%d %b %Y, %H:%M')}</div>
</div>
""", unsafe_allow_html=True)

# ── Summary metric strip ──────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
for col, value, label in [
    (m1, f"{dataset_summary.row_count:,}", "Total Records"),
    (m2, f"{dataset_summary.column_count}", "Columns"),
    (m3, f"{profiling_result.data_quality_score:.0f}/100" if profiling_result else "—", "Quality Score"),
    (m4, f"{len(kpis)}", "KPIs Identified"),
    (m5, f"{len(insights)}", "Insights"),
]:
    with col:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-value">{value}</div>
          <div class="metric-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ── Main tabs ─────────────────────────────────────────────────────────────────
tab_overview, tab_kpis, tab_insights, tab_viz, tab_report, tab_chat = st.tabs([
    "📋 Overview", "📈 KPIs", "💡 Insights", "📊 Visualizations", "📄 Report", "💬 Chat"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    if profiling_result:
        col_a, col_b = st.columns([3, 2])
        with col_a:
            st.markdown("#### Data Profiling Narrative")
            st.markdown(f"""
            <div style="background:#17140e;border:1px solid #4a4232;border-radius:10px;
                        padding:1.2rem 1.4rem;font-size:0.87rem;color:#c8b898;line-height:1.7;">
              {profiling_result.profiling_narrative.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)

            if profiling_result.quality_issues:
                st.markdown("#### ⚠️ Quality Issues")
                for issue in profiling_result.quality_issues:
                    st.markdown(f"""
                    <div style="background:#3a2020;border-left:3px solid #e05252;border-radius:0 6px 6px 0;
                                padding:8px 12px;margin:4px 0;font-size:0.83rem;color:#e09090;">
                      {issue}
                    </div>
                    """, unsafe_allow_html=True)

        with col_b:
            st.markdown("#### Column Type Breakdown")
            type_data = {
                "Numeric": len(profiling_result.numeric_columns),
                "Categorical": len(profiling_result.categorical_columns),
                "Datetime": len(profiling_result.datetime_columns),
                "Text": len(profiling_result.text_columns),
            }
            type_data = {k: v for k, v in type_data.items() if v > 0}
            if type_data:
                fig = go.Figure(go.Pie(
                    labels=list(type_data.keys()),
                    values=list(type_data.values()),
                    hole=0.55,
                    marker_colors=["#c9a227", "#5da870", "#e09030", "#8a7550"],
                ))
                fig.update_layout(
                    paper_bgcolor="#3a3528", plot_bgcolor="#3a3528",
                    font_color="#c8b898", showlegend=True, height=280,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(font=dict(color="#8a7550", size=12)),
                )
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Missing Data by Column")
            null_data = sorted(
                [(cp.name, cp.null_pct) for cp in profiling_result.column_profiles if cp.null_pct > 0],
                key=lambda x: -x[1]
            )
            if null_data:
                names, pcts = zip(*null_data[:15])
                fig2 = go.Figure(go.Bar(
                    x=list(pcts), y=list(names), orientation="h",
                    marker_color=["#e05252" if p > 50 else "#c9a227" if p > 20 else "#8a7550" for p in pcts],
                ))
                fig2.update_layout(
                    paper_bgcolor="#3a3528", plot_bgcolor="#3a3528",
                    font_color="#c8b898", height=max(200, len(null_data) * 22),
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis=dict(title="Missing %", color="#6b5f45"),
                    yaxis=dict(color="#8a7550"),
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.success("No missing data detected!")

        # Column detail table
        st.markdown("#### Column Statistics")
        if profiling_result.column_profiles:
            rows = []
            for cp in profiling_result.column_profiles:
                row = {
                    "Column": cp.name,
                    "Type": cp.inferred_type,
                    "Missing %": f"{cp.null_pct:.1f}%",
                    "Unique": cp.unique_count,
                    "Unique %": f"{cp.unique_pct:.1f}%",
                }
                if cp.inferred_type == "numeric":
                    row["Mean"] = f"{cp.mean:.2f}" if cp.mean is not None else "—"
                    row["Min"] = str(cp.min_val)
                    row["Max"] = str(cp.max_val)
                else:
                    row["Mean"] = "—"; row["Min"] = "—"; row["Max"] = "—"
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Raw data preview
    df = get_cached_dataframe(result.get("file_path", ""))
    if df is not None:
        st.markdown("#### Data Preview")
        st.dataframe(df.head(20), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: KPIs
# ══════════════════════════════════════════════════════════════════════════════
with tab_kpis:
    if not kpis:
        st.info("No KPIs generated. Run a full analysis first.")
    else:
        st.markdown(f"#### {len(kpis)} KPIs Identified for **{domain}**")

        # Priority filter
        priority_filter = st.multiselect(
            "Filter by Priority",
            options=["Critical", "High", "Medium", "Low"],
            default=["Critical", "High", "Medium", "Low"],
        )
        filtered_kpis = [k for k in kpis if k.priority in priority_filter]

        c1, c2 = st.columns(2)
        for i, kpi in enumerate(filtered_kpis):
            col = c1 if i % 2 == 0 else c2
            with col:
                st.markdown(f"""
                <div class="kpi-card {_kpi_border_class(kpi.priority)}">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                    <div class="kpi-name">{kpi.name}</div>
                    <div class="{_priority_class(kpi.priority)}" style="font-size:0.72rem;">{kpi.priority}</div>
                  </div>
                  <div class="kpi-category">{kpi.category}</div>
                  <div class="kpi-definition">{kpi.business_definition}</div>
                  {f'<div class="kpi-value">{kpi.current_value} {kpi.unit or ""}</div>' if kpi.current_value else ""}
                  {f'<div style="font-size:0.75rem;color:#7a6e55;margin-top:6px;font-style:italic;">Formula: {kpi.formula}</div>' if kpi.formula else ""}
                  <div style="font-size:0.78rem;color:#6b5f45;margin-top:8px;border-top:1px solid #4a4232;padding-top:8px;">
                    <b style="color:#8a7550;">Why it matters:</b> {kpi.why_important}
                  </div>
                  {f'<div style="font-size:0.72rem;color:#7a6e55;margin-top:4px;">Requires: {", ".join(kpi.required_columns)}</div>' if kpi.required_columns else ""}
                </div>
                """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_insights:
    if not insights:
        st.info("No insights generated yet.")
    else:
        st.markdown(f"#### {len(insights)} Executive Insights")

        type_filter = st.multiselect(
            "Filter by Type",
            options=["trend", "opportunity", "risk", "performance", "anomaly", "benchmark"],
            default=["trend", "opportunity", "risk", "performance", "anomaly", "benchmark"],
        )
        filtered_insights = [i for i in insights if i.type.lower() in [t.lower() for t in type_filter]]

        for insight in filtered_insights:
            with st.expander(f"{'🔴' if insight.priority == 'Critical' else '🟠' if insight.priority == 'High' else '🟡' if insight.priority == 'Medium' else '🟢'} {insight.title}", expanded=insight.priority in ["Critical", "High"]):
                st.markdown(f"""
                <div class="insight-card" style="margin:0;">
                  <span class="insight-type-badge {_type_class(insight.type)}">{insight.type}</span>
                  <span style="margin-left:8px;" class="{_priority_class(insight.priority)}">{insight.priority}</span>
                  <div class="insight-summary"><b>Summary:</b> {insight.executive_summary}</div>
                  <div style="font-size:0.85rem;color:#d1d5db;line-height:1.65;margin:10px 0;">{insight.detailed_analysis}</div>
                  {'<div style="margin:8px 0;"><b style="font-size:0.78rem;color:#8a7550;">Evidence:</b><ul style="margin:4px 0;padding-left:20px;">' + "".join(f"<li style='font-size:0.82rem;color:#8a7550;'>{e}</li>" for e in insight.evidence) + "</ul></div>" if insight.evidence else ""}
                  <div class="insight-recommendation"><b>→ Recommendation:</b> {insight.recommendation}</div>
                  {f'<div style="font-size:0.78rem;color:#6b5f45;margin-top:8px;"><b>Business Impact:</b> {insight.business_impact}</div>' if insight.business_impact else ""}
                  <div style="font-size:0.72rem;color:#7a6e55;margin-top:8px;">Confidence: {insight.confidence}</div>
                </div>
                """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: VISUALIZATIONS
# ══════════════════════════════════════════════════════════════════════════════
with tab_viz:
    if not viz_recs:
        st.info("No visualization recommendations generated.")
    else:
        st.markdown(f"#### {len(viz_recs)} Visualization Recommendations")
        st.markdown("*AI-recommended chart types and axes for your data*")

        df_viz = pd.DataFrame([{
            "Title": v.get("title", ""),
            "Chart Type": v.get("chart_type", ""),
            "X Axis": v.get("x_axis", ""),
            "Y Axis": v.get("y_axis", ""),
            "Aggregation": v.get("aggregation", ""),
            "Power BI Type": v.get("powerbi_visual_type", ""),
            "Purpose": v.get("business_purpose", ""),
        } for v in viz_recs])
        st.dataframe(df_viz, use_container_width=True, hide_index=True)

        # Live chart previews from actual data
        df = get_cached_dataframe(result.get("file_path", ""))
        if df is not None and profiling_result:
            st.markdown("#### Live Data Previews")
            num_cols = profiling_result.numeric_columns
            cat_cols = profiling_result.categorical_columns

            preview_cols = st.columns(2)
            charts_drawn = 0

            for rec in viz_recs[:6]:
                chart_type = rec.get("chart_type", "").lower()
                x = rec.get("x_axis") or (cat_cols[0] if cat_cols else None)
                y = rec.get("y_axis") or (num_cols[0] if num_cols else None)

                if not x or not y or x not in df.columns or y not in df.columns:
                    continue

                fig = None
                try:
                    if chart_type in ("bar", "clustered"):
                        agg = df.groupby(x)[y].sum().reset_index().sort_values(y, ascending=False).head(15)
                        fig = px.bar(agg, x=x, y=y, title=rec.get("title", ""),
                                     color_discrete_sequence=["#c9a227"])
                    elif chart_type == "line":
                        agg = df.groupby(x)[y].sum().reset_index()
                        fig = px.line(agg, x=x, y=y, title=rec.get("title", ""),
                                      color_discrete_sequence=["#e0b830"])
                    elif chart_type in ("pie", "donut"):
                        agg = df.groupby(x)[y].sum().reset_index().head(8)
                        fig = px.pie(agg, names=x, values=y, title=rec.get("title", ""),
                                     hole=0.4 if chart_type == "donut" else 0)
                    elif chart_type == "scatter" and len(num_cols) >= 2:
                        fig = px.scatter(df.sample(min(500, len(df))), x=num_cols[0], y=num_cols[1],
                                         title=rec.get("title", ""), opacity=0.6,
                                         color_discrete_sequence=["#5da870"])

                    if fig:
                        fig.update_layout(
                            paper_bgcolor="#3a3528", plot_bgcolor="#3a3528",
                            font_color="#c8b898", height=300,
                            margin=dict(l=10, r=10, t=40, b=10),
                        )
                        with preview_cols[charts_drawn % 2]:
                            st.plotly_chart(fig, use_container_width=True)
                            st.markdown(f"<div style='font-size:0.75rem;color:#6b5f45;text-align:center;'>{rec.get('business_purpose','')}</div>", unsafe_allow_html=True)
                        charts_drawn += 1
                except Exception:
                    continue


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: EXECUTIVE REPORT
# ══════════════════════════════════════════════════════════════════════════════
with tab_report:
    report_md = result.get("executive_report")
    if not report_md:
        st.info("Executive report not generated yet. It is produced automatically at the end of the analysis pipeline.")
    else:
        col_rh, col_rdl = st.columns([3, 1])
        with col_rh:
            st.markdown("#### Executive Analytics Report")
            st.markdown(f"*Full consolidated report from all {len(kpis)} KPIs and {len(insights)} insights.*")
        with col_rdl:
            st.download_button(
                "⬇️ Download Report (MD)",
                data=report_md,
                file_name=f"{result.get('file_name','report').replace('.','_')}_executive_report.md",
                mime="text/markdown",
                use_container_width=True,
            )

        st.markdown("---")
        st.markdown(report_md)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6: CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown("#### Ask Follow-Up Questions")
    st.markdown("<div style='font-size:0.82rem;color:#6b5f45;margin-bottom:1rem;'>Ask anything about your dataset, KPIs, and insights.</div>", unsafe_allow_html=True)

    # Suggested prompts
    suggestions = [
        "Show me only Critical insights",
        "Explain the top KPI in detail",
        "What are the biggest business risks?",
        "Generate recommendations for executives",
        "Which columns drive the most value?",
    ]
    sug_cols = st.columns(len(suggestions))
    for i, sug in enumerate(suggestions):
        with sug_cols[i]:
            if st.button(sug, key=f"sug_{i}", use_container_width=True):
                st.session_state["pending_chat"] = sug

    st.markdown("---")

    # Chat history display
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            role = msg.get("role", "") if isinstance(msg, dict) else msg.role
            content = msg.get("content", "") if isinstance(msg, dict) else msg.content
            if role == "user":
                st.markdown(f"""
                <div style="text-align:right;">
                  <div class="chat-role">You</div>
                  <div class="chat-user">{content}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div>
                  <div class="chat-role">Analytics AI</div>
                  <div class="chat-assistant">{content}</div>
                </div>
                """, unsafe_allow_html=True)

    # Input
    user_input = st.chat_input("Ask about your data, KPIs, or insights…")
    if "pending_chat" in st.session_state:
        user_input = st.session_state.pop("pending_chat")

    if user_input:
        with st.spinner("Thinking…"):
            try:
                updated = _run_follow_up(result, user_input)
                st.session_state.analysis_result = updated
                st.session_state.chat_history = updated.get("chat_history", [])

                # Persist
                if DB_AVAILABLE:
                    session_id = st.session_state.session_id
                    analysis_id = result.get("analysis_id")
                    user_msg = ChatMessage(role="user", content=user_input)
                    storage.save_message(session_id, user_msg, analysis_id)
                    new_msgs = updated.get("chat_history", [])
                    if new_msgs:
                        last = new_msgs[-1]
                        if isinstance(last, dict):
                            last = ChatMessage(**last)
                        if last.role == "assistant":
                            storage.save_message(session_id, last, analysis_id)

            except Exception as e:
                st.error(f"Chat error: {e}")
        st.rerun()
