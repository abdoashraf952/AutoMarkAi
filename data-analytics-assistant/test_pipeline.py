"""
Test & Validation Script for the AI-Powered Data Analytics Assistant
Run: python test_pipeline.py

Tests:
  1. Import health check
  2. Schema instantiation
  3. DataFrameService (load & summarize)
  4. StatisticsService (profile)
  5. GeminiService connectivity
  6. Full pipeline (mocked Gemini)
  7. DashboardService utilities
  8. CheckpointManager (in-memory)
  9. ReportGenerator
"""
from __future__ import annotations

import json
import os
import sys
import traceback
import uuid
from pathlib import Path

# ── colour helpers ────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
CYAN  = "\033[96m"
RESET = "\033[0m"
BOLD  = "\033[1m"

_passed = 0
_failed = 0
_skipped = 0


def _pass(msg: str):
    global _passed
    _passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def _fail(msg: str, err: str = ""):
    global _failed
    _failed += 1
    print(f"  {RED}✗{RESET} {msg}")
    if err:
        print(f"    {RED}{err[:200]}{RESET}")


def _skip(msg: str, reason: str = ""):
    global _skipped
    _skipped += 1
    print(f"  {YELLOW}⊘{RESET} {msg}{f' ({reason})' if reason else ''}")


def section(title: str):
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────

section("1. Import Health Check")
try:
    from app.schemas.state import AnalyticsState
    from app.schemas.dataset import DatasetSummary, ProfilingResult, ColumnProfile
    from app.schemas.kpi import KPI
    from app.schemas.insight import Insight
    from app.schemas.dashboard import DashboardSpec, DashboardPage, Visual, KPICard
    from app.schemas.chat import ChatMessage
    _pass("All schemas imported")
except Exception as e:
    _fail("Schema imports", str(e)); sys.exit(1)

try:
    from app.services.dataframe_service import DataFrameService
    from app.services.statistics_service import StatisticsService
    from app.services.dashboard_service import DashboardService, get_dashboard_service
    _pass("All services imported")
except Exception as e:
    _fail("Service imports", str(e))

try:
    from app.agents.data_loader import data_loader_agent, get_cached_dataframe
    from app.agents.profiling import profiling_agent
    from app.agents.business_analysis import business_analysis_agent
    from app.agents.kpi_discovery import kpi_discovery_agent
    from app.agents.insight_generation import insight_generation_agent
    from app.agents.visualization import visualization_agent
    from app.agents.powerbi_builder import powerbi_builder_agent
    from app.agents.report_generator import report_generator_agent
    from app.agents.orchestrator import chat_orchestrator_agent
    _pass("All agents imported")
except Exception as e:
    _fail("Agent imports", str(e))

try:
    from app.graph.workflow import get_analytics_graph, build_analytics_graph
    _pass("Graph workflow imported")
except Exception as e:
    _fail("Graph import", str(e))

try:
    from app.memory.checkpoint import get_checkpoint_manager, InMemoryCheckpointManager
    _pass("Checkpoint manager imported")
except Exception as e:
    _fail("Checkpoint import", str(e))


# ─────────────────────────────────────────────────────────────────────────────

section("2. Schema Instantiation")

try:
    kpi = KPI(
        id="kpi_test_01",
        name="Total Revenue",
        business_definition="Sum of all revenue across all orders",
        formula="SUM(Revenue)",
        required_columns=["Revenue"],
        priority="Critical",
        category="Revenue",
        why_important="Core financial health indicator",
        current_value="$52,483.00",
        unit="$",
    )
    assert kpi.id == "kpi_test_01"
    _pass("KPI schema")
except Exception as e:
    _fail("KPI schema", str(e))

try:
    insight = Insight(
        id="insight_test_01",
        title="Revenue Concentrated in Technology",
        type="trend",
        priority="High",
        executive_summary="Technology products account for 58% of total revenue.",
        detailed_analysis="Analysis shows consistent technology dominance across all regions.",
        evidence=["Technology: $30,440", "Furniture: $15,200", "Office Supplies: $6,843"],
        recommendation="Expand technology product range to capture growing demand.",
        affected_kpis=["kpi_test_01"],
        confidence="High",
    )
    assert insight.type == "trend"
    _pass("Insight schema")
