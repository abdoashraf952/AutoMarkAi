# AutoMark AI — Unified Platform

Two services sharing one PostgreSQL database:

| Service | Description | URL |
|---------|-------------|-----|
| **CRM** | ORCAST AI agent — qualifies leads via Facebook Messenger, Page Comments, and Vapi voice calls. Escalates to humans via Gmail + HubSpot. | http://localhost:8000 |
| **Analytics** | Data Analytics Assistant — upload CSV/Excel files or connect a SQL source for AI-powered KPI discovery and insights. | http://localhost:8501 |

Both services read and write to a single **PostgreSQL + pgvector** database (`automark`). CRM tables and Analytics tables live side by side with no name conflicts.

---

## What the CRM Does

### Channels
| Channel | Inbound | Outbound |
|---------|---------|----------|
| Facebook Messenger | Text, voice (transcribed), images (described) | Text reply or TTS audio |
| Facebook Page Comments | Top-level post comments | Public comment reply **+ private Messenger DM** |
| Vapi Voice | Transcribed speech | Text returned to Vapi for TTS |

### AI Pipeline (ORCAST)
Each inbound message runs through a LangGraph graph:

```
Load memory → Classify intent → Route
  ├── CRM / HubSpot lookup
  ├── RAG knowledge base search
  ├── Lead scoring
  ├── Human escalation
  └── General conversation
→ Generate response → Save memory → Deliver reply
```

### Human Handoff
When the AI escalates a conversation to a human agent, it automatically:
1. Creates an escalation record in PostgreSQL
2. Creates a HubSpot note on the contact (if a HubSpot contact ID is known)
3. Advances the HubSpot deal stage if the lead is qualified
4. **Sends a Gmail notification email** to your configured address with full lead details

### Facebook Comment → Messenger DM
When someone comments on a Facebook Page post, the AI:
1. Replies to the comment publicly in the post thread
2. **Also sends the reply as a private Messenger DM** to open a direct conversation with the commenter

This converts public engagement into private, trackable conversations automatically.

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
| `LANGCHAIN_PROJECT` | LangSmith project name | `automark-ai` |

### CRM — Channels

| Variable | Description |
|----------|-------------|
| `MESSENGER_VERIFY_TOKEN` | Webhook verify token set in your Meta App |
| `MESSENGER_ACCESS_TOKEN` | Facebook Page access token |
| `MESSENGER_APP_SECRET` | Meta App secret (for request signing) |
| `MESSENGER_PAGE_ID` | Your Facebook Page ID |
| `FB_COMMENTS_VERIFY_TOKEN` | Webhook verify token for Page Comments |
| `FB_COMMENTS_ACCESS_TOKEN` | Page access token for commenting |
| `FB_COMMENTS_APP_SECRET` | Meta App secret for Comments app |
| `FB_COMMENTS_PAGE_ID` | Your Facebook Page ID |
| `VAPI_API_KEY` | Vapi voice AI API key |
| `VAPI_WEBHOOK_SECRET` | Vapi webhook HMAC secret |

### CRM — Integrations

| Variable | Description |
|----------|-------------|
| `HUBSPOT_ACCESS_TOKEN` | HubSpot Private App token |
| `HUBSPOT_BASE_URL` | HubSpot API base (default: `https://api.hubapi.com`) |

### CRM — Gmail Handoff Emails

When a conversation is escalated to a human, a notification email is sent automatically.

| Variable | Description |
|----------|-------------|
| `GMAIL_SENDER` | Gmail address used to send notifications (e.g. `bot@gmail.com`) |
| `GMAIL_APP_PASSWORD` | Google App Password — **not** your regular password. Generate at: Google Account → Security → 2-Step Verification → App passwords |
| `GMAIL_RECIPIENT` | Email address that receives handoff alerts (e.g. `team@yourcompany.com`) |

> If any of the three Gmail variables are empty, the email step is silently skipped. The escalation still saves to the database and HubSpot normally.

