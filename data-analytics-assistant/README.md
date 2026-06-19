# 📊 AI-Powered Data Analytics Assistant

A production-quality, multi-agent business intelligence system built with **LangGraph**, **Gemini API**, **Streamlit**, **FastAPI**, **PostgreSQL**, and **Pandas**. Upload any business dataset and receive executive-level KPIs, data-driven insights, visualization recommendations, and a complete Power BI dashboard specification — fully automated by AI.

---

## 🏗️ Architecture

```
data-analytics-assistant/
├── app/
│   ├── agents/           # 8 specialized AI agents
│   │   ├── data_loader.py        # File I/O, DataFrame cache
│   │   ├── profiling.py          # Statistical column profiling
│   │   ├── business_analysis.py  # Domain inference
│   │   ├── kpi_discovery.py      # KPI identification
│   │   ├── insight_generation.py # Executive insights
│   │   ├── visualization.py      # Chart recommendations
│   │   ├── powerbi_builder.py    # Dashboard spec generation
│   │   └── orchestrator.py       # Follow-up chat handler
│   │
│   ├── graph/
│   │   ├── workflow.py   # LangGraph StateGraph definition
│   │   └── nodes.py      # Node wrappers & routing logic
│   │
│   ├── schemas/          # Pydantic models for all data types
│   │   ├── state.py      # Central AnalyticsState
│   │   ├── dataset.py    # DatasetSummary, ProfilingResult, ColumnProfile
│   │   ├── kpi.py        # KPI model
│   │   ├── insight.py    # Insight model
│   │   ├── dashboard.py  # DashboardSpec, DashboardPage, Visual, KPICard
│   │   └── chat.py       # ChatMessage model
│   │
│   ├── services/         # Business logic layer
│   │   ├── gemini_service.py     # Gemini API wrapper (JSON + text)
│   │   ├── dataframe_service.py  # File loading, schema extraction
│   │   ├── statistics_service.py # Column profiling & stats
│   │   └── storage_service.py    # High-level persistence
│   │
│   ├── database/         # Data layer
│   │   ├── connection.py # SQLAlchemy engine & session management
│   │   ├── models.py     # ORM models (Session, Analysis, KPI, Insight, etc.)
│   │   └── repository.py # CRUD operations
│   │
│   ├── prompts/          # Prompt templates per agent
│   └── ui/
│       └── streamlit_app.py  # Full Streamlit interface
│
├── uploads/              # Uploaded dataset storage
├── .env                  # Environment variables
├── docker-compose.yml
├── requirements.txt
└── main.py
```

---

## 🤖 Multi-Agent LangGraph Workflow

```
Upload → [Data Loader] → [Profiling] → [Business Analysis]
                                              ↓
              [Power BI Builder] ← [Visualization] ← [Insight Generation] ← [KPI Discovery]
                    ↓
             Dashboard JSON Spec

Follow-up Query → [Chat Orchestrator] → Response with full context
```

### Agents

| Agent | Responsibility |
|---|---|
| **Data Loader** | Load CSV/Excel, validate, extract schema, cache DataFrame |
| **Profiling** | Column types, nulls, distributions, quality score, narrative |
| **Business Analysis** | Infer domain (Sales/Finance/HR/etc.), entities, context |
| **KPI Discovery** | 6-10 domain-specific KPIs with formulas, priorities, definitions |
| **Insight Generation** | 5-8 executive insights with evidence, recommendations, impact |
| **Visualization** | Chart type recommendations per KPI/insight + Power BI mapping |
| **Power BI Builder** | Full multi-page dashboard JSON spec |
| **Chat Orchestrator** | Follow-up Q&A with full analysis context + memory |

---

## 🚀 Quick Start

### Option 1: Local Setup

```bash
# 1. Clone and install
git clone <repo>
cd data-analytics-assistant
pip install -r requirements.txt

# 2. Configure environment
cp .env .env.local
# Edit .env and set GEMINI_API_KEY

# 3. Start PostgreSQL (or use Docker)
docker run -d -p 5432:5432 \
  -e POSTGRES_DB=analytics_db \
  -e POSTGRES_USER=analytics_user \
  -e POSTGRES_PASSWORD=analytics_pass \
  postgres:16-alpine

# 4. Run the app
streamlit run app/ui/streamlit_app.py
# OR
python main.py
```

### Option 2: Docker Compose

```bash
# Set GEMINI_API_KEY in .env, then:
docker-compose up --build
# Open http://localhost:8501
```

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GEMINI_API_KEY` | **Required.** Google Gemini API key | — |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.0-flash` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `UPLOAD_DIR` | Directory for uploaded files | `uploads` |
| `DEBUG` | Enable SQLAlchemy echo | `false` |

---

## 🗄️ Database Schema

```sql
sessions        → id, created_at, updated_at
analyses        → id, session_id, file_name, dataset_summary (JSON), profiling_result (JSON),
                   business_domain, domain_confidence, domain_reasoning
kpis            → id, analysis_id, name, definition, formula, priority, category, raw_data (JSON)
insights        → id, analysis_id, title, type, priority, summary, evidence (JSON), recommendation
dashboard_specs → id, analysis_id, title, spec_json (JSON)
chat_messages   → id, session_id, analysis_id, role, content, message_type, timestamp
```

**No DataFrames are stored in the database.** Only metadata, summaries, and serializable outputs.

---

## 💡 Usage Guide

1. **Upload** a CSV or Excel file via the sidebar
2. **Click "Run Analysis"** — the 7-agent pipeline runs automatically
3. **Review results** across 6 tabs:
   - **Overview** — data profiling narrative, quality issues, column statistics
   - **KPIs** — prioritized KPIs with definitions, formulas, and current values
   - **Insights** — executive insights with evidence and recommendations
   - **Visualizations** — chart recommendations + live Plotly previews
   - **Dashboard** — Power BI JSON spec (downloadable)
   - **Chat** — ask follow-up questions with full analysis context

### Example Follow-Up Queries
- *"Show me only revenue-related insights"*
- *"Explain the top KPI in more detail"*
- *"What are the biggest risks in this dataset?"*
- *"Generate dashboard recommendations for the CFO"*
- *"Which columns have the most business impact?"*

---

## 🔧 Technical Details

### LangGraph State
The central `AnalyticsState` (Pydantic model) flows through all nodes:
- Session & file metadata
- `DatasetSummary` + `ProfilingResult`
- Business domain & reasoning
- List of `KPI` objects
- List of `Insight` objects
- `DashboardSpec` with pages, KPI cards, and visuals
- `ChatMessage` history

### Gemini Prompting Strategy
- **System instructions** per agent with specific expert personas
- **Low temperature (0.2-0.3)** for structured JSON outputs (KPIs, dashboard)
- **Moderate temperature (0.4-0.5)** for narratives and insights
- **JSON extraction** with fallback regex parsing for robustness

### Memory Architecture
- **In-process**: DataFrame cache (`dict`) keyed by file path
- **Session persistence**: PostgreSQL via SQLAlchemy
- **Conversation**: Full chat history passed in each Gemini call (last 10 turns)

---

## 🚀 Future Scalability

- [ ] Add Celery + Redis for async pipeline execution
- [ ] Support multi-file cross-dataset analysis
- [ ] Export to actual Power BI PBIX via Microsoft API
- [ ] Add forecasting agent (Prophet/ARIMA)
- [ ] Multi-user auth with tenant isolation
- [ ] Streaming LangGraph responses to UI
- [ ] RAG layer for industry benchmark retrieval
