# 📊 AI-Powered Data Analytics Assistant

> A production-quality, multi-agent Business Intelligence system that automatically transforms any uploaded CSV or Excel business dataset into executive-level KPIs, data-driven insights, visualization recommendations, and a complete Power BI dashboard specification — powered by **Google Gemini**, orchestrated by **LangGraph**, and delivered through a **Streamlit** interface.

---

## Table of Contents

1. [What This System Does](#1-what-this-system-does)
2. [Technology Stack](#2-technology-stack)
3. [Project Structure](#3-project-structure)
4. [Architecture Overview](#4-architecture-overview)
5. [The Multi-Agent Pipeline](#5-the-multi-agent-pipeline)
6. [Data Flow & LangGraph Workflow](#6-data-flow--langgraph-workflow)
7. [Database Schema](#7-database-schema)
8. [Pydantic Schemas (State Management)](#8-pydantic-schemas-state-management)
9. [Service Layer](#9-service-layer)
10. [Memory & Checkpointing](#10-memory--checkpointing)
11. [Prompt Engineering Strategy](#11-prompt-engineering-strategy)
12. [The Streamlit Interface](#12-the-streamlit-interface)
13. [Prerequisites](#13-prerequisites)
14. [Installation & Setup (Local)](#14-installation--setup-local)
15. [Running with Docker Compose](#15-running-with-docker-compose)
16. [Environment Variables Reference](#16-environment-variables-reference)
17. [Running the Test Suite](#17-running-the-test-suite)
18. [How to Use the Application](#18-how-to-use-the-application)
19. [Example Follow-Up Questions](#19-example-follow-up-questions)
20. [Troubleshooting](#20-troubleshooting)
21. [Future Scalability Roadmap](#21-future-scalability-roadmap)

---

## 1. What This System Does

You upload a raw business dataset (CSV or Excel). The system automatically:

| Step | What Happens |
|------|-------------|
| **Load** | Reads your file, validates structure, infers schema |
| **Profile** | Computes per-column statistics: nulls, distributions, data types, quality score |
| **Classify** | Identifies the business domain (Sales, Finance, HR, Marketing, etc.) with confidence score |
| **KPIs** | Discovers 6–10 measurable KPIs with formulas, priorities, and business definitions |
| **Insights** | Generates 5–8 executive-level observations backed by specific data evidence |
| **Visualize** | Recommends optimal chart types for each KPI and insight |
| **Dashboard** | Produces a complete Power BI JSON specification with pages, cards, and visuals |
| **Report** | Assembles a full Markdown executive report combining all outputs |
| **Chat** | Lets you ask follow-up questions with full analysis context and conversational memory |

No manual configuration. No domain expertise required. Just upload and run.

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **AI Model** | Google Gemini 2.0 Flash (`google-genai`) | All LLM calls: profiling narratives, KPI discovery, insight generation, dashboard specs, chat |
| **Orchestration** | LangGraph 0.3 (`StateGraph`) | Multi-agent pipeline with conditional routing and error handling |
| **UI** | Streamlit 1.45 | Web interface: file upload, tabbed results, live charts, chat |
| **Data Processing** | Pandas 2.2, NumPy 2.2 | DataFrame loading, column profiling, statistical summaries |
| **Visualization** | Plotly 6.1 | Live chart previews in the Visualizations tab |
| **Database** | PostgreSQL 16 + SQLAlchemy 2.0 | Session persistence, analysis history, chat memory |
| **Validation** | Pydantic 2.11 | Typed state objects, schema validation, LangGraph dict coercion |
| **Config** | python-dotenv | Environment variable management |
| **Containers** | Docker + Docker Compose | One-command deployment |

---

## 3. Project Structure

```
data-analytics-assistant/
│
├── app/
│   ├── __init__.py
│   │
│   ├── agents/                      ← 9 AI agent modules
│   │   ├── __init__.py
│   │   ├── data_loader.py           ← Agent 1: File I/O + DataFrame cache
│   │   ├── profiling.py             ← Agent 2: Statistical profiling + Gemini narrative
│   │   ├── business_analysis.py     ← Agent 3: Domain inference (Sales/Finance/HR…)
│   │   ├── kpi_discovery.py         ← Agent 4: KPI identification + formulas
│   │   ├── insight_generation.py    ← Agent 5: Executive insights with evidence
│   │   ├── visualization.py         ← Agent 6: Chart type recommendations
│   │   ├── powerbi_builder.py       ← Agent 7: Full Power BI JSON spec
│   │   ├── report_generator.py      ← Agent 8: Consolidated Markdown report
│   │   └── orchestrator.py          ← Agent 9: Conversational follow-up Q&A
│   │
│   ├── graph/                       ← LangGraph workflow definition
│   │   ├── __init__.py
│   │   ├── workflow.py              ← StateGraph, edges, error routing, singleton
│   │   └── nodes.py                 ← Node wrappers: dict↔AnalyticsState + routing fns
│   │
│   ├── schemas/                     ← Pydantic models for all data contracts
│   │   ├── __init__.py
│   │   ├── state.py                 ← AnalyticsState (central pipeline state)
│   │   ├── dataset.py               ← DatasetSummary, ProfilingResult, ColumnProfile
│   │   ├── kpi.py                   ← KPI model
│   │   ├── insight.py               ← Insight model
│   │   ├── dashboard.py             ← DashboardSpec, DashboardPage, Visual, KPICard
│   │   └── chat.py                  ← ChatMessage model
│   │
│   ├── services/                    ← Business logic, no Streamlit or LangGraph deps
│   │   ├── __init__.py
│   │   ├── gemini_service.py        ← Gemini API wrapper (text + JSON generation)
│   │   ├── dataframe_service.py     ← File loading, schema extraction, serialization
│   │   ├── statistics_service.py    ← Column profiling, type inference, quality scoring
│   │   ├── dashboard_service.py     ← Dashboard validation, enrichment, export utilities
│   │   └── storage_service.py       ← High-level DB persistence (sessions, KPIs, etc.)
│   │
│   ├── database/                    ← Data access layer
│   │   ├── __init__.py
│   │   ├── connection.py            ← SQLAlchemy engine, session factory, init_db()
│   │   ├── models.py                ← ORM models: Session, Analysis, KPI, Insight…
│   │   └── repository.py            ← CRUD operations for all models
│   │
│   ├── memory/                      ← Session memory and checkpointing
│   │   ├── __init__.py
│   │   └── checkpoint.py            ← CheckpointManager (PostgreSQL) + InMemory fallback
│   │
│   ├── prompts/                     ← LLM prompt templates (one file per agent)
│   │   ├── __init__.py
│   │   ├── profiling_prompt.py
│   │   ├── business_prompt.py
│   │   ├── kpi_prompt.py
│   │   ├── insight_prompt.py
│   │   ├── visualization_prompt.py
│   │   ├── dashboard_prompt.py
│   │   └── chat_prompt.py
│   │
│   └── ui/
│       ├── __init__.py
│       └── streamlit_app.py         ← Full Streamlit interface (7 tabs, sidebar, chat)
│
├── uploads/                         ← Uploaded files are stored here
│   └── sample_sales_data.csv        ← 60-row demo dataset (ready to use)
│
├── .env                             ← Environment variables (copy and fill in)
├── requirements.txt                 ← Python dependencies
├── Dockerfile                       ← Container image definition
├── docker-compose.yml               ← PostgreSQL + App orchestration
├── main.py                          ← Entry point (launches Streamlit)
├── test_pipeline.py                 ← 10-section validation test suite
└── README.md                        ← This file
```

---

## 4. Architecture Overview

The system is built in **six clean layers** that never reach downward:

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT UI LAYER                        │
│   File upload · 7 tabs · Live charts · Chat interface        │
└────────────────────────┬────────────────────────────────────┘
                         │ invokes
┌────────────────────────▼────────────────────────────────────┐
│               LANGGRAPH ORCHESTRATION LAYER                  │
│   StateGraph · Conditional edges · Error routing · Nodes     │
└────────────────────────┬────────────────────────────────────┘
                         │ calls
┌────────────────────────▼────────────────────────────────────┐
│                     AGENT LAYER (9 agents)                   │
│   Each agent receives AnalyticsState, returns partial dict   │
└────────────────────────┬────────────────────────────────────┘
                         │ uses
┌────────────────────────▼────────────────────────────────────┐
│                     SERVICE LAYER                            │
│   GeminiService · DataFrameService · StatisticsService       │
│   DashboardService · StorageService                          │
└────────────────────────┬────────────────────────────────────┘
                         │ reads/writes
┌────────────────────────▼────────────────────────────────────┐
│                    DATABASE LAYER                            │
│   PostgreSQL · SQLAlchemy ORM · Repository pattern           │
└────────────────────────┬────────────────────────────────────┘
                         │ validated by
┌────────────────────────▼────────────────────────────────────┐
│                     SCHEMA LAYER                             │
│   Pydantic models for all data contracts and state           │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. The Multi-Agent Pipeline

Each agent is a pure Python function that accepts an `AnalyticsState` and returns a partial state `dict`. LangGraph merges the returned dict back into the global state before passing it to the next node.

### Agent 1 — Data Loader (`agents/data_loader.py`)

**Responsibility:** Load the uploaded file into a Pandas DataFrame, validate it exists, extract a serializable `DatasetSummary`, and cache the DataFrame in process memory.

**Key design:** The DataFrame is **never stored in the database** — only a JSON-serializable `DatasetSummary` (row count, column count, dtypes, 5 sample rows) is saved. The raw DataFrame lives in a process-local dict (`_DATAFRAME_CACHE`) keyed by file path so downstream agents can access it without re-reading disk.

**Outputs added to state:**
- `dataset_summary` — `DatasetSummary` object
- `current_step = "data_loaded"`

**Routing after this agent:** If `is_follow_up=True`, skip the full pipeline and go directly to the Chat Orchestrator. Otherwise continue to Profiling.

---

### Agent 2 — Data Profiling (`agents/profiling.py`)

**Responsibility:** Deep statistical analysis of every column using `StatisticsService`, then a Gemini-generated narrative explaining what the data represents in business terms.

**What it computes per column:**
- `inferred_type`: numeric / categorical / datetime / text / boolean
- Nulls (count + percentage), unique count and percentage
- For **numeric** columns: mean, median, std, min, max, Q25, Q75
- For **categorical** columns: top-10 value frequencies with percentages
- 5 sample values from each column

**Dataset-level metrics:**
- Overall missing data percentage
- Duplicate row count
- Data quality score (0–100, deducted for missing data and duplicates)
- List of quality issues (e.g. "Columns >50% null: customer_notes")

**Gemini call:** Uses `PROFILING_SYSTEM` persona (Senior Data Analytics Engineer) at `temperature=0.3` to write a 3–5 paragraph business-facing profiling narrative.

**Outputs added to state:**
- `profiling_result` — full `ProfilingResult` with column profiles and narrative

---

### Agent 3 — Business Analysis (`agents/business_analysis.py`)

**Responsibility:** Infer the business domain from column names, data types, and sample values. No hardcoded rules — Gemini reasons about the data.

**Supported domains:** Sales, Retail, Marketing, Finance, HR, Operations, E-Commerce, Healthcare, Logistics, Education, Other

**Gemini call:** `temperature=0.2` (lowest temperature, most deterministic). The prompt includes all column names with inferred types and 3 sample rows in JSON format. Returns structured JSON.

**Outputs added to state:**
- `business_domain` — e.g. `"Sales"`
- `domain_confidence` — float 0.0–1.0
- `domain_reasoning` — 2–3 sentence explanation

---

### Agent 4 — KPI Discovery (`agents/kpi_discovery.py`)

**Responsibility:** Identify 6–10 measurable, domain-specific KPIs that can actually be computed from the available columns. Every KPI includes a business definition, formula, priority, and explanation of why executives should care.

**KPI priorities:** Critical / High / Medium / Low

**KPI categories:** Revenue, Operations, Customer, Financial, HR, Quality, Growth

**What makes a good KPI here:** It references real column names, has a computable formula (e.g. `SUM(Revenue) / COUNT(Order ID)`), and is directly relevant to the inferred domain.

**Gemini call:** `temperature=0.25`, JSON output mode. Prompt includes all numeric column stats (mean, min, max, estimated total) and categorical distributions.

**Outputs added to state:**
- `kpis` — list of `KPI` Pydantic objects

---

### Agent 5 — Insight Generation (`agents/insight_generation.py`)

**Responsibility:** Produce 5–8 executive-level insights backed by specific numbers from the actual dataset. Every insight must cite real statistics — no generic statements.

**Insight types:** trend / opportunity / risk / performance / anomaly / benchmark

**What makes these insights different from generic AI output:** The agent first pulls live computed statistics from the cached DataFrame (e.g. `SUM(Revenue) = $52,483`, `top category = Technology at 58%`) and includes them explicitly in the Gemini prompt. The model cannot fabricate numbers — the real values are already in the prompt.

**Each insight includes:**
- `executive_summary` — 1–2 sentence headline with specific numbers
- `detailed_analysis` — 2–3 paragraphs of deeper analysis
- `evidence` — list of specific data points (e.g. "Technology revenue: $30,440 across 23 orders")
- `recommendation` — actionable next step for leadership
- `business_impact` — quantified or qualified impact statement
- `confidence` — High / Medium / Low

**Gemini call:** `temperature=0.4` (slightly more creative for narrative quality).

**Outputs added to state:**
- `insights` — list of `Insight` Pydantic objects

---

### Agent 6 — Visualization (`agents/visualization.py`)

**Responsibility:** Recommend the optimal chart type for each KPI and insight, including Power BI visual type mappings.

**Each recommendation includes:**
- `chart_type` — bar / line / pie / donut / scatter / area / funnel / waterfall / heatmap / treemap / gauge / table / combo
- `x_axis`, `y_axis`, `series_column` — mapped to actual column names
- `aggregation` — sum / avg / count / min / max / none
- `powerbi_visual_type` — the exact Power BI visual identifier string
- `why_this_chart` — rationale for the choice
- `business_purpose` — what decision this visual supports

**Gemini call:** `temperature=0.3`, JSON array output.

**Outputs added to state:**
- `visualization_recommendations` — list of raw dicts (not Pydantic, stays flexible for the UI)

---

### Agent 7 — Power BI Dashboard Builder (`agents/powerbi_builder.py`)

**Responsibility:** Generate a complete, structured Power BI dashboard specification as a JSON object — ready for a developer to implement in Power BI Desktop or via the Power BI REST API.

**Dashboard structure:** 3 pages by default:
1. **Executive Overview** — KPI cards, summary visuals, global filters
2. **Detailed Analysis** — Deep-dive charts, cross-filtering, drill-downs
3. **Trends & Forecasting** — Time-series visuals, period comparisons

**Each page contains:**
- `kpi_cards` — KPI card definitions with measure, format, comparison, and grid position
- `visuals` — chart definitions with type, axes, filters, drill-down, and grid position
- `slicers` — filter column names for interactive filtering
- `theme` — "Corporate" by default

**Outputs added to state:**
- `dashboard_spec` — `DashboardSpec` Pydantic object (also stored as `raw_spec` dict for JSON export)

---

### Agent 8 — Report Generator (`agents/report_generator.py`)

**Responsibility:** Assemble a complete Markdown executive report from all prior agent outputs. This is a **pure Python agent** — no Gemini call. It formats all structured data (KPIs, insights, dashboard spec, quality findings) into a professional, downloadable document.

**Report sections:**
1. Cover page (domain, confidence, timestamp)
2. Dataset Overview (row count, columns, memory)
3. Data Quality (score, issues, column breakdown)
4. Business Context (domain reasoning)
5. KPIs (grouped by priority with formulas and current values)
6. Insights (grouped by priority with evidence and recommendations)
7. Visualization Recommendations (table format)
8. Power BI Dashboard Specification (pages, cards, visuals)
9. Footer (session ID, timestamp)

**Outputs added to state:**
- `executive_report` — Markdown string
- `report_generated_at` — ISO timestamp

---

### Agent 9 — Chat Orchestrator (`agents/orchestrator.py`)

**Responsibility:** Answer follow-up questions using the full analysis context. Triggered instead of the full pipeline when `is_follow_up=True`.

**Context injected into every Gemini call:**
- Business domain and reasoning
- All KPIs with current values
- All insights with recommendations
- Dashboard title and page names
- Last 10 turns of conversation history

**Gemini call:** `temperature=0.5` (more conversational). Uses `CHAT_SYSTEM` persona.

**Memory:** Full `chat_history` list is appended to state and persisted to PostgreSQL after each turn.

---

## 6. Data Flow & LangGraph Workflow

### Pipeline: New Analysis

```
                    ┌──────────────┐
                    │  User Upload  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
               ┌────│  data_loader │────┐  is_follow_up=True
               │    └──────┬───────┘    │
          error│           │ continue   ▼
               │    ┌──────▼───────┐  ┌─────────────────┐
               │    │   profiling  │  │ chat_orchestrator│──► END
               │    └──────┬───────┘  └─────────────────┘
               │           │
               │    ┌──────▼───────┐
               │    │  business_   │
               │    │  analysis    │
               │    └──────┬───────┘
               │           │
               │    ┌──────▼───────┐
               │    │ kpi_discovery│
               │    └──────┬───────┘
               │           │
               │    ┌──────▼───────┐
               │    │  insight_    │
               │    │  generation  │
               │    └──────┬───────┘
               │           │
               │    ┌──────▼───────┐
               │    │visualization │
               │    └──────┬───────┘
               │           │
               │    ┌──────▼───────┐
               │    │  powerbi_    │
               │    │   builder    │
               │    └──────┬───────┘
               │           │
               │    ┌──────▼───────┐
               │    │   report_    │
               │    │  generator   │
               │    └──────┬───────┘
               │           │
               └───► ┌─────▼──────┐
                     │error_handler│──► END
                     └────────────┘
                           │
                          END
```

### Error Handling

Every sequential edge is a **conditional edge** that checks `state.get("error_message")`. If any agent sets `error_message`, the pipeline immediately routes to `error_handler` and then `END`. The error is preserved in state and displayed in the Streamlit UI. The app does not crash.

### State Serialization

LangGraph stores state as plain Python `dict`. Every node wrapper in `graph/nodes.py` does:

```python
def node_kpi_discovery(state: dict) -> dict:
    s = AnalyticsState(**state)          # dict → typed Pydantic model
    result = kpi_discovery_agent(s)      # agent works with typed objects
    result["kpis"] = [k.model_dump() for k in result["kpis"]]  # back to dict
    return {**state, **result}           # merge into LangGraph state dict
```

The `AnalyticsState` model uses a `@model_validator(mode="before")` to coerce all nested dicts back into their typed Pydantic models on construction, so agents always receive clean typed objects regardless of how many LangGraph roundtrips the state has gone through.

---

## 7. Database Schema

Six tables. **No DataFrames are ever stored** — only JSON-serializable metadata.

```sql
-- One row per browser session
sessions
  id           VARCHAR(36) PRIMARY KEY    -- UUID
  created_at   TIMESTAMP
  updated_at   TIMESTAMP

-- One row per file analysis
analyses
  id                VARCHAR(36) PRIMARY KEY
  session_id        VARCHAR(36) → sessions.id
  file_name         VARCHAR(512)
  file_path         VARCHAR(1024)
  file_size_bytes   INTEGER
  dataset_summary   JSON          -- DatasetSummary dict (no DataFrame)
  profiling_result  JSON          -- ProfilingResult dict
  business_domain   VARCHAR(128)
  domain_confidence FLOAT
  domain_reasoning  TEXT

-- One row per KPI per analysis
kpis
  id                  VARCHAR(36) PRIMARY KEY
  analysis_id         VARCHAR(36) → analyses.id
  name, definition    TEXT
  formula             TEXT
  priority, category  VARCHAR
  raw_data            JSON          -- Full KPI dict for reconstruction

-- One row per insight per analysis
insights
  id                  VARCHAR(36) PRIMARY KEY
  analysis_id         VARCHAR(36) → analyses.id
  title, type         VARCHAR/TEXT
  executive_summary   TEXT
  evidence            JSON          -- list of strings
  recommendation      TEXT
  raw_data            JSON

-- One row per analysis (dashboard spec)
dashboard_specs
  id            VARCHAR(36) PRIMARY KEY
  analysis_id   VARCHAR(36) → analyses.id
  title         VARCHAR(512)
  spec_json     JSON              -- Full DashboardSpec dict

-- One row per chat message
chat_messages
  id               VARCHAR(36) PRIMARY KEY
  session_id       VARCHAR(36) → sessions.id
  analysis_id      VARCHAR(36) nullable
  role             VARCHAR(16)   -- "user" or "assistant"
  content          TEXT
  message_type     VARCHAR(64)   -- "text", "analysis", etc.
  message_metadata JSON
  timestamp        TIMESTAMP

-- One row per state snapshot (used by CheckpointManager)
session_snapshots
  id            VARCHAR(36) PRIMARY KEY
  session_id    VARCHAR(36)     -- indexed
  snapshot_key  VARCHAR(256)    -- e.g. "latest_analysis"
  state_json    JSON            -- full AnalyticsState dict
  created_at    TIMESTAMP
  updated_at    TIMESTAMP
```

---

## 8. Pydantic Schemas (State Management)

### `AnalyticsState` — The Central Pipeline Object

Every agent receives this object. LangGraph stores it as a plain dict; the `@model_validator` coerces nested dicts back to typed objects on each instantiation.

```python
class AnalyticsState(BaseModel):
    session_id: str                                  # Browser session UUID
    analysis_id: Optional[str]                       # DB analysis record ID
    user_query: str                                  # Initial query string
    follow_up_query: Optional[str]                   # Chat follow-up query
    file_name: str                                   # e.g. "sales_q1.csv"
    file_path: str                                   # Disk path to uploaded file
    file_size_bytes: int
    dataset_summary: Optional[DatasetSummary]        # Schema + sample rows
    profiling_result: Optional[ProfilingResult]      # Column stats + narrative
    business_domain: str                             # e.g. "Sales"
    domain_confidence: float                         # 0.0 – 1.0
    domain_reasoning: str                            # LLM explanation
    kpis: list[KPI]                                  # Discovered KPIs
    insights: list[Insight]                          # Executive insights
    dashboard_spec: Optional[DashboardSpec]          # Power BI spec
    visualization_recommendations: list[dict]        # Chart recommendations
    chat_history: list[ChatMessage]                  # Full conversation
    current_step: str                                # Pipeline step tracker
    error_message: Optional[str]                     # Set on agent failure
    is_follow_up: bool                               # Routes to chat branch
    executive_report: Optional[str]                  # Final Markdown report
    report_generated_at: Optional[str]               # ISO timestamp
```

### `KPI`

```python
class KPI(BaseModel):
    id: str                          # e.g. "kpi_001"
    name: str                        # e.g. "Total Revenue"
    business_definition: str         # Plain English definition
    formula: Optional[str]           # e.g. "SUM(Revenue)"
    required_columns: list[str]      # Column names needed to compute it
    priority: str                    # "Critical" | "High" | "Medium" | "Low"
    category: str                    # "Revenue" | "Operations" | "Customer" | ...
    why_important: str               # Executive-facing explanation
    current_value: Optional[str]     # Computed value from dataset if possible
    unit: Optional[str]              # "$" | "%" | "units" | "ratio"
    trend_direction: Optional[str]   # "up" | "down" | "stable" | "unknown"
    benchmark: Optional[str]         # Industry benchmark if known
```

### `Insight`

```python
class Insight(BaseModel):
    id: str                          # e.g. "insight_001"
    title: str                       # Punchy headline
    type: str                        # "trend" | "opportunity" | "risk" | "performance" | "anomaly" | "benchmark"
    priority: str                    # "Critical" | "High" | "Medium" | "Low"
    executive_summary: str           # 1–2 sentence headline with numbers
    detailed_analysis: str           # 2–3 paragraph analysis
    evidence: list[str]              # Specific data points (e.g. "Tech revenue: $30,440")
    recommendation: str              # Actionable next step
    affected_kpis: list[str]         # KPI IDs impacted by this insight
    business_impact: Optional[str]   # Quantified impact statement
    confidence: str                  # "High" | "Medium" | "Low"
```

### `DashboardSpec` (simplified)

```python
class DashboardSpec(BaseModel):
    title: str
    description: str
    target_audience: str
    pages: list[DashboardPage]       # Each page has kpi_cards + visuals + slicers
    global_filters: list[str]
    data_refresh_frequency: str
    executive_summary: str
    implementation_notes: list[str]
    raw_spec: dict                   # Original LLM JSON for export
```

---

## 9. Service Layer

### `GeminiService` (`services/gemini_service.py`)

Wraps the `google-genai` SDK. Two core methods:

- `generate(prompt, temperature, max_tokens, system_instruction)` → raw text string
- `generate_json(prompt, ...)` → parsed Python object (dict or list)

`generate_json` appends `"Return ONLY valid JSON..."` to the prompt and strips markdown fences from the response before parsing. Falls back to regex-based JSON extraction if standard `json.loads()` fails.

### `DataFrameService` (`services/dataframe_service.py`)

- `load_file(path)` → `pd.DataFrame` — supports `.csv` and `.xlsx`/`.xls`
- `extract_summary(df, file_name)` → `DatasetSummary` — row count, columns, dtypes, memory, 5 sample rows
- `clean_for_serialization(obj)` → replaces `NaN`, `inf`, numpy types for JSON safety

### `StatisticsService` (`services/statistics_service.py`)

- `profile_dataframe(df, summary)` → `ProfilingResult`
- Per-column type inference: tries numeric → bool → datetime → high cardinality (text) → low cardinality (categorical)
- Computes full descriptive stats for numeric columns and top-10 value counts for categorical columns
- Calculates data quality score: `max(0, 100 - missing_pct - (duplicate_count / row_count * 10))`

### `DashboardService` (`services/dashboard_service.py`)

Post-processing utilities for `DashboardSpec` objects:

- `validate_spec(spec)` → list of warning strings (empty = valid)
- `enrich_with_kpis(spec, kpis)` → injects KPI cards from the KPI list into a page
- `enrich_with_insights(spec, insights)` → adds card visuals for critical insights
- `to_json(spec)` → pretty-printed JSON string
- `to_powerbi_template(spec)` → Power BI Report Builder-compatible JSON structure
- `to_markdown_summary(spec)` → compact Markdown summary
- `count_total_visuals(spec)`, `get_all_measures(spec)`, `get_all_dimensions(spec)` → introspection utilities

### `StorageService` (`services/storage_service.py`)

High-level persistence facade over `AnalyticsRepository`. All methods open their own DB session via the `get_db()` context manager:

- `ensure_session(session_id)` — creates session row if missing
- `create_analysis(state)` → analysis ID string
- `update_analysis(analysis_id, state)` — stores profiling result and business context
- `save_kpis(analysis_id, kpis)` — replaces all KPIs for an analysis
- `save_insights(analysis_id, insights)` — replaces all insights
- `save_dashboard_spec(analysis_id, spec)` — upserts dashboard spec
- `save_message(session_id, message, analysis_id)` — appends chat message
- `get_chat_history(session_id, limit=50)` — retrieves conversation

---

## 10. Memory & Checkpointing

The system maintains **three levels of memory**:

### Level 1 — In-Process DataFrame Cache

```python
# agents/data_loader.py
_DATAFRAME_CACHE: dict[str, pd.DataFrame] = {}
```

The raw DataFrame lives here during a Streamlit session. Other agents call `get_cached_dataframe(file_path)` to access it. This avoids re-reading and re-parsing the file for every agent. Lives as long as the Python process is running.

### Level 2 — Streamlit Session State

The full result dict is stored in `st.session_state.analysis_result` after a successful pipeline run. Chat history is mirrored in `st.session_state.chat_history`. This persists across Streamlit re-renders within the same browser tab.

### Level 3 — PostgreSQL Persistence

Two mechanisms:

**`StorageService`** — Saves analysis records, KPIs, insights, dashboard specs, and chat messages to their respective tables after the pipeline completes. These survive process restarts.

**`CheckpointManager`** (`memory/checkpoint.py`) — Saves a full JSON snapshot of `AnalyticsState` to the `session_snapshots` table after every successful analysis. Can restore full state from a session ID + key lookup. When PostgreSQL is unavailable, `InMemoryCheckpointManager` provides the same API using a process-local dict.

```python
# How checkpointing works
cp = get_checkpoint_manager(use_db=True)
cp.save(session_id, "latest_analysis", state_dict)   # upsert
state = cp.load(session_id, "latest_analysis")        # restore
```

---

## 11. Prompt Engineering Strategy

Each agent has a dedicated prompt file in `app/prompts/` with a `SYSTEM` persona string and a `PROMPT` template with `{named_placeholders}`.

| Agent | Persona | Temperature | Output Format |
|-------|---------|-------------|---------------|
| Profiling | Senior Data Analytics Engineer | 0.3 | Free text narrative |
| Business Analysis | Senior BI Analyst (15+ years) | 0.2 | Structured JSON object |
| KPI Discovery | Chief Analytics Officer | 0.25 | JSON array of KPI objects |
| Insight Generation | Chief Data Officer | 0.4 | JSON array of insight objects |
| Visualization | Data Viz Expert + BI Architect | 0.3 | JSON array of viz recommendations |
| Dashboard Builder | Power BI Solutions Architect | 0.3 | JSON object (full spec) |
| Chat | BI Assistant with full context | 0.5 | Free text Markdown response |

**Why different temperatures?**
- `0.2` for business domain inference — needs to be deterministic and factual
- `0.3–0.35` for structured JSON outputs — needs consistency but some flexibility
- `0.4–0.5` for narratives and chat — benefits from slightly more varied language

**JSON robustness:** `generate_json()` appends `"Return ONLY valid JSON. No markdown fences, no preamble."` to every JSON prompt, then strips any remaining fences with regex, then falls back to scanning for the first `{` or `[` character. This handles the cases where the model adds brief preamble text before the JSON.

---

## 12. The Streamlit Interface

The UI is a single `streamlit_app.py` file (~1000 lines) with a dark theme and custom CSS.

### Sidebar
- **File uploader** — drag/drop CSV or Excel
- **Run Analysis button** — triggers the full pipeline
- **Session info** — truncated session UUID
- **Domain badge** — shows inferred domain + confidence after analysis
- **Download Report (MD)** — sidebar download for the Markdown executive report
- **New Analysis button** — resets state cleanly

### Main Area — 7 Tabs

| Tab | Content |
|-----|---------|
| **📋 Overview** | Profiling narrative · Quality issues · Column type pie chart · Missing data bar chart · Column statistics table · Raw data preview (first 20 rows) |
| **📈 KPIs** | Priority-filtered KPI cards with definition, formula, current value, required columns, and why-it-matters |
| **💡 Insights** | Type-filtered insight cards with badge, summary, detailed analysis, evidence bullets, recommendation, and business impact |
| **📊 Visualizations** | Chart recommendation table + live Plotly previews generated from actual data |
| **🗂️ Dashboard** | Dashboard page specs, KPI cards, visual definitions, download Power BI JSON spec, implementation notes |
| **📄 Report** | Full Markdown executive report rendered inline + download button + Power BI template export + spec stats |
| **💬 Chat** | Suggested prompts · Chat history display · `st.chat_input` input · Suggestion buttons |

### Progress Animation

The 7-step pipeline progress is shown with pill badges that cycle through states:
- Idle → `step-pill` (grey)
- Running → `step-pill active` (blue, shows ⏳)
- Done → `step-pill done` (green, shows ✅)

---

## 13. Prerequisites

Before installing, make sure you have:

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Python | ≥ 3.11 | `python --version` |
| pip | Latest | `pip --version` |
| PostgreSQL | ≥ 14 (or use Docker) | `psql --version` |
| Docker & Docker Compose | Any recent version | `docker --version` |
| Google Gemini API Key | Free tier works | [Get key](https://aistudio.google.com/app/apikey) |

You need a **Gemini API key** from [Google AI Studio](https://aistudio.google.com/app/apikey). The free tier (1500 requests/day) is sufficient for development. The system uses `gemini-2.0-flash` by default which is fast and cost-efficient.

---

## 14. Installation & Setup (Local)

### Step 1 — Clone the project

```bash
git clone <your-repo-url>
cd data-analytics-assistant
```

### Step 2 — Create a virtual environment

```bash
python -m venv venv

# Activate it:
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure environment variables

```bash
cp .env .env.local   # optional: keep original as template
```

Open `.env` and fill in your values:

```env
# ── REQUIRED ────────────────────────────────────────────────────────────────
GEMINI_API_KEY=your_actual_gemini_api_key_here

# ── OPTIONAL: Change Gemini model ───────────────────────────────────────────
GEMINI_MODEL=gemini-2.0-flash

# ── DATABASE (leave defaults if using Docker) ────────────────────────────────
DATABASE_URL=postgresql://analytics_user:analytics_pass@localhost:5432/analytics_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=analytics_db
DB_USER=analytics_user
DB_PASSWORD=analytics_pass

# ── APP ─────────────────────────────────────────────────────────────────────
UPLOAD_DIR=uploads
MAX_FILE_SIZE_MB=50
DEBUG=false
```

### Step 5 — Start PostgreSQL

**Option A — Docker (easiest):**
```bash
docker run -d \
  --name analytics_postgres \
  -e POSTGRES_DB=analytics_db \
  -e POSTGRES_USER=analytics_user \
  -e POSTGRES_PASSWORD=analytics_pass \
  -p 5432:5432 \
  postgres:16-alpine
```

**Option B — Local PostgreSQL:**
```bash
# Create the database and user manually
psql -U postgres
CREATE DATABASE analytics_db;
CREATE USER analytics_user WITH PASSWORD 'analytics_pass';
GRANT ALL PRIVILEGES ON DATABASE analytics_db TO analytics_user;
\q
```

> **Note:** If PostgreSQL is unavailable, the app still works fully — it falls back to `InMemoryCheckpointManager` and skips DB persistence. You'll see a yellow warning banner in the UI.

### Step 6 — Create the uploads directory

```bash
mkdir -p uploads
```

### Step 7 — Run the application

```bash
# Option A — via main.py
python main.py

# Option B — directly with Streamlit
streamlit run app/ui/streamlit_app.py

# Option C — with custom port
streamlit run app/ui/streamlit_app.py --server.port 8080
```

Open your browser at **http://localhost:8501**

The database tables are created automatically on first launch via `init_db()`.

---

## 15. Running with Docker Compose

The cleanest way to run the full system (app + PostgreSQL) in one command.

### Step 1 — Set your Gemini API key

Edit `.env` and set `GEMINI_API_KEY=your_key_here`

### Step 2 — Build and start

```bash
docker-compose up --build
```

This will:
1. Pull `postgres:16-alpine` and start the database
2. Wait for the DB health check to pass
3. Build the app Docker image
4. Start the Streamlit app on port 8501

### Step 3 — Open the app

Go to **http://localhost:8501**

### Useful Docker commands

```bash
# Start in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# View only app logs
docker-compose logs -f app

# Stop everything
docker-compose down

# Stop and delete database data (full reset)
docker-compose down -v

# Rebuild just the app (after code changes)
docker-compose up --build app
```

---

## 16. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | **Yes** | — | Google Gemini API key from AI Studio |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model name. Use `gemini-1.5-pro` for higher quality at higher cost |
| `DATABASE_URL` | No | `postgresql://analytics_user:analytics_pass@localhost:5432/analytics_db` | Full PostgreSQL connection string |
| `DB_HOST` | No | `localhost` | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |
| `DB_NAME` | No | `analytics_db` | Database name |
| `DB_USER` | No | `analytics_user` | Database username |
| `DB_PASSWORD` | No | `analytics_pass` | Database password |
| `UPLOAD_DIR` | No | `uploads` | Directory where uploaded files are saved |
| `MAX_FILE_SIZE_MB` | No | `50` | Maximum upload file size |
| `DEBUG` | No | `false` | Set `true` to enable SQLAlchemy query logging |

---

## 17. Running the Test Suite

The project includes a 10-section test script that validates every major component without needing a running Streamlit server.

```bash
# Make sure you're in the project root with venv activated
python test_pipeline.py
```

### What gets tested

| Section | Tests |
|---------|-------|
| 1 | All Python imports (schemas, services, agents, graph, memory) |
| 2 | Schema instantiation + dict→model roundtrip (LangGraph coercion) |
| 3 | DataFrameService: load CSV, extract summary, serialization |
| 4 | StatisticsService: column profiling, type inference, quality score |
| 5 | Gemini connectivity (skipped if `GEMINI_API_KEY` not set) |
| 6 | DashboardService: validation, JSON export, Power BI template, enrichment |
| 7 | InMemoryCheckpointManager: save, load, list, delete |
| 8 | ReportGenerator: full Markdown report with all sections |
| 9 | LangGraph graph compilation (all nodes registered and connected) |
| 10 | Full end-to-end pipeline run on `sample_sales_data.csv` (skipped without API key) |

### Expected output (without Gemini key)

```
────────────────────────────────────────────────────────────
  1. Import Health Check
────────────────────────────────────────────────────────────
  ✓ All schemas imported
  ✓ All services imported
  ✓ All agents imported
  ✓ Graph workflow imported
  ✓ Checkpoint manager imported

... (sections 2-9 all pass) ...

────────────────────────────────────────────────────────────
  Results
────────────────────────────────────────────────────────────

  Total: 28  |  Passed: 27  |  Failed: 0  |  Skipped: 1
  All tests passed!
```

---

## 18. How to Use the Application

### Step 1 — Prepare your dataset

Supported formats: **CSV** (`.csv`) and **Excel** (`.xlsx`, `.xls`)

Your file should have:
- A header row with column names
- Business data (not raw logs or system data)
- Ideally 100+ rows for meaningful insights (the system works with any size)

The included `uploads/sample_sales_data.csv` is a 60-row sales dataset you can use for an immediate demo.

### Step 2 — Upload and analyze

1. Open the app at `http://localhost:8501`
2. Click **"Drop CSV or Excel file"** in the sidebar or drag your file onto it
3. Click the **"🚀 Run Analysis"** button
4. Watch the 7-step pipeline progress indicator
5. Results appear across 7 tabs when complete

Typical pipeline time: **30–60 seconds** depending on dataset size and Gemini API latency.

### Step 3 — Explore the results

**Overview tab** — Start here. Read the profiling narrative to understand your data. Check the quality score and fix any flagged issues in your source data.

**KPIs tab** — Filter by priority (Critical/High/Medium/Low). Each card shows the business definition, formula, required columns, and current value computed from your data.

**Insights tab** — Filter by type (trend, opportunity, risk, etc.). Each insight card has a collapsible detailed section. Critical and High priority insights start expanded. Every recommendation is actionable and specific.

**Visualizations tab** — See the chart recommendation table and live Plotly previews built from your actual data. These tell you what charts to build in Power BI or Tableau.

**Dashboard tab** — Review the 3-page dashboard specification. Download the JSON spec to hand off to a Power BI developer. Each page shows KPI card definitions and visual placements.

**Report tab** — Full Markdown executive report combining all outputs. Download it as `.md` or copy-paste into Word/Notion/Confluence. Also shows the Power BI template export.

**Chat tab** — Ask follow-up questions in natural language. The AI has full context of all KPIs, insights, and the dashboard spec.

### Step 4 — Download your outputs

From the **sidebar:**
- 📄 Download Report (MD) — full Markdown executive report

From the **Dashboard tab:**
- ⬇️ Download JSON Spec — raw Power BI dashboard specification

From the **Report tab:**
- ⬇️ Download Report (MD) — same Markdown report
- ⬇️ Download Power BI Template JSON — developer-ready template structure

---

## 19. Example Follow-Up Questions

Once your analysis is complete, try these in the Chat tab:

```
Show me only the Critical priority insights
```
```
Explain why Technology is the top-performing category
```
```
What are the biggest risks in this dataset?
```
```
Which KPIs should the CFO focus on first?
```
```
Generate a 3-bullet executive summary for the board
```
```
What visualizations would you recommend for a weekly ops meeting?
```
```
How would you design the Executive Overview dashboard page?
```
```
Which columns have the most business impact and why?
```
```
Compare the performance of East vs West regions
```
```
What data quality issues should I fix before going live?
```

---

## 20. Troubleshooting

### `GEMINI_API_KEY` is not set

**Symptom:** Profiling agent returns an error about authentication.

**Fix:**
```bash
# Check your .env file
cat .env | grep GEMINI

# Make sure it's loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GEMINI_API_KEY', 'NOT SET'))"
```

---

### Database connection error

**Symptom:** Yellow warning banner "Database unavailable (running without persistence)"

**This is non-fatal.** The app runs fully in-memory. To fix:

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check connection
psql postgresql://analytics_user:analytics_pass@localhost:5432/analytics_db -c "SELECT 1"

# If using Docker Compose, check health
docker-compose ps
```

---

### Gemini returns invalid JSON

**Symptom:** `ValueError: Could not extract valid JSON from response`

This happens rarely when the model adds extra preamble. The `generate_json()` method has three fallback strategies, but if it still fails:

```bash
# Try switching to a different model in .env
GEMINI_MODEL=gemini-1.5-flash

# Or enable debug to see the raw Gemini response
DEBUG=true
```

---

### File upload fails silently

**Symptom:** File uploaded but "Run Analysis" does nothing.

**Fix:** Check that the `uploads/` directory exists and is writable:
```bash
mkdir -p uploads
chmod 755 uploads
```

---

### `ModuleNotFoundError: No module named 'app'`

**Symptom:** Import error when running from a subdirectory.

**Fix:** Always run commands from the project root:
```bash
cd data-analytics-assistant
python main.py
# NOT: cd app && python ui/streamlit_app.py
```

---

### Docker: port 8501 already in use

```bash
# Find what's using the port
lsof -i :8501

# Kill it, or change the port in docker-compose.yml:
# ports:
#   - "8502:8501"
```

---

### Analysis is very slow

- `gemini-2.0-flash` is the fastest model (default). Don't switch to `gemini-1.5-pro` unless you need higher quality.
- Large files (>10,000 rows) will slow down the Statistics Service. The profiling prompt itself is token-heavy.
- The pipeline makes **6 separate Gemini API calls** sequentially. Total time is roughly `6 × average_latency`.

---

## 21. Future Scalability Roadmap

| Feature | Description |
|---------|-------------|
| **Async pipeline** | Move LangGraph execution to Celery + Redis to support concurrent users and non-blocking UI |
| **Streaming responses** | Use Gemini streaming to show partial results as each agent completes |
| **Multi-file analysis** | Cross-dataset KPI calculation and joined insights |
| **Forecasting agent** | Add an Agent 10 that runs Prophet or ARIMA on datetime columns and appends trend forecasts to the report |
| **Power BI automation** | Connect to the Power BI REST API to programmatically create actual PBIX reports from the dashboard spec |
| **RAG knowledge base** | Add a vector database of industry benchmarks so the insight agent can compare KPIs against sector averages |
| **Multi-user auth** | Tenant isolation with user accounts, session ownership, and role-based access control |
| **Scheduled reports** | Cron-based re-analysis of recurring data files with email delivery |
| **Export to Excel** | `openpyxl`-based Excel workbook with one sheet per KPI, insight table, and chart placeholders |
| **Agent tracing** | LangSmith integration for full agent call tracing, prompt inspection, and latency monitoring |

---

*Built with LangGraph · Google Gemini · Streamlit · PostgreSQL · Pydantic*
