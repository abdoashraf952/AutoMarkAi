# AutoMark AI — Unified Business Intelligence Platform

> **AI-powered CRM agent + Data Analytics Assistant sharing one PostgreSQL database.**
> Built on Google Gemini 2.5 · LangGraph · FastAPI · Streamlit · pgvector

---

## Overview

AutoMark AI is a unified platform that combines two intelligent systems into a single monorepo with a shared database. It helps businesses automate customer conversations across social media and voice channels while simultaneously analyzing business data for strategic insights.

```
                        ┌─────────────────────────────────────┐
                        │         AutoMark AI Platform         │
                        │                                      │
     Facebook ──────►   │  ┌───────────────┐  ┌────────────┐ │
     Messenger          │  │  ORCAST CRM   │  │ Analytics  │ │
     Comments ──────►   │  │   Agent       │  │ Assistant  │ │
     Vapi Voice ─────►  │  │  Port 8000    │  │ Port 8501  │ │
                        │  └───────┬───────┘  └─────┬──────┘ │
                        │          │                 │        │
                        │          └────────┬────────┘        │
                        │                  │                  │
                        │    ┌─────────────▼──────────────┐   │
                        │    │  PostgreSQL + pgvector      │   │
                        │    │  Database: automark         │   │
                        │    │  Port 5432                  │   │
                        │    └─────────────────────────────┘   │
                        └─────────────────────────────────────┘
```

---

## The Two Services

### 1. ORCAST CRM Agent — `http://localhost:8000`

An AI-powered conversational sales agent that runs 24/7 on three channels simultaneously. It qualifies leads, answers questions from your knowledge base, creates HubSpot contacts, scores leads, and escalates to humans with full context when needed.

**Channels:**

| Channel | What it does |
|---------|-------------|
| **Facebook Messenger** | Receives text, voice (transcribed by Gemini), and images (described by Gemini). Replies with text or synthesized TTS audio. |
| **Facebook Page Comments** | Detects new comments on your Page posts. Replies publicly with a brief acknowledgement, then sends the full AI response as a **private Messenger DM** — converting public engagement into private conversations. |
| **Vapi Voice (Phone)** | Handles live inbound calls. Vapi manages speech-to-text and text-to-speech; ORCAST handles the conversation logic. |

**When a human agent is needed:**
- Creates an escalation record in PostgreSQL
- Adds a note to the HubSpot contact
- Sends a **Gmail notification email** with the full conversation summary, lead profile, and recent message transcript

### 2. Data Analytics Assistant — `http://localhost:8501`

An AI-powered business intelligence tool that turns raw datasets into executive insights. Upload a CSV or Excel file (or connect a SQL source) and receive KPIs, data-driven insights, visualization recommendations, and a full Markdown executive report — all generated automatically by AI.

**Built-in CRM integration:** The sidebar includes a **"🤝 Analyze CRM Data"** feature that loads leads, conversations, or escalations directly from the shared database and runs the full analysis pipeline on them.

---

