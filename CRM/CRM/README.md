# AutoMark AI — ORCAST CRM Agent

> **Stack:** Python 3.12 · FastAPI · LangGraph · Google Gemini 2.5 · PostgreSQL + pgvector · HubSpot · Meta Graph API · Vapi

---

## What Is This Project?

**ORCAST** (Orchestrated CRM Agent for Sales & Tracking) is an AI-powered conversational sales agent built on top of **Google Gemini 2.5** and orchestrated by a **LangGraph StateGraph**. It operates across three live channels simultaneously:

| Channel | What it does |
|---|---|
| **Facebook Messenger** | Replies to DMs, supports both text and voice messages |
| **Facebook Page Comments** | Replies publicly to comments on your business Page |
| **Vapi (Phone)** | Handles live inbound voice calls; Vapi manages STT/TTS |

When a customer reaches out on any channel, ORCAST:

1. **Loads conversation memory** from PostgreSQL (rolling-summarization — history never gets cut off)
2. **Classifies the intent** of the message (CRM request, product question, lead signal, escalation, or general chat)
3. **Routes to the right node** — saves contact info to HubSpot, searches the knowledge base, scores the lead, or escalates to a human
4. **Generates a response** using Gemini 2.5 Flash with function-calling tools
5. **Saves the turn** to memory and **delivers the reply** back to the originating channel

Everything is async, fully typed, and production-ready.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CHANNEL ADAPTERS                              │
│  Messenger  ──┐              UnifiedMessage             ┌─ Messenger │
│  FB Comments ─┼─────────────────────────────────────────┼─ FB Comment│
│  Vapi Voice  ─┘  (text / voice→text / image→text)       └─ Vapi text │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                    ORCAST — LangGraph StateGraph                     │
│                                                                      │
│  memory_load → intent_classify                                       │
│     ├─ crm_request     → hubspot_node    ─┐                          │
│     ├─ knowledge_q     → rag_node        ─┤→ generate_response       │
│     ├─ lead_qualify    → lead_scoring ───┤     (Gemini 2.5 Flash)    │
│     ├─ escalation      → handoff_node   ─┘                           │
│     └─ general         ──────────────────→ generate_response         │
│                                            │                         │
│                                       save_memory → messaging_node   │
└──────────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────────┐
│                        SERVICE LAYER                                 │
│  RAG (pgvector hybrid dense + sparse + RRF + rerank)                 │
│  Memory (PostgreSQL rolling-summarization)                           │
│  HubSpot REST API v3 (contacts, deals, notes)                        │
│  LangSmith tracing                                                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## How Each Component Works

### 1. Channel Adapters (`app/api/`)

Each adapter receives a webhook event from the platform, normalises it into a `UnifiedMessage`, and passes it to `run_graph()`. The same `UnifiedMessage` schema works for all three channels.

- **Messenger** (`messenger.py`) — verifies Meta webhook signatures using HMAC-SHA256, handles text and voice (audio) attachments. Voice is transcribed by Gemini before being sent to the graph.
- **Facebook Page Comments** (`facebook_comments.py`) — listens to the `feed` webhook event. Replies are posted as public comment replies. Personal data is never shared publicly.
- **Vapi** (`vapi.py`) — Vapi calls your webhook once per turn with the transcript. ORCAST returns a plain-text reply in the HTTP response body; no outbound call needed.

### 2. ORCAST Graph (`app/graph/`)

The graph is a **LangGraph StateGraph** — a directed graph where each node is an async Python function and all shared data flows through a single `GraphState` TypedDict.

| Node | Responsibility |
|---|---|
| `memory_load` | Loads conversation summary, recent messages, and lead profile from Postgres |
| `intent_classify` | Sends the message to Gemini (temp=0) and gets back a structured JSON intent label + extracted data |
| `hubspot_node` | Calls `crm_operation` to create or update a contact in HubSpot, then updates the lead profile in Postgres |
| `rag_node` | Runs a hybrid vector search, reranks results, generates a grounded answer |
| `lead_scoring_node` | Runs deterministic lead scoring (no LLM); auto-escalates if score ≥ 80 |
| `handoff_node` | Creates a HubSpot note, optionally advances the deal stage, writes an escalation record to Postgres |
| `generate_response` | Gemini 2.5 Flash with function-calling in a tool-call loop (up to `MAX_AGENT_ITERATIONS`) |
| `save_memory` | Appends the user/assistant turn; triggers rolling summarization when `message_count` reaches threshold |
| `messaging_node` | Delivers the response to the right channel; synthesizes speech for Messenger voice turns |