### CRM — AI & RAG

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_MODEL_FALLBACK` | Fallback Gemini model | `gemini-2.5-pro` |
| `GEMINI_EMBEDDING_MODEL` | Embedding model for RAG | `models/text-embedding-004` |
| `GEMINI_TTS_MODEL` | TTS model for voice replies | `gemini-2.5-flash-preview-tts` |
| `RERANKER_BACKEND` | `gemini` or `cross-encoder` | `gemini` |
| `RAG_TOP_K` | Number of RAG chunks to retrieve | `5` |
| `RAG_SIMILARITY_THRESHOLD` | Minimum similarity score | `0.30` |
| `KNOWLEDGE_BASE_PATH` | Path to knowledge base documents | `./knowledge_base` |
| `MAX_CONVERSATION_HISTORY` | Messages kept in memory | `20` |
| `MAX_AGENT_ITERATIONS` | Max LangGraph steps per turn | `6` |

### Analytics only

| Variable | Description | Default |
|----------|-------------|---------|
| `UPLOAD_DIR` | Directory for uploaded files | `uploads` |
| `MAX_FILE_SIZE_MB` | Upload size limit | `50` |
| `SQL_SOURCE_MAX_ROWS` | Row cap for SQL sources | `100000` |
| `SQL_SOURCE_TIMEOUT_MS` | SQL query timeout | `30000` |

---

## Local Development (without Docker)

> **The database must be running before either app starts.** The easiest way is to start just the PostgreSQL container from Docker Compose, then run the apps natively.

### Option A — DB in Docker, apps native (recommended for dev)

```bash
# 1. Start only the database container (stays running in background)
docker-compose up db -d

# 2. Install Python dependencies (once)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Run the CRM (in one terminal, from project root)
cd CRM
PYTHONPATH=.. uvicorn main:app --reload --port 8000

# 4. Run the Analytics Assistant (in another terminal, from project root)
cd ..   # back to AutoMarkAi/
streamlit run data-analytics-assistant/app/ui/streamlit_app.py --server.port 8501

# 5. Stop the database when done
docker-compose down db
```

### Option B — Full local PostgreSQL install

You need PostgreSQL 16 with the pgvector extension installed.

```bash
# macOS
brew install postgresql@16 pgvector

# Ubuntu/Debian
sudo apt install postgresql-16 postgresql-16-pgvector

# Windows (WSL)
sudo apt install postgresql postgresql-contrib
# pgvector must be built from source on WSL — see https://github.com/pgvector/pgvector
```

Once PostgreSQL is running:

```bash
# Create the shared database and schema
psql -U postgres -c "CREATE DATABASE automark;"
psql -U postgres -d automark -f CRM/scripts/init_db.sql

# Install deps
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# CRM (terminal 1, from project root)
cd CRM && PYTHONPATH=.. uvicorn main:app --reload --port 8000

# Analytics (terminal 2, from project root)
streamlit run data-analytics-assistant/app/ui/streamlit_app.py --server.port 8501
```

### Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` on CRM start | PostgreSQL not running | Run `docker-compose up db -d` first |
| `role "postgres" does not exist` | Wrong DB user | Check `DB_USER` in `.env` |
| `database "automark" does not exist` | Schema not initialised | Run `psql -U postgres -f CRM/scripts/init_db.sql` |
| Streamlit `ModuleNotFoundError: app` | Wrong working directory | Run streamlit from project root, not from `Data Analytics/` |

---

## Project Structure