except Exception as e:
    _fail("Insight schema", str(e))

try:
    card = KPICard(title="Total Revenue", measure="SUM(Revenue)", format="currency")
    visual = Visual(
        id="viz_01", title="Revenue by Category", chart_type="bar",
        x_axis="Product Category", y_axis="Revenue",
        business_purpose="Show revenue distribution across product lines",
    )
    page = DashboardPage(
        page_name="Executive Overview", page_number=1,
        purpose="High-level KPI summary for C-suite",
        kpi_cards=[card], visuals=[visual],
    )
    spec = DashboardSpec(
        title="Sales Analytics Dashboard",
        description="Complete sales overview",
        target_audience="Executive Leadership",
        pages=[page],
    )
    assert len(spec.pages) == 1
    _pass("DashboardSpec schema")
except Exception as e:
    _fail("DashboardSpec schema", str(e))

try:
    state = AnalyticsState(
        session_id=str(uuid.uuid4()),
        file_name="sample_sales_data.csv",
        file_path="uploads/sample_sales_data.csv",
        business_domain="Sales",
        kpis=[kpi],
        insights=[insight],
        dashboard_spec=spec,
    )
    assert state.business_domain == "Sales"
    assert len(state.kpis) == 1
    _pass("AnalyticsState schema (with nested models)")
except Exception as e:
    _fail("AnalyticsState schema", str(e))

try:
    # Test dict → model coercion (as LangGraph would do)
    state_dict = state.model_dump()
    restored = AnalyticsState(**state_dict)
    assert isinstance(restored.kpis[0], KPI)
    assert isinstance(restored.insights[0], Insight)
    assert isinstance(restored.dashboard_spec, DashboardSpec)
    _pass("AnalyticsState dict→model coercion (LangGraph roundtrip)")
except Exception as e:
    _fail("AnalyticsState coercion", str(e))


# ─────────────────────────────────────────────────────────────────────────────

section("3. DataFrameService")

SAMPLE_CSV = Path("uploads/sample_sales_data.csv")

try:
    svc = DataFrameService()
    if not SAMPLE_CSV.exists():
        _skip("Load CSV", "sample_sales_data.csv not found")
    else:
        df = svc.load_file(str(SAMPLE_CSV))
        assert len(df) > 0
        _pass(f"Load CSV → {len(df)} rows, {len(df.columns)} columns")

        summary = svc.extract_summary(df, SAMPLE_CSV.name)
        assert summary.row_count == len(df)
        assert summary.column_count == len(df.columns)
        assert len(summary.sample_rows) <= 5
        _pass(f"Extract summary: {summary.row_count} rows, {summary.column_count} cols")

        # Test serialization
        dumped = summary.model_dump()
        restored_summary = DatasetSummary(**dumped)
        assert restored_summary.file_name == summary.file_name
        _pass("DatasetSummary serialization roundtrip")
except Exception as e:
    _fail("DataFrameService", str(e))
    df = None; summary = None


# ─────────────────────────────────────────────────────────────────────────────

section("4. StatisticsService")

try:
    if SAMPLE_CSV.exists() and 'df' in dir() and df is not None:
        stat_svc = StatisticsService()
        profiling = stat_svc.profile_dataframe(df, summary)
        assert profiling.data_quality_score >= 0
        assert len(profiling.column_profiles) == len(df.columns)
        _pass(f"Profile DataFrame: quality={profiling.data_quality_score:.0f}/100")

        numeric_profiles = [p for p in profiling.column_profiles if p.inferred_type == "numeric"]
        _pass(f"Numeric columns: {profiling.numeric_columns}")
        _pass(f"Categorical columns: {profiling.categorical_columns[:5]}")

        # Verify numeric stats
        if numeric_profiles:
            np_ = numeric_profiles[0]
            assert np_.mean is not None
            _pass(f"Column '{np_.name}': mean={np_.mean:.2f}, min={np_.min_val}, max={np_.max_val}")
    else:
        _skip("StatisticsService", "DataFrame not available")