### 3. Tools (`app/tools/`)

Tools are the functions the `generate_response` node can call. They are also called deterministically by dedicated graph nodes before Gemini runs.

| Tool | Function | Description |
|---|---|---|
| `crm_operation` | `hubspot_tool.py` | Thin dispatcher to `hubspot_service`. Supports `create_contact`, `update_contact`, `search_contact`, `get_contact`, `create_deal`, `update_deal`. `create_contact` deduplicates by email/phone before creating. |
| `score_lead` | `lead_scoring_tool.py` | Deterministic formula: budget (35%) + authority (30%) + engagement (20%) + interest (15%). Returns score 0-100 and temperature label. |
| `search_knowledge_base` | `rag_tool.py` | Retrieves chunks from pgvector, reranks with Gemini, generates a grounded answer. Returns `INSUFFICIENT_CONTEXT` sentinel if knowledge base can't answer. |
| `escalate_to_human` | `handoff_tool.py` | Creates a HubSpot note, advances the deal stage if qualified, writes an escalation record, marks conversation as `escalated` in Postgres. |
| `send_reply` | `messaging_tool.py` | Delivers the response; synthesizes Gemini TTS for Messenger voice turns; retries up to 3 times on delivery failure. |

### 4. RAG Pipeline (`app/rag/`)

Documents in `knowledge_base/` are chunked and ingested into PostgreSQL.

- **Dense search**: `text-embedding-004` embeddings stored as `VECTOR(768)`, searched with HNSW cosine index
- **Sparse search**: PostgreSQL `TSVECTOR` full-text search with GIN index
- **Fusion**: Reciprocal Rank Fusion (RRF) merges both result lists
- **Reranking**: Gemini re-scores the fused results (or cross-encoder if `RERANKER_BACKEND=cross-encoder`)
- **Answer generation**: Gemini generates a grounded answer from top-K chunks only; refuses to answer if context is insufficient

Supported document formats: PDF, DOCX, TXT, MD, images (Gemini multimodal ingestion).

### 5. Memory (`app/memory/postgres_memory.py`)

One row per user in the `conversations` table. Messages are stored as a JSONB array. When `message_count` exceeds `SUMMARIZATION_MESSAGE_THRESHOLD`, Gemini summarises the oldest messages, which are then discarded. Only the summary + last N messages are passed to the graph on every turn — giving unbounded history in bounded token cost.

### 6. Lead Scoring Formula

```
Score = (budget × 35%) + (authority × 30%) + (engagement_level × 20%) + (interest_level × 15%)

Temperature thresholds:
  ≥ 80  →  Qualified   — triggers automatic escalation to human
  ≥ 60  →  Hot
  ≥ 30  →  Warm
   < 30  →  Cold
```

| Input | Type | Values |
|---|---|---|
| `budget` | enum | `unknown` / `low` / `medium` / `high` / `very_high` |
| `authority` | enum | `unknown` / `influencer` / `recommender` / `decision_maker` |
| `engagement_level` | integer 0–10 | 0 = never engages, 10 = extremely active |
| `interest_level` | integer 0–10 | 0 = no interest, 10 = ready to buy |

### Design Decisions

| Decision | Rationale |
|---|---|
| LangGraph StateGraph | Deterministic graph wiring; each node is testable in isolation |
| Gemini 2.5 Flash primary / Pro fallback | Cost-efficient primary; Pro for complex reasoning |
| pgvector hybrid RAG (dense + sparse + RRF) | Better recall than pure cosine similarity |
| Rolling summarization memory | Unbounded conversation history in bounded tokens |
| Deterministic lead scoring | Auditable formula, zero LLM hallucination risk |
| Messenger voice → Gemini TTS | Pluggable — swap `synthesize_speech` to change backend |
| Vapi → text passthrough | Vapi handles its own STT/TTS; no backend TTS needed |
| Retry only on 429 + 5xx | 4xx errors (400 Bad Request, 404) will not recover on retry |

---

## Project Structure