## Full Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AutoMark AI Monorepo                            │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    ORCAST CRM Agent (FastAPI)                     │   │
│  │                                                                   │   │
│  │  Channels           Graph (LangGraph)         Integrations        │   │
│  │  ─────────          ──────────────────         ────────────        │   │
│  │  Messenger ──►      memory_load                HubSpot REST        │   │
│  │  FB Comments ──►    intent_classify    ──►     Gmail SMTP          │   │
│  │  Vapi Voice ──►     hubspot_node               pgvector RAG        │   │
│  │                     rag_node                   Gemini LLM          │   │
│  │                     lead_scoring_node          TTS / STT            │   │
│  │                     handoff_node                                   │   │
│  │                     generate_response                              │   │
│  │                     save_memory                                    │   │
│  │                     messaging_node                                 │   │
│  └───────────────────────────┬──────────────────────────────────────┘   │
│                               │ reads/writes                             │
│  ┌────────────────────────────▼────────────────────────────────────┐    │
│  │                  PostgreSQL + pgvector (automark)                 │    │
│  │                                                                   │    │
│  │  CRM Tables               Analytics Tables                        │    │
│  │  ──────────               ─────────────────                       │    │
│  │  conversations            sessions                                │    │
│  │  leads                    analyses                                │    │
│  │  escalations              kpis                                    │    │
│  │  document_chunks          insights                                │    │
│  │  (pgvector HNSW)          chat_messages                           │    │
│  └────────────────────────────▲────────────────────────────────────┘    │
│                               │ reads/writes                             │
│  ┌────────────────────────────┴────────────────────────────────────┐    │
│  │              Data Analytics Assistant (Streamlit)                 │    │
│  │                                                                   │    │
│  │  Input Sources          8-Agent Pipeline        Output             │    │
│  │  ─────────────          ─────────────────        ──────            │    │
│  │  CSV / Excel ──►        data_loader              6-tab UI          │    │
│  │  SQL Database ──►       profiling        ──►     KPI cards         │    │
│  │  CRM Tables ──►         business_analysis        Insights          │    │
│  │                         kpi_discovery            Charts            │    │
│  │                         insight_generation       Report (MD)       │    │
│  │                         visualization            Chat Q&A          │    │
│  │                         report_generator                           │    │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### ORCAST Graph Pipeline

Every inbound message (from any channel) runs through this LangGraph StateGraph:

```
Inbound Message (Messenger / FB Comment / Vapi)
         │
         ▼
   memory_load  ──► loads rolling summary + lead profile from PostgreSQL
         │
         ▼
  [already escalated?]
         ├── YES ──► already_escalated ──► send "already escalated" reply
         │
         └── NO ──► intent_classify  ──► Gemini structured output
                          │
                          ▼
               [route by intent]
                ├── crm_request    ──► hubspot_node      ─┐
                ├── knowledge_question ──► rag_node       ─┤
                ├── lead_qualification ──► lead_scoring   ─┤──► generate_response
                ├── escalation     ──► handoff_node       ─┤
                └── general_conversation ─────────────────┘
                                                           │
                                                    save_memory
                                                           │
                                                    messaging_node
                                                           │
                                                    Reply to channel
```

### Analytics Pipeline

```
Data Source (CSV / SQL / CRM tables)
         │
         ▼
   data_loader  ──► caches DataFrame in memory
         │
         ▼
   profiling  ──► column stats, quality score, Gemini narrative
         │
         ▼
   business_analysis  ──► Gemini infers domain (Sales, Finance, HR…)
         │
         ▼
   kpi_discovery  ──► Gemini identifies 6–10 KPIs with formulas
         │
         ▼
   insight_generation  ──► Gemini generates 5–8 evidence-backed insights
         │
         ▼
   visualization  ──► recommends chart types + live Plotly previews
         │
         ▼
   report_generator  ──► assembles full Markdown executive report
         │
         ▼
   Streamlit UI (6 tabs: Overview / KPIs / Insights / Charts / Report / Chat)
```

### RAG (Knowledge Base) Pipeline