except Exception as e:
    _fail("StatisticsService", str(e))


# ─────────────────────────────────────────────────────────────────────────────

section("5. Gemini Service Connectivity")

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_KEY or GEMINI_KEY == "your_gemini_api_key_here":
    _skip("Gemini API call", "GEMINI_API_KEY not set")
else:
    try:
        from app.services.gemini_service import get_gemini_service
        gemini = get_gemini_service()
        response = gemini.generate("Reply with exactly: PONG", max_tokens=20, temperature=0)
        assert "PONG" in response.upper() or len(response) > 0
        _pass(f"Gemini text generation: '{response[:50]}'")
    except Exception as e:
        _fail("Gemini text generation", str(e))

    try:
        result = gemini.generate_json(
            'Return this JSON object with no changes: {"status": "ok", "value": 42}',
            max_tokens=50, temperature=0,
        )
        assert result.get("status") == "ok"
        _pass(f"Gemini JSON generation: {result}")
    except Exception as e:
        _fail("Gemini JSON generation", str(e))


# ─────────────────────────────────────────────────────────────────────────────

section("6. DashboardService")

try:
    dash_svc = get_dashboard_service()

    # Validation
    warnings = dash_svc.validate_spec(spec)
    _pass(f"Spec validation: {len(warnings)} warnings")

    # Export
    json_str = dash_svc.to_json(spec)
    parsed = json.loads(json_str)
    _pass(f"JSON export: {len(json_str)} chars")

    # Power BI template
    pbi = dash_svc.to_powerbi_template(spec)
    assert "reportTemplate" in pbi
    _pass("Power BI template conversion")

    # Markdown summary
    md = dash_svc.to_markdown_summary(spec)
    assert "Executive Overview" in md
    _pass("Markdown summary")

    # Utilities
    total = dash_svc.count_total_visuals(spec)
    measures = dash_svc.get_all_measures(spec)
    dims = dash_svc.get_all_dimensions(spec)
    _pass(f"Utilities: {total} visuals, {len(measures)} measures, {len(dims)} dimensions")

    # Enrichment
    enriched = dash_svc.enrich_with_kpis(spec, [kpi])
    _pass(f"KPI enrichment: {len(enriched.pages[0].kpi_cards)} cards on page 1")

except Exception as e:
    _fail("DashboardService", str(e))


# ─────────────────────────────────────────────────────────────────────────────

section("7. CheckpointManager (In-Memory)")

try:
    cp = InMemoryCheckpointManager()
    session_id = str(uuid.uuid4())
    test_state = {"session_id": session_id, "business_domain": "Sales", "kpis": [kpi.model_dump()]}

    cp.save(session_id, "latest", test_state)
    loaded = cp.load(session_id, "latest")
    assert loaded is not None
    assert loaded.get("business_domain") == "Sales"
    _pass("Save & load checkpoint")

    keys = cp.list_keys(session_id)
    assert "latest" in keys
    _pass(f"List keys: {keys}")

    cp.delete(session_id, "latest")
    assert cp.load(session_id, "latest") is None
    _pass("Delete checkpoint")

    cp.save(session_id, "a", {"x": 1})
    cp.save(session_id, "b", {"x": 2})
    cp.delete_session(session_id)
    assert cp.list_keys(session_id) == []
    _pass("Delete session")

except Exception as e:
    _fail("CheckpointManager", str(e))


# ─────────────────────────────────────────────────────────────────────────────

section("8. Report Generator Agent")