```
CRM/
├── .env                          ← secrets (never commit)
├── .env.example                  ← template — copy to .env
├── requirements.txt
├── docker-compose.yml            ← PostgreSQL + pgvector container
├── Dockerfile
├── main.py                       ← FastAPI entry point + admin endpoints
├── config.py                     ← pydantic-settings Settings (all env vars)
├── scripts/
│   └── init_db.sql               ← PostgreSQL schema (auto-run by Docker)
├── knowledge_base/               ← put your company documents here
└── app/
    ├── db.py                     ← shared asyncpg connection pool
    ├── api/
    │   ├── messenger.py          ← Messenger webhook + outbound adapter
    │   ├── facebook_comments.py  ← FB Page Comments webhook + adapter
    │   └── vapi.py               ← Vapi webhook + adapter
    ├── graph/
    │   ├── state.py              ← GraphState TypedDict + AgentResponse model
    │   ├── prompts.py            ← system prompt builder + Gemini tool schemas
    │   ├── nodes.py              ← all LangGraph node functions
    │   └── orchestrator.py       ← build_graph() + run_graph() entrypoint
    ├── tools/
    │   ├── hubspot_tool.py       ← crm_operation dispatcher
    │   ├── lead_scoring_tool.py  ← deterministic scoring formula
    │   ├── rag_tool.py           ← knowledge base search + grounded answer
    │   ├── handoff_tool.py       ← escalation to human agent
    │   └── messaging_tool.py     ← channel-aware reply delivery
    ├── memory/
    │   └── postgres_memory.py    ← rolling-summarization memory layer
    ├── rag/
    │   ├── embeddings.py         ← Gemini text-embedding-004 helpers
    │   ├── vector_store.py       ← pgvector dense + sparse store
    │   ├── retriever.py          ← query expansion + RRF fusion
    │   ├── reranker.py           ← Gemini or cross-encoder reranking
    │   └── ingest.py             ← PDF/DOCX/TXT/MD/image ingestion pipeline
    └── services/
        ├── gemini_service.py     ← multimodal normalisation + text/tool generation
        └── hubspot_service.py    ← HubSpot REST v3 client (httpx + tenacity)
```

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | 3.11 may work but is untested |
| Docker + Docker Compose | latest | for PostgreSQL + pgvector |
| ngrok | 3.x | for local webhook testing only |
| Git | any | |

---

## Step 1 — Get Your API Keys & Tokens

### Google Gemini API Key

