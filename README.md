# AutoMark AI — Unified Platform

Two services sharing one PostgreSQL database:

| Service | Description | URL |
|---------|-------------|-----|
| **CRM** | ORCAST AI agent — handles Facebook Messenger, Page Comments, and Vapi voice calls. Qualifies leads and syncs to HubSpot. | http://localhost:8000 |
| **Analytics** | Data Analytics Assistant — upload CSV/Excel files or connect a SQL source for AI-powered KPI discovery and insights. | http://localhost:8501 |

Both services read and write to a single **PostgreSQL + pgvector** database (`automark`). CRM tables and Analytics tables live side by side with no name conflicts.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

---

## Quick Start (Docker — recommended)

**1. Clone and configure**

```bash
git clone <repo-url>
cd AutoMarkAi
cp .env.example .env
```

Open `.env` and fill in at minimum:

```env
GEMINI_API_KEY=your_key_here
```

**2. Start all services**

```bash
docker-compose up --build
```

This starts three containers:
- `automark_db` — PostgreSQL 16 with pgvector extension, port 5432
- `automark_crm` — FastAPI CRM agent, port 8000
- `automark_analytics` — Streamlit analytics UI, port 8501

The database schema is created automatically on first run.

**3. Open the apps**

- Analytics UI: http://localhost:8501
- CRM health check: http://localhost:8000/health

**4. Stop everything**

```bash
docker-compose down

# To also delete the database volume (wipes all data):
docker-compose down -v
```

---

## Environment Variables

All configuration lives in `.env` at the project root. Copy `.env.example` as a starting point.

### Shared (both services)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Full PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/automark` |
| `GEMINI_API_KEY` | Google Gemini API key — **required** | — |
| `GEMINI_MODEL` | Primary Gemini model | `gemini-2.5-flash` |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing | `false` |
| `LANGCHAIN_API_KEY` | LangSmith API key (optional) | — |

### CRM only

| Variable | Description |
|----------|-------------|
| `HUBSPOT_ACCESS_TOKEN` | HubSpot Private App token |
| `MESSENGER_VERIFY_TOKEN` | Facebook Messenger webhook verify token |
| `MESSENGER_ACCESS_TOKEN` | Facebook Page access token |
| `VAPI_API_KEY` | Vapi voice AI key |
| `VAPI_WEBHOOK_SECRET` | Vapi webhook HMAC secret |
| `FB_COMMENTS_VERIFY_TOKEN` | Facebook Page Comments verify token |
| `RERANKER_BACKEND` | `gemini` or `cross-encoder` |

### Analytics only

| Variable | Description | Default |
|----------|-------------|---------|
| `UPLOAD_DIR` | Directory for uploaded files | `uploads` |
| `MAX_FILE_SIZE_MB` | Upload size limit | `50` |
| `SQL_SOURCE_MAX_ROWS` | Row cap for SQL sources | `100000` |

---

## Local Development (without Docker)

You need PostgreSQL 16 with the pgvector extension installed locally.

**1. Install PostgreSQL + pgvector**

```bash
# macOS
brew install postgresql@16
brew install pgvector

# Ubuntu/Debian
sudo apt install postgresql-16 postgresql-16-pgvector
```

**2. Create the database**

```bash
psql -U postgres -c "CREATE DATABASE automark;"
psql -U postgres -d automark -f CRM/scripts/init_db.sql
```

**3. Install Python dependencies**

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**4. Run the CRM**

```bash
# From the project root
cd CRM
PYTHONPATH=.. uvicorn main:app --reload --port 8000
```

**5. Run the Analytics Assistant**

```bash
# From the project root
streamlit run "Data Analytics/app/ui/streamlit_app.py" --server.port 8501
```

---

## Project Structure

```
AutoMarkAi/
├── .env                    ← fill in secrets (gitignored)
├── .env.example            ← template — copy to .env
├── docker-compose.yml      ← starts db + crm + analytics
├── Dockerfile              ← single image for both services
├── requirements.txt        ← combined Python dependencies
├── config.py               ← CRM settings (pydantic-settings)
├── main.py                 ← Analytics CLI launcher
│
├── CRM/                    ← CRM Agent (ORCAST)
│   ├── main.py             ← FastAPI entry point
│   ├── app/
│   │   ├── api/            ← Messenger, Facebook, Vapi webhooks
│   │   ├── graph/          ← LangGraph ORCAST orchestrator
│   │   ├── tools/          ← lead scoring, HubSpot, RAG, escalation
│   │   ├── memory/         ← rolling-summarization PostgreSQL memory
│   │   ├── rag/            ← hybrid vector + full-text search
│   │   └── services/       ← Gemini + HubSpot clients
│   ├── knowledge_base/     ← documents ingested for RAG
│   └── scripts/
│       └── init_db.sql     ← PostgreSQL schema (pgvector tables)
│
└── Data Analytics/         ← Analytics Assistant
    └── app/
        ├── agents/         ← 8 AI agents (load, profile, KPI, insight…)
        ├── database/       ← SQLAlchemy models + repository
        ├── graph/          ← LangGraph analytics workflow
        ├── schemas/        ← Pydantic data models
        ├── services/       ← Gemini, dataframe, SQL, storage
        └── ui/
            └── streamlit_app.py  ← 6-tab Streamlit interface
```

---

## Shared Database Tables

Both services write to the **`automark`** database. There are no table name conflicts.

**CRM tables** (created by `CRM/scripts/init_db.sql`):
- `conversations` — rolling-summary memory per user
- `leads` — lead qualification data
- `escalations` — human-handoff records
- `document_chunks` — pgvector RAG store (HNSW + full-text indexes)

**Analytics tables** (created by SQLAlchemy on first startup):
- `sessions` — browser sessions
- `analyses` — uploaded dataset metadata and domain inference
- `kpis` — discovered KPIs per analysis
- `insights` — executive insights per analysis
- `chat_messages` — follow-up conversation history

---

## CRM Webhook Setup

The CRM exposes three webhook endpoints. Register them in your Meta and Vapi dashboards:

| Channel | Method | Path |
|---------|--------|------|
| Facebook Messenger | GET + POST | `/messenger/webhook` |
| Facebook Page Comments | GET + POST | `/facebook/webhook` |
| Vapi Voice | POST | `/vapi/webhook` |

For local development, expose port 8000 via a tunneling tool (e.g. ngrok):

```bash
ngrok http 8000
# Then set the ngrok URL as the webhook in Meta / Vapi dashboards
```