```
knowledge_base/*.md  (company info, services, pricing, FAQ…)
         │
         ▼  python -m app.rag.ingest --source ./knowledge_base
         │
   Load & chunk (2000 chars, 200 overlap)
         │
         ▼
   Embed with Gemini (models/gemini-embedding-2 → 768 dimensions)
         │
         ▼
   Upsert into document_chunks
         │   ├── VECTOR(768) HNSW index  (dense cosine search)
         │   └── TSVECTOR GIN index      (sparse full-text search)
         │
         ▼  at query time
   Hybrid RRF fusion (dense + sparse results)
         │
         ▼
   Gemini reranking
         │
         ▼
   Grounded answer generation (LCEL chain)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Google Gemini 2.5 Flash (primary) · Gemini 2.5 Pro (fallback) |
| **Embeddings** | Gemini Embedding 2 (768-dim) via Google AI SDK |
| **Orchestration** | LangGraph StateGraph (ORCAST graph + Analytics graph) |
| **CRM Backend** | FastAPI · asyncpg · pgvector |
| **Analytics Frontend** | Streamlit · Plotly |
| **Database** | PostgreSQL 16 + pgvector extension |
| **CRM Integrations** | HubSpot REST v3 · Meta Graph API v19 · Vapi Voice |
| **Notifications** | Gmail SMTP · Resend API |
| **Tracing** | LangSmith |
| **Containerization** | Docker · Docker Compose |

---

## Project Structure

```
AutoMarkAi/
│
├── .env                              ← secrets (gitignored — copy from .env.example)
├── .env.example                      ← template with all variables documented
├── config.py                         ← unified pydantic-settings for both services
├── docker-compose.yml                ← three services: db + crm + analytics
├── Dockerfile                        ← single image for both services
├── requirements.txt                  ← combined Python dependencies
├── start.sh                          ← one-command dev launcher
│
├── shared/                           ← cross-project utilities
│   ├── crm_models.py                 ← SQLAlchemy read-only models for CRM tables
│   ├── crm_reader.py                 ← load CRM data as DataFrames (used by Analytics)
│   └── log_visualizer.py             ← parse CRM JSON logs into timeline charts
│
├── CRM/                              ← ORCAST CRM Agent
│   ├── main.py                       ← FastAPI app + lifespan (DB init, graph compile)
│   ├── config.py                     ← thin redirect → root config.py
│   ├── scripts/init_db.sql           ← PostgreSQL schema + pgvector indexes
│   ├── knowledge_base/               ← markdown docs for RAG (edit these!)
│   └── app/
│       ├── api/
│       │   ├── messenger.py          ← Messenger webhook + private DM sender
│       │   ├── facebook_comments.py  ← Page Comments webhook
│       │   ├── vapi.py               ← Vapi voice webhook + HMAC verification
│       │   └── admin.py              ← /admin/db/* database access endpoints
│       ├── graph/
│       │   ├── orchestrator.py       ← LangGraph compilation + run_graph()
│       │   ├── nodes.py              ← all 10 graph node implementations
│       │   ├── state.py              ← GraphState TypedDict + AgentResponse
│       │   └── prompts.py            ← system prompt builder + tool schemas
│       ├── memory/
│       │   └── postgres_memory.py    ← rolling-summarization PostgreSQL memory
│       ├── rag/
│       │   ├── embeddings.py         ← Gemini embeddings (768-dim, SDK-based)
│       │   ├── vector_store.py       ← pgvector HNSW + GIN full-text operations
│       │   ├── retriever.py          ← hybrid RRF fusion retriever
│       │   ├── reranker.py           ← Gemini or cross-encoder reranker
│       │   └── ingest.py             ← PDF / DOCX / MD / JSON / image ingestion
│       ├── services/
│       │   ├── gemini_service.py     ← Gemini text, audio, image, TTS client
│       │   ├── hubspot_service.py    ← HubSpot REST v3 (contacts, deals, notes)
│       │   └── email_service.py      ← Resend API + Gmail SMTP escalation emails
│       └── tools/
│           ├── handoff_tool.py       ← escalate_to_human → HubSpot + Email
│           ├── hubspot_tool.py       ← crm_operation dispatcher
│           ├── lead_scoring_tool.py  ← deterministic 4-factor scoring (0–100)
│           ├── messaging_tool.py     ← multi-channel reply delivery
│           └── rag_tool.py           ← search_knowledge_base (lazy LCEL chain)
│
└── data-analytics-assistant/         ← Analytics Assistant
    └── app/
        ├── agents/                   ← 8 specialized AI agents
        │   ├── data_loader.py        ← CSV / Excel / SQL / CRM table loading
        │   ├── profiling.py          ← column statistics + quality scoring
        │   ├── business_analysis.py  ← domain inference (Sales, Finance, HR…)
        │   ├── kpi_discovery.py      ← 6–10 KPIs with formulas + values
        │   ├── insight_generation.py ← 5–8 executive insights with evidence
        │   ├── visualization.py      ← chart type recommendations
        │   ├── report_generator.py   ← full Markdown executive report
        │   └── orchestrator.py       ← conversational follow-up Q&A
        ├── database/
        │   ├── connection.py         ← SQLAlchemy lazy engine + session
        │   ├── models.py             ← ORM models for Analytics tables
        │   └── repository.py         ← CRUD for analyses, KPIs, insights, chat
        ├── graph/
        │   ├── workflow.py           ← LangGraph analytics StateGraph
        │   └── nodes.py              ← node wrappers + conditional routing
        ├── schemas/                  ← Pydantic models (AnalyticsState, KPI, Insight…)
        ├── prompts/                  ← per-agent Gemini prompt templates
        ├── services/
        │   ├── gemini_service.py     ← ChatGoogleGenerativeAI wrapper
        │   ├── dataframe_service.py  ← file loading + schema extraction
        │   ├── statistics_service.py ← column profiling + quality algorithm
        │   ├── sql_source_service.py ← read-only SQL → DataFrame (100k row cap)
        │   └── storage_service.py    ← persistence abstraction layer
        └── ui/
            └── streamlit_app.py      ← 6-tab Streamlit UI (1000+ lines)
```

---

## Shared Database

Both services connect to a single PostgreSQL database (`automark`). No table name conflicts exist.

```
automark database
│
├── CRM tables (created by scripts/init_db.sql)
│   ├── conversations    user_id PK · source · status · summary · messages JSONB
│   ├── leads            user_id PK · name · email · phone · lead_score · hubspot_ids
│   ├── escalations      id PK · user_id FK · reason · priority · status
│   └── document_chunks  id PK · embedding VECTOR(768) · ts_content TSVECTOR · content
│
└── Analytics tables (created by SQLAlchemy on startup)
    ├── sessions         id PK · user_agent · created_at
    ├── analyses         id PK · session_id FK · file_name · business_domain
    ├── kpis             id PK · analysis_id FK · name · formula · priority
    ├── insights         id PK · analysis_id FK · title · type · recommendation
    └── chat_messages    id PK · session_id FK · role · content · timestamp
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — for PostgreSQL
- [Google Gemini API key](https://aistudio.google.com/app/apikey) — required
- Python 3.12

---

## Quick Start

### Docker (everything in one command)

```bash
git clone https://github.com/abdoashraf952/AutoMarkAi.git
cd AutoMarkAi
cp .env.example .env
# Edit .env — fill in GEMINI_API_KEY at minimum

docker-compose up --build
```

| Service | URL |
|---------|-----|
| Analytics UI | http://localhost:8501 |
| CRM API | http://localhost:8000 |
| CRM Docs | http://localhost:8000/docs |
| DB Admin | http://localhost:8000/admin/db/stats |

### Local Development (DB in Docker, apps native)

```bash
# 1. Start database
bash start.sh         # or: docker-compose up db -d

# 2. Terminal 1 — CRM
cd CRM
set PYTHONPATH=..     # Windows CMD  (use export PYTHONPATH=.. on Mac/Linux)
python -m uvicorn main:app --port 8000

# 3. Terminal 2 — Analytics
streamlit run data-analytics-assistant/app/ui/streamlit_app.py --server.port 8501

# 4. Embed knowledge base (first time only)
cd CRM
python -m app.rag.ingest --source ./knowledge_base
```

---

## API Reference (CRM)

### Webhook Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/messenger/webhook` | Meta verification handshake |
| `POST` | `/messenger/webhook` | Messenger messages + Page feed events |
| `GET` | `/facebook/webhook` | Meta verification handshake |
| `POST` | `/facebook/webhook` | Facebook Page comment events |
| `POST` | `/vapi/webhook` | Vapi voice call events |

### Database Admin Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/db/stats` | Row counts + breakdowns for all tables |
| `GET` | `/admin/db/leads` | All leads (filter: temperature, min_score) |
| `GET` | `/admin/db/leads/{user_id}` | Single lead profile |
| `GET` | `/admin/db/conversations` | All conversations (filter: status, source) |
| `GET` | `/admin/db/conversations/{user_id}` | Full conversation + lead + escalations |
| `DELETE` | `/admin/db/conversations/{user_id}` | Delete conversation + related data |
| `GET` | `/admin/db/escalations` | All escalations (filter: status, priority) |
| `PATCH` | `/admin/db/escalations/{id}/close` | Mark escalation as closed |
| `GET` | `/admin/db/chunks` | RAG knowledge-base chunks |
| `DELETE` | `/admin/db/chunks` | Wipe RAG store (re-ingest after) |

Full interactive docs: **http://localhost:8000/docs**

---

## Environment Variables

All variables live in `.env` at the project root.

### Required

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI Studio key |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/automark` |

### CRM — Channels

| Variable | Description |
|----------|-------------|
| `MESSENGER_ACCESS_TOKEN` | Facebook **Page** Access Token (not User token) |
| `MESSENGER_VERIFY_TOKEN` | Webhook verify token (set in Meta App dashboard) |
| `MESSENGER_PAGE_ID` | Your Facebook Page numeric ID |
| `FB_COMMENTS_ACCESS_TOKEN` | Page Access Token for comments |
| `FB_COMMENTS_VERIFY_TOKEN` | Webhook verify token for comments |
| `VAPI_API_KEY` | Vapi voice AI API key |
| `VAPI_WEBHOOK_SECRET` | Vapi webhook HMAC secret |

### CRM — Integrations

| Variable | Description |
|----------|-------------|
| `HUBSPOT_ACCESS_TOKEN` | HubSpot Private App token |
| `RESEND_API_KEY` | Resend.com API key (HTTPS email, no firewall issues) |
| `GMAIL_SENDER` | Gmail sender address (SMTP fallback) |
| `GMAIL_APP_PASSWORD` | Google App Password for SMTP |
| `GMAIL_RECIPIENT` | Who receives handoff alert emails |

### HubSpot Required Scopes

Go to **HubSpot → Settings → Integrations → Private Apps → Scopes**:

`crm.objects.contacts.read` · `crm.objects.contacts.write` · `crm.objects.deals.read` · `crm.objects.deals.write` · `crm.objects.notes.write`

### Meta App Required Permissions

`pages_messaging` · `pages_read_engagement` · `pages_manage_metadata` · `pages_read_user_content`

---

## Knowledge Base

The CRM answers product questions using a RAG pipeline over your knowledge base documents.

**Edit the files in `CRM/knowledge_base/`** with your real business information:

| File | Content |
|------|---------|
| `company_overview.md` | Who you are, what you do |
| `services.md` | Services you offer |
| `pricing.md` | Plans and pricing |
| `faq.md` | Common questions and answers |
| `contact_and_hours.md` | Phone, email, opening hours |
| `process_and_onboarding.md` | How you work with clients |

After editing, re-embed:

```bash
cd CRM
python -m app.rag.ingest --source ./knowledge_base --reset
```

---

## Lead Scoring

The CRM automatically scores every lead from 0–100 using a deterministic formula:

| Factor | Weight | Values |
|--------|--------|--------|
| Budget | 35% | unknown=0 · low=25 · medium=50 · high=75 · very_high=100 |
| Authority | 30% | unknown=0 · influencer=33 · recommender=66 · decision_maker=100 |
| Engagement | 20% | 0–10 scale |
| Interest | 15% | 0–10 scale |

**Temperature thresholds:**
- `cold` — score < 30
- `warm` — score 30–59
- `hot` — score 60–79
- `qualified` — score ≥ 80 → triggers automatic escalation to human

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` on startup | PostgreSQL not running | `docker-compose up db -d` |
| `404 Not Found` on embedding | Wrong embedding model | Set `GEMINI_EMBEDDING_MODEL=models/gemini-embedding-2` |
| `403 Forbidden` on HubSpot | Missing scopes | Add required scopes in HubSpot Private App settings |
| `OAuthException` on Messenger send | User Access Token instead of Page Token | Get Page token via `GET /me/accounts` in Graph API Explorer |
| `SMTP timeout` on email | Port 587/465 blocked | Set `RESEND_API_KEY` in `.env` for HTTPS delivery |
| `ModuleNotFoundError: app` on Analytics | Wrong working directory | Run streamlit from the project root, not from `data-analytics-assistant/` |
