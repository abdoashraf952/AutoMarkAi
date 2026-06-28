# AutoMark AI — ORCAST CRM Agent

> **Stack:** Python 3.12 · FastAPI · LangGraph · Google Gemini 2.5 · PostgreSQL + pgvector · HubSpot · Meta Graph API · Vapi

Part of the **AutoMark AI** unified platform. Both the CRM and the [Data Analytics Assistant](../data-analytics-assistant/README.md) share one PostgreSQL database (`automark`).

---

## What It Does

**ORCAST** (Orchestrated CRM Agent for Sales & Tracking) is an AI-powered conversational sales agent that runs on three channels simultaneously:

| Channel | Behaviour |
|---------|-----------|
| **Facebook Messenger** | Receives text, voice (transcribed), and images (described). Sends text or TTS audio replies. |
| **Facebook Page Comments** | Replies publicly in the comment thread **and** sends a private Messenger DM to start a direct conversation. |
| **Vapi Voice** | Handles live inbound calls. Vapi manages STT/TTS; the agent returns text. |

For every inbound message the agent:

1. Loads conversation memory from PostgreSQL (rolling summarization — history never gets cut off)
2. Classifies intent — CRM lookup, knowledge-base question, lead qualification, escalation, or general chat
3. Routes to the right node — saves leads to HubSpot, searches the knowledge base via hybrid RAG, scores the lead, or escalates to a human
4. Generates a response with Gemini 2.5 Flash using function-calling tools
5. Saves the turn to memory and delivers the reply back to the originating channel

When a conversation is escalated, the agent:
- Creates a HubSpot note on the contact
- Advances the deal stage if the lead is qualified
- **Sends a Gmail notification email** to the configured recipient with full lead details

---

## Database

Tables in the shared `automark` PostgreSQL database written by this service:

| Table | Description |
|-------|-------------|
| `conversations` | Rolling-summary conversation memory per user |
| `leads` | Lead qualification data (name, email, score, temperature, HubSpot IDs) |
| `escalations` | Human-handoff records with reason, priority, open/closed |
| `document_chunks` | RAG knowledge base — pgvector embeddings + full-text index |

The [Data Analytics Assistant](../data-analytics-assistant/README.md) can query these tables directly to analyze CRM performance.

---

## Agent Pipeline (LangGraph)

```
memory_load
  └─► [escalated?]
        ├─► already_escalated → save_memory → END
        └─► intent_classify
              ├─► hubspot_node      → generate_response
              ├─► rag_node          → generate_response
              ├─► lead_scoring_node → [qualified?]
              │     ├─► handoff_node → generate_response
              │     └─► generate_response
              ├─► handoff_node      → generate_response
              └─► generate_response (general)
generate_response → save_memory → messaging_node → END
```

---

## Project Structure

```
CRM/
├── main.py                 ← FastAPI entry point (lifespan: DB init + graph compile)
├── config.py               ← thin redirect → root config.py
├── app/
│   ├── api/
│   │   ├── messenger.py    ← Messenger webhook + send_message_to_commenter()
│   │   ├── facebook_comments.py ← Page Comments webhook
│   │   └── vapi.py         ← Vapi voice webhook + signature verification
│   ├── graph/
│   │   ├── orchestrator.py ← build_graph() + run_graph() entrypoint
│   │   ├── nodes.py        ← all 10 graph node implementations
│   │   ├── state.py        ← GraphState TypedDict + AgentResponse
│   │   └── prompts.py      ← system prompt builder + tool schemas
│   ├── memory/
│   │   └── postgres_memory.py ← rolling-summarization PostgreSQL memory
│   ├── rag/
│   │   ├── embeddings.py   ← Gemini gemini-embedding-2 (768-d, SDK-based)
│   │   ├── vector_store.py ← pgvector dense + GIN sparse operations
│   │   ├── retriever.py    ← hybrid RRF fusion retriever
│   │   ├── reranker.py     ← Gemini or cross-encoder reranking
│   │   └── ingest.py       ← PDF / DOCX / TXT / image ingestion
│   ├── services/
│   │   ├── gemini_service.py   ← Gemini multimodal (text, audio, image, TTS)
│   │   ├── hubspot_service.py  ← HubSpot REST v3 (contacts, deals, notes)
│   │   └── email_service.py    ← Gmail SMTP handoff notifications
│   └── tools/
│       ├── handoff_tool.py     ← escalate_to_human → HubSpot + Gmail
│       ├── hubspot_tool.py     ← crm_operation dispatcher
│       ├── lead_scoring_tool.py← deterministic 4-factor scoring (0–100)
│       ├── messaging_tool.py   ← send_reply (comment reply + Messenger DM)
│       └── rag_tool.py         ← search_knowledge_base (LCEL pipeline)
├── knowledge_base/         ← markdown docs ingested for RAG
└── scripts/
    └── init_db.sql         ← CREATE TABLE / INDEX for all CRM tables
```

---

## Running

> The database must be running first. See the [root start.sh](../start.sh) or the [root README](../README.md).