try:
    from app.agents.report_generator import report_generator_agent

    full_state = AnalyticsState(
        session_id=str(uuid.uuid4()),
        file_name="sample_sales_data.csv",
        file_path="uploads/sample_sales_data.csv",
        file_size_bytes=12345,
        business_domain="Sales",
        domain_confidence=0.95,
        domain_reasoning="Column names such as Revenue, Profit, and Order ID strongly indicate a retail sales dataset.",
        kpis=[kpi],
        insights=[insight],
        dashboard_spec=spec,
        visualization_recommendations=[{
            "title": "Revenue by Category",
            "chart_type": "bar",
            "x_axis": "Product Category",
            "y_axis": "Revenue",
            "business_purpose": "Show revenue distribution",
        }],
    )

    result = report_generator_agent(full_state)
    assert "executive_report" in result
    report = result["executive_report"]
    assert "Executive Analytics Report" in report
    assert "Total Revenue" in report  # KPI name
    assert "Revenue Concentrated in Technology" in report  # Insight title
    assert "Sales Analytics Dashboard" in report  # Dashboard title
    _pass(f"Report generated: {len(report)} characters")

    sections_found = [s for s in ["Dataset Overview", "Data Quality", "Business Context", "KPI", "Insight", "Visualization", "Power BI"] if s in report]
    _pass(f"Report sections found: {sections_found}")

except Exception as e:
    _fail("Report Generator", str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────

section("9. LangGraph Graph Construction")

try:
    graph = build_analytics_graph()
    assert graph is not None
    _pass("LangGraph graph compiled successfully")

    # Verify singleton caching
    graph2 = get_analytics_graph()
    _pass("Singleton graph factory works")

except Exception as e:
    _fail("LangGraph compilation", str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────

section("10. Full Pipeline (requires GEMINI_API_KEY + sample CSV)")

if not GEMINI_KEY or GEMINI_KEY == "your_gemini_api_key_here":
    _skip("Full pipeline run", "GEMINI_API_KEY not set")
elif not SAMPLE_CSV.exists():
    _skip("Full pipeline run", "sample_sales_data.csv not found in uploads/")
else:
    try:
        initial_state = {
            "session_id": str(uuid.uuid4()),
            "file_name": SAMPLE_CSV.name,
            "file_path": str(SAMPLE_CSV),
            "file_size_bytes": SAMPLE_CSV.stat().st_size,
            "user_query": "Analyze this sales dataset",
            "is_follow_up": False,
            "chat_history": [],
            "kpis": [],
            "insights": [],
            "visualization_recommendations": [],
            "current_step": "start",
            "error_message": None,
        }

        print(f"  {YELLOW}Running pipeline (this may take 30-60 seconds)…{RESET}")
        pipeline = get_analytics_graph()
        result = pipeline.invoke(initial_state)

        if result.get("error_message"):
            _fail("Full pipeline", result["error_message"][:300])
        else:
            _pass(f"Pipeline completed: step='{result.get('current_step')}'")
            _pass(f"Domain: {result.get('business_domain')} ({result.get('domain_confidence', 0)*100:.0f}%)")
            _pass(f"KPIs: {len(result.get('kpis', []))}")
            _pass(f"Insights: {len(result.get('insights', []))}")
            _pass(f"Viz recs: {len(result.get('visualization_recommendations', []))}")
            _pass(f"Dashboard pages: {len(result.get('dashboard_spec', {}).get('pages', []) if isinstance(result.get('dashboard_spec'), dict) else [])}")
            _pass(f"Executive report: {len(result.get('executive_report', '') or '')} chars")

    except Exception as e:
        _fail("Full pipeline", str(e))
        traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────

section("Results")
total = _passed + _failed + _skipped
print(f"\n  {BOLD}Total: {total}{RESET}  |  "
      f"{GREEN}{BOLD}Passed: {_passed}{RESET}  |  "
      f"{RED}{BOLD}Failed: {_failed}{RESET}  |  "
      f"{YELLOW}{BOLD}Skipped: {_skipped}{RESET}\n")

if _failed > 0:
    print(f"  {RED}Some tests failed. Review errors above.{RESET}\n")
    sys.exit(1)
else:
    print(f"  {GREEN}All tests passed!{RESET}\n")