1. Open [aistudio.google.com](https://aistudio.google.com)
2. Sign in with a Google account
3. Click **Get API key** → **Create API key in new project** (or select an existing project)
4. Copy the key — it looks like `AIzaSy...`
5. Paste it into `.env` as `GEMINI_API_KEY`

> The free tier gives you 15 req/min on Gemini 2.5 Flash, which is enough for testing.
> For production, enable billing in [console.cloud.google.com](https://console.cloud.google.com).

---

### HubSpot Private App Token

HubSpot private apps replace the older OAuth flow for server-to-server integrations.

1. Log in to [app.hubspot.com](https://app.hubspot.com) (create a free account if needed)
2. Go to **Settings** (gear icon, top-right) → **Integrations** → **Private Apps**
3. Click **Create a private app**
4. Name it (e.g. `AutoMark AI ORCAST`) and add a description
5. Switch to the **Scopes** tab and enable:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.objects.deals.read`
   - `crm.objects.deals.write`
   - `crm.objects.notes.write`
6. Click **Create app** → **Continue creating**
7. On the next screen, click **Show token** and copy it — it starts with `pat-na1-...`
8. Paste it into `.env` as `HUBSPOT_ACCESS_TOKEN`

> The token is shown only once at creation. If you lose it, rotate it from the same Private Apps page.

---

### Meta (Facebook) Tokens — Messenger + Page Comments

You need a **Meta Developer account** and a **Facebook Page** you admin.

#### Create the Meta App

1. Go to [developers.facebook.com](https://developers.facebook.com) → **My Apps** → **Create App**
2. Choose **Business** as the app type → click **Next**
3. Fill in App Name (e.g. `AutoMark AI`) and contact email → **Create App**

#### Get the Page Access Token

4. In your app dashboard, click **Add Product** → find **Messenger** → click **Set Up**
5. Under **Access Tokens** → click **Add or Remove Pages** → connect your Facebook Page
6. After connecting, click **Generate Token** next to your Page
7. Copy the token — this is your `META_ACCESS_TOKEN`

> For production, generate a **System User long-lived token** via Business Manager → System Users. Page tokens expire; system user tokens do not.

#### Get the App Secret

8. Go to **App Settings** → **Basic**
9. Click **Show** next to **App Secret** and copy it → paste as `META_APP_SECRET`

#### Get the Page ID

10. On your Facebook Page, go to **About** → scroll down to **Page ID** (a long number)
11. Copy it → paste as `FACEBOOK_PAGE_ID`

#### Set the Verify Token

12. Choose any random string (e.g. `my_secret_verify_token_2024`) → paste as `META_VERIFY_TOKEN`
    You will enter this same string in the Meta webhook configuration later.

#### Configure Webhooks (after the server is running)

13. In your Meta App dashboard → **Messenger** → **Webhooks** → **Add Callback URL**:
    - Callback URL: `https://your-ngrok-url.ngrok.io/messenger/webhook`
    - Verify Token: the value you set as `META_VERIFY_TOKEN`
14. Subscribe to: `messages`, `messaging_postbacks`
15. For **Page Comments**, add a second webhook under **Webhooks** product:
    - Callback URL: `https://your-ngrok-url.ngrok.io/facebook/webhook`
    - Same verify token
    - Subscribe to: `feed`

---

### Vapi API Key + Webhook Secret

1. Sign up / log in at [dashboard.vapi.ai](https://dashboard.vapi.ai)
2. In the sidebar, go to **Account** → **API Keys** → copy your key → paste as `VAPI_API_KEY`
3. Create an **Assistant** in Vapi and set the **Server URL** (webhook) to:
   `https://your-ngrok-url.ngrok.io/vapi/webhook`
4. In the webhook settings, Vapi lets you set a **Secret** for HMAC verification → choose a random string and paste it as `VAPI_WEBHOOK_SECRET`

---

### LangSmith API Key (optional — for tracing)

LangSmith is optional. Skip this section if you don't need request tracing.

1. Sign up at [smith.langchain.com](https://smith.langchain.com)
2. Go to **Settings** → **API Keys** → **Create API Key**
3. Copy the key → paste as `LANGCHAIN_API_KEY`
4. Set `LANGCHAIN_TRACING_V2=true` in `.env`
5. Set `LANGCHAIN_PROJECT` to any name (e.g. `automark-crm-dev`)

---

## Step 2 — Clone & Install

```bash
# Clone
git clone <your-repo-url>
cd CRM

# Create virtual environment
python -m venv .venv

# Activate — Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Activate — macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 3 — Configure Environment

```bash
# Copy the example file
cp .env.example .env
```

Open `.env` and fill in every value. Minimum required to run:

```env
GEMINI_API_KEY=AIzaSy...
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/automark
HUBSPOT_ACCESS_TOKEN=pat-na1-...
META_VERIFY_TOKEN=your_chosen_verify_token
META_ACCESS_TOKEN=EAAxxxxx...
META_APP_SECRET=abc123...
FACEBOOK_PAGE_ID=123456789
VAPI_API_KEY=vapi_...
VAPI_WEBHOOK_SECRET=your_chosen_secret
```

Optional (leave blank to disable):
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=automark-crm-dev
```

---

## Step 4 — Start PostgreSQL

```bash
# Start PostgreSQL + pgvector in Docker
docker-compose up postgres -d

# Wait ~10 seconds for the container to be healthy, then verify:
docker exec -it automark_postgres psql -U postgres -d automark -c "\dt"
```

You should see four tables: `conversations`, `leads`, `escalations`, `document_chunks`.

The `init_db.sql` script runs automatically on first startup — it creates all tables, HNSW vector indexes, and GIN full-text indexes.

---

## Step 5 — Ingest Your Knowledge Base

Place your company documents (PDF, DOCX, TXT, MD, or images) in the `knowledge_base/` folder.

```bash
# Ingest all documents
python -m app.rag.ingest --source ./knowledge_base

# Re-ingest from scratch (drops existing chunks first)
python -m app.rag.ingest --source ./knowledge_base --reset
```

The ingester chunks documents, generates embeddings with `text-embedding-004`, and stores them in pgvector. You can re-run this at any time when documents change.

---

## Step 6 — Run the Application

### Development mode (with auto-reload and Swagger UI)

```bash
DEBUG=True python main.py
```

The server starts at `http://localhost:8000`.

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### With uvicorn directly

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Production mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

> Keep `--workers 1`. The asyncpg connection pool is in-process and is not shared across worker processes.

### Full Docker Compose (app + postgres)

```bash
docker-compose up --build
```

---

## Step 7 — Expose to the Internet (Webhooks)

Meta and Vapi require a public HTTPS URL to send webhooks to. Use ngrok for local testing:

```bash
ngrok http 8000
```

Copy the `https://xxxxx.ngrok.io` URL. Your webhook endpoints are:

| Platform | Endpoint | Notes |
|---|---|---|
| Messenger | `https://xxxxx.ngrok.io/messenger/webhook` | GET (verify) + POST (events) |
| Facebook Page Comments | `https://xxxxx.ngrok.io/facebook/webhook` | GET (verify) + POST (events) |
| Vapi | `https://xxxxx.ngrok.io/vapi/webhook` | POST only |

Enter the Messenger and Facebook webhook URLs in your Meta App Dashboard (see Step 1).
Enter the Vapi URL in your Vapi Assistant's **Server URL** field.

---

## Step 8 — Verify Everything Works

### Health checks

```bash
# Basic health
curl http://localhost:8000/health

# Deep health (checks Postgres + HubSpot connectivity)
curl http://localhost:8000/health/deep
```

Expected response from `/health/deep`:
```json
{
  "status": "healthy",
  "checks": {
    "postgres": { "status": "ok", "knowledge_base_chunks": 42 },
    "hubspot": { "status": "ok", "http_status": 200 }
  }
}
```

### Verify webhook handshake (Messenger)

```bash
curl "http://localhost:8000/messenger/webhook?hub.mode=subscribe&hub.verify_token=YOUR_VERIFY_TOKEN&hub.challenge=test123"
# Expected: test123
```

### Simulate a conversation (no real webhook needed)

```bash
# General conversation
curl -X POST "http://localhost:8000/admin/simulate?user_id=test_01&source=messenger&content=Hello"

# Product question (triggers RAG)
curl -X POST "http://localhost:8000/admin/simulate?user_id=test_01&source=messenger&content=What+are+your+prices?"

# CRM capture (triggers HubSpot contact creation)
curl -X POST "http://localhost:8000/admin/simulate?user_id=test_02&source=messenger&content=My+name+is+John+Doe,+email+john@example.com"

# Lead qualification (triggers scoring)
curl -X POST "http://localhost:8000/admin/simulate?user_id=test_03&source=messenger&content=I+am+the+CEO+with+a+100k+budget+and+very+interested"

# Escalation request
curl -X POST "http://localhost:8000/admin/simulate?user_id=test_04&source=messenger&content=I+want+to+speak+to+a+human+please"
```

### Inspect memory

```bash
# View a user's conversation memory
curl http://localhost:8000/admin/memory/test_01

# Clear a user's memory
curl -X DELETE http://localhost:8000/admin/memory/test_01

# Manually trigger rolling summarization
curl -X POST http://localhost:8000/admin/summarize/test_01
```

### Ingest via HTTP

```bash
# Ingest knowledge base (DEBUG=True required)
curl -X POST "http://localhost:8000/admin/ingest?reset=false"
```

> All `/admin/` endpoints are only available when `DEBUG=True`.

---

## Environment Variables Reference

### Google Gemini

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | **Required.** API key from Google AI Studio |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Primary model for response generation |
| `GEMINI_MODEL_FALLBACK` | `gemini-2.5-pro` | Fallback for complex reasoning tasks |
| `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` | Embedding model for RAG |
| `GEMINI_TTS_MODEL` | `gemini-2.5-flash-preview-tts` | TTS model for Messenger voice replies |

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/automark` | PostgreSQL connection string |

### HubSpot

| Variable | Default | Description |
|---|---|---|
| `HUBSPOT_ACCESS_TOKEN` | — | **Required.** Private App token |
| `HUBSPOT_BASE_URL` | `https://api.hubapi.com` | HubSpot API base URL (do not change) |

### Meta (Facebook)

| Variable | Description |
|---|---|
| `META_VERIFY_TOKEN` | **Required.** Any random string; must match the value you enter in Meta webhook config |
| `META_ACCESS_TOKEN` | **Required.** Page Access Token (or System User token) |
| `META_APP_SECRET` | **Required.** App Secret from Meta App Settings → Basic; used for webhook signature verification |
| `FACEBOOK_PAGE_ID` | **Required.** Numeric Page ID; prevents the agent from replying to its own posts |

### Vapi

| Variable | Description |
|---|---|
| `VAPI_API_KEY` | **Required.** API key from dashboard.vapi.ai |
| `VAPI_WEBHOOK_SECRET` | **Required.** Secret for HMAC-SHA256 webhook signature verification |

### LangSmith (optional)

| Variable | Default | Description |
|---|---|---|
| `LANGCHAIN_TRACING_V2` | `false` | Set to `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | — | LangSmith API key |
| `LANGCHAIN_PROJECT` | `automark-ai` | Project name in LangSmith |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` | LangSmith endpoint (do not change) |

### RAG Tuning

| Variable | Default | Description |
|---|---|---|
| `RAG_TOP_K` | `5` | Number of chunks returned after reranking |
| `RAG_SIMILARITY_THRESHOLD` | `0.30` | Minimum cosine similarity to include a chunk |
| `RERANKER_BACKEND` | `gemini` | `gemini` or `cross-encoder` (cross-encoder requires `sentence-transformers`) |
| `KNOWLEDGE_BASE_PATH` | `./knowledge_base` | Directory scanned by the ingestion pipeline |

### Memory Tuning

| Variable | Default | Description |
|---|---|---|
| `MAX_CONVERSATION_HISTORY` | `20` | Recent messages passed to the graph context |
| `SUMMARIZATION_MESSAGE_THRESHOLD` | `20` | Message count that triggers rolling summarization |

### Application

| Variable | Default | Description |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | Uvicorn bind host |
| `APP_PORT` | `8000` | Uvicorn bind port |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DEBUG` | `False` | Enables Swagger UI, ReDoc, and all `/admin/` endpoints |
| `MAX_AGENT_ITERATIONS` | `6` | Max Gemini tool-call loop iterations per message |

---

## Database Schema

Four tables are created automatically by `scripts/init_db.sql`:

| Table | Purpose |
|---|---|
| `conversations` | One row per user — stores `summary`, `messages` (JSONB), `message_count`, channel `source`, and `status` (`active` / `escalated`) |
| `leads` | One row per user — stores progressively collected lead data: `name`, `email`, `phone`, `budget`, `authority`, `engagement_level`, `interest_level`, `lead_score`, `lead_temperature`, `hubspot_contact_id`, `hubspot_deal_id` |
| `escalations` | Append-only log of every human-handoff event with `reason`, `priority`, `status`, and `hubspot_note_id` |
| `document_chunks` | RAG vector store — `content`, `embedding` (VECTOR(768)), `ts_content` (TSVECTOR), `source_file`, `chunk_index` |

---

## Testing

```bash
# Run unit tests
pytest tests/ -v

# Verify all modules import cleanly
python -c "from app.graph.orchestrator import compiled_graph; print('Graph OK')"
python -c "from main import app; print('App OK')"

# Print the compiled graph structure (Mermaid)
python -c "from app.graph.orchestrator import compiled_graph; print(compiled_graph.get_graph().draw_mermaid())"
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `startup.postgres_error` on launch | Make sure Docker is running: `docker-compose up postgres -d` |
| `401 Unauthorized` from HubSpot | Token expired or missing a required scope — regenerate it in Private Apps settings |
| Messenger webhook verification fails | `META_VERIFY_TOKEN` in `.env` must exactly match what you entered in the Meta dashboard |
| Vapi webhook returns 401 | `VAPI_WEBHOOK_SECRET` must match the secret configured in your Vapi assistant |
| Knowledge base returns no results | Run ingestion first: `python -m app.rag.ingest --source ./knowledge_base` |
| `pgvector` extension not found | Use the `pgvector/pgvector:pg16` Docker image — it includes the extension |
| `Too many workers` warning | Keep `--workers 1`; the asyncpg pool is not fork-safe |

---

*AutoMark AI — ORCAST CRM Agent · Powered by Google Gemini + LangGraph + pgvector*