```bash
# From the AutoMarkAi/ root
docker-compose up db -d

# Then from this directory (AutoMarkAi/CRM/)
PYTHONPATH=.. python -m uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

---

## Knowledge Base → pgvector (RAG Ingestion)

The RAG tool answers customer questions by searching embedded documents stored in the `document_chunks` pgvector table. **The table starts empty — you must run the ingestion before RAG works.**

### Supported file formats

| Format | Extension |
|--------|-----------|
| Markdown | `.md` |
| Plain text | `.txt` |
| PDF | `.pdf` |
| Word document | `.docx` / `.doc` |
| FAQ (JSON array) | `.json` |
| Images | `.png` / `.jpg` / `.jpeg` |

### Step 1 — Add your documents

Place your files inside `CRM/knowledge_base/`. The default files provided are:

```
knowledge_base/
├── company_overview.md      ← who you are
├── contact_and_hours.md     ← phone, email, opening hours
├── faq.md                   ← common questions & answers
├── pricing.md               ← plans and pricing
├── process_and_onboarding.md← how you work with clients
└── services.md              ← services you offer
```

Edit these files with your real business information, or add new files. The agent will only answer from what is in this folder.

### Step 2 — Run the ingestion

From the **`CRM/`** directory with the database running:

```bash
# First time (or after adding new files)
PYTHONPATH=.. python -m app.rag.ingest --source ./knowledge_base

# To re-embed everything from scratch (e.g. after editing files)
PYTHONPATH=.. python -m app.rag.ingest --source ./knowledge_base --reset
```

**Windows (CMD):**
```cmd
set PYTHONPATH=H:\New folder\project\AutoMarkAi
python -m app.rag.ingest --source ./knowledge_base
```

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH = "H:\New folder\project\AutoMarkAi"
python -m app.rag.ingest --source ./knowledge_base
```

Expected output:
```
[info] ingest.file.done   file=company_overview.md    chunks_stored=2
[info] ingest.file.done   file=contact_and_hours.md   chunks_stored=2
[info] ingest.file.done   file=faq.md                 chunks_stored=5
[info] ingest.file.done   file=pricing.md             chunks_stored=3
[info] ingest.file.done   file=process_and_onboarding.md chunks_stored=4
[info] ingest.file.done   file=services.md            chunks_stored=4
[info] ingest.directory.done  files_processed=6  chunks_stored=20  errors=0
```

### Step 3 — Verify in the database

```bash
# From AutoMarkAi/ root
docker-compose exec db psql -U postgres -d automark \
  -c "SELECT source_file, count(*) as chunks FROM document_chunks GROUP BY source_file;"
```

Expected:
```
        source_file        | chunks
---------------------------+--------
 company_overview.md       |      2
 faq.md                    |      5
 pricing.md                |      3
 ...
```

### Ingest a single file

```bash
PYTHONPATH=.. python -m app.rag.ingest --source ./knowledge_base/pricing.md
```

### How it works

```
knowledge_base/*.md
       │
       ▼
  Load & split into chunks (2000 chars, 200 overlap)
       │
       ▼
  Embed with Gemini (models/gemini-embedding-2 → 768 dimensions)
       │
       ▼
  Upsert into document_chunks (pgvector HNSW index + full-text GIN index)
       │
       ▼
  RAG tool: hybrid dense + sparse search → rerank → grounded answer
```

### Embedding model

| Setting | Value |
|---------|-------|
| `GEMINI_EMBEDDING_MODEL` | `models/gemini-embedding-2` |
| Output dimensions | 768 (matches `VECTOR(768)` in the DB schema) |
| Task types | `RETRIEVAL_DOCUMENT` for ingestion, `RETRIEVAL_QUERY` for search |

> If you change `GEMINI_EMBEDDING_MODEL`, you must run `--reset` to re-embed all documents with the new model, otherwise vector dimensions will mismatch.

### Re-ingest after editing files

```bash
# Wipe old vectors and re-embed everything
PYTHONPATH=.. python -m app.rag.ingest --source ./knowledge_base --reset
```

### Via the API (when DEBUG=True)

When the CRM is running with `DEBUG=True`, you can trigger ingestion via HTTP:

```bash
curl -X POST "http://localhost:8000/admin/ingest"

# Force re-embed everything:
curl -X POST "http://localhost:8000/admin/ingest?reset=true"
```

---

## Webhook Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/messenger/webhook` | Meta verification handshake |
| `POST` | `/messenger/webhook` | Messenger DMs + Page feed events |
| `GET` | `/facebook/webhook` | Meta verification handshake |
| `POST` | `/facebook/webhook` | Facebook Page comment events |
| `POST` | `/vapi/webhook` | Vapi voice call events |
| `GET` | `/health` | Health check |

---

## Environment Variables

All loaded from `../. env` (the root unified `.env`) via `config.py`.

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI Studio key |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `MESSENGER_ACCESS_TOKEN` | Yes | Facebook Page access token |
| `MESSENGER_VERIFY_TOKEN` | Yes | Webhook verify token |
| `FB_COMMENTS_ACCESS_TOKEN` | Yes | Facebook comments token |
| `HUBSPOT_ACCESS_TOKEN` | Recommended | HubSpot Private App token |
| `GMAIL_SENDER` | Optional | Gmail address for handoff emails |
| `GMAIL_APP_PASSWORD` | Optional | Google App Password |
| `GMAIL_RECIPIENT` | Optional | Who receives handoff alerts |
| `VAPI_API_KEY` | Optional | Vapi voice integration |