```
AutoMarkAi/
├── .env                              ← fill in secrets (gitignored)
├── .env.example                      ← template — copy to .env
├── config.py                         ← unified settings (pydantic-settings)
├── docker-compose.yml                ← starts db + crm + analytics
├── Dockerfile                        ← single image for both services
├── requirements.txt                  ← combined Python dependencies
├── start.sh                          ← local dev launcher (starts DB first)
│
├── shared/                           ← cross-project utilities
│   ├── crm_models.py                 ← SQLAlchemy models for CRM tables (read-only)
│   └── crm_reader.py                 ← load CRM tables as DataFrames for Analytics
│
├── CRM/                              ← CRM Agent (ORCAST)
│   ├── __init__.py
│   ├── main.py                       ← FastAPI entry point
│   ├── config.py                     ← thin redirect → root config.py
│   ├── app/
│   │   ├── api/
│   │   │   ├── messenger.py          ← Messenger webhook + DM sender
│   │   │   ├── facebook_comments.py  ← Page Comments webhook
│   │   │   └── vapi.py               ← Vapi voice webhook
│   │   ├── graph/                    ← LangGraph ORCAST orchestrator
│   │   ├── tools/
│   │   │   ├── handoff_tool.py       ← escalation → HubSpot + Gmail
│   │   │   ├── hubspot_tool.py       ← CRM operations
│   │   │   ├── lead_scoring_tool.py
│   │   │   ├── messaging_tool.py     ← reply delivery (comment + DM)
│   │   │   └── rag_tool.py           ← knowledge base search
│   │   ├── memory/                   ← rolling-summarization memory
│   │   ├── rag/                      ← hybrid vector + full-text search
│   │   └── services/
│   │       ├── email_service.py      ← Gmail handoff notifications
│   │       ├── gemini_service.py     ← Gemini multimodal client
│   │       └── hubspot_service.py    ← HubSpot REST client
│   ├── knowledge_base/               ← documents ingested for RAG
│   └── scripts/
│       └── init_db.sql               ← PostgreSQL schema (pgvector tables)
│
└── data-analytics-assistant/         ← Analytics Assistant
    ├── __init__.py
    └── app/
        ├── agents/                   ← 8 AI agents (load, profile, KPI, insight…)
        ├── database/                 ← SQLAlchemy models + repository
        ├── graph/                    ← LangGraph analytics workflow
        ├── schemas/                  ← Pydantic data models
        ├── services/                 ← Gemini, dataframe, SQL, storage
        └── ui/
            └── streamlit_app.py      ← 6-tab Streamlit UI + CRM data loader
```

---

## Shared Database Tables

Both services write to the **`automark`** database. There are no table name conflicts.

**CRM tables** (created by `CRM/scripts/init_db.sql` on first DB start):
- `conversations` — rolling-summary memory per user
- `leads` — lead qualification data (name, email, score, temperature)
- `escalations` — human-handoff records with priority and status
- `document_chunks` — pgvector RAG store (HNSW cosine + full-text GIN indexes)

**Analytics tables** (created by SQLAlchemy on first Streamlit load):
- `sessions` — browser sessions
- `analyses` — uploaded dataset metadata and domain inference
- `kpis` — discovered KPIs per analysis
- `insights` — executive insights per analysis
- `chat_messages` — follow-up conversation history

---

## CRM Webhook Setup

Register these endpoints in your Meta App and Vapi dashboards:

| Channel | Method | Path |
|---------|--------|------|
| Facebook Messenger | GET + POST | `/messenger/webhook` |
| Facebook Page Comments | GET + POST | `/facebook/webhook` |
| Vapi Voice | POST | `/vapi/webhook` |

For local development, expose port 8000 via a tunnel:

```bash
ngrok http 8000
# Use the ngrok HTTPS URL as the webhook base in Meta / Vapi dashboards
```

### Meta App Permissions Required

| Permission | Used for |
|------------|----------|
| `pages_messaging` | Send Messenger replies and private DMs to commenters |
| `pages_read_engagement` | Read Page comments via webhook |
| `pages_manage_metadata` | Subscribe to webhook events |
| `pages_read_user_content` | Access comment content |

### Setting Up Gmail App Password

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** (required)
3. Under "How you sign in to Google", click **App passwords**
4. Create a new app password — select "Mail" and your device
5. Copy the 16-character code into `GMAIL_APP_PASSWORD` in `.env`

> Use a dedicated Gmail account for sending, not your personal one.

---

## Analytics — Supported Data Sources

| Source | Formats |
|--------|---------|
| File upload | CSV, XLSX, XLS (up to `MAX_FILE_SIZE_MB`) |
| SQL database | Any SQLAlchemy-compatible database via connection string |

The Analytics pipeline runs 8 AI agents in sequence: data loading → statistical profiling → business domain inference → KPI discovery → insight generation → visualization recommendations → report generation → conversational follow-up.
