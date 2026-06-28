# AutoMark AI — Data Analytics Assistant

> **Stack:** Python 3.12 · Streamlit · LangGraph · Google Gemini 2.5 · PostgreSQL · Pandas · Plotly

Part of the **AutoMark AI** unified platform. Both this service and the [CRM Agent](../CRM/README.md) share one PostgreSQL database (`automark`).

---

## What It Does

An AI-powered business intelligence assistant that turns raw data into executive insights in minutes. Upload a CSV or Excel file (or connect a SQL source) and receive:

- **Statistical profiling** — column types, missing data, quality score
- **Business domain inference** — Sales, Finance, HR, Operations, etc.
- **KPI discovery** — 6–10 relevant KPIs with formulas and current values
- **Executive insights** — 5–8 data-driven observations with evidence and recommendations
- **Visualization recommendations** — chart types with live Plotly previews
- **Full executive report** — downloadable Markdown

**CRM Integration:** The sidebar includes a built-in **"🤝 Analyze CRM Data"** loader that pulls `leads`, `conversations`, or `escalations` directly from the shared database and runs the full AI pipeline on them — no file upload needed.

---

## Database

Tables in the shared `automark` PostgreSQL database written by this service:

| Table | Description |
|-------|-------------|
| `sessions` | Browser sessions |
| `analyses` | Per-dataset analysis metadata and domain inference |
| `kpis` | Discovered KPIs per analysis |
| `insights` | Executive insights per analysis |
| `chat_messages` | Follow-up conversation history |
| `session_snapshots` | LangGraph checkpoint state |

Tables this service can **read** from the CRM (via `shared/crm_reader.py`):

| Table | Description |
|-------|-------------|
| `leads` | Lead profiles — scores, budgets, contact info |
| `conversations` | Summary memory per user, message counts |
| `escalations` | Human handoff records with priority and status |

---

## Agent Pipeline (LangGraph)

```
data_loader
  └─► profiling
        └─► business_analysis
              └─► kpi_discovery
                    └─► insight_generation
                          └─► visualization
                                └─► report_generator → END

Follow-up path:
data_loader → chat_orchestrator → END
```

---

## Project Structure

```
data-analytics-assistant/
└── app/
    ├── agents/
    │   ├── data_loader.py        ← CSV/Excel/SQL loading + DataFrame cache
    │   ├── profiling.py          ← StatisticsService + Gemini narrative
    │   ├── business_analysis.py  ← Gemini domain inference (JSON output)
    │   ├── kpi_discovery.py      ← Gemini structured KPI extraction
    │   ├── insight_generation.py ← Gemini evidence-backed insights
    │   ├── visualization.py      ← chart type recommendations
    │   ├── report_generator.py   ← Markdown executive report assembly
    │   └── orchestrator.py       ← follow-up chat Q&A handler
    ├── database/
    │   ├── connection.py         ← SQLAlchemy lazy engine + init_db()
    │   ├── models.py             ← ORM models for Analytics tables
    │   └── repository.py         ← CRUD — analyses, KPIs, insights, chat
    ├── graph/
    │   ├── workflow.py           ← LangGraph StateGraph definition
    │   └── nodes.py              ← node wrappers + routing logic
    ├── memory/
    │   └── checkpoint.py         ← PostgreSQL + in-memory session snapshots
    ├── prompts/                  ← per-agent Gemini prompt templates
    ├── schemas/
    │   ├── state.py              ← AnalyticsState (central LangGraph state)
    │   ├── dataset.py            ← DatasetSummary, ProfilingResult, ColumnProfile
    │   ├── kpi.py                ← KPI model
    │   ├── insight.py            ← Insight model with evidence + recommendations
    │   ├── chat.py               ← ChatMessage model
    │   └── datasource.py         ← DataSource (file or SQL discriminated union)
    ├── services/
    │   ├── gemini_service.py     ← ChatGoogleGenerativeAI wrapper (text + JSON)
    │   ├── dataframe_service.py  ← CSV/Excel loading + schema extraction
    │   ├── statistics_service.py ← column profiling + quality scoring
    │   ├── sql_source_service.py ← read-only SQL → DataFrame (100k row cap)
    │   └── storage_service.py    ← high-level persistence API
    └── ui/
        └── streamlit_app.py      ← 6-tab Streamlit UI (893 lines)
```

---

## Running

> The database must be running first. See the [root start.sh](../start.sh) or the [root README](../README.md).

```bash
# From the AutoMarkAi/ root
docker-compose up db -d

# Then from AutoMarkAi/ root
streamlit run data-analytics-assistant/app/ui/streamlit_app.py --server.port 8501
```

App: http://localhost:8501

---

## UI Tabs

| Tab | Content |
|-----|---------|
| **Overview** | Profiling narrative, quality issues, column stats, data preview |
| **KPIs** | Priority-filtered cards with definitions, formulas, current values |
| **Insights** | Type/priority filtered cards with evidence, recommendations, business impact |
| **Visualizations** | Recommended chart types + live Plotly previews |
| **Report** | Full Markdown executive report with download button |
| **Chat** | Suggested prompts + follow-up Q&A with Gemini |

---

## CRM Data Integration

The sidebar **"🤝 Analyze CRM Data"** section lets you load any CRM table directly:

```
Select table:  leads / conversations / escalations
               ↓
Load & Analyze → saves CSV to uploads/ → runs full 8-agent pipeline
               ↓
Results appear in all 6 tabs
```

Powered by [shared/crm_reader.py](../shared/crm_reader.py).

---

## Supported Data Sources

| Source | Details |
|--------|---------|
| File upload | CSV, XLSX, XLS — up to 50 MB |
| SQL database | Any SQLAlchemy-compatible DB via connection string (SELECT-only, 100k row cap) |
| CRM database | Direct load of `leads`, `conversations`, `escalations` from the shared `automark` DB |

---

## Environment Variables

All loaded from `../.env` (the root unified `.env`).

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI Studio key |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `UPLOAD_DIR` | No | File upload directory (default: `uploads`) |
| `MAX_FILE_SIZE_MB` | No | Upload size limit (default: `50`) |
| `SQL_SOURCE_MAX_ROWS` | No | SQL query row cap (default: `100000`) |
