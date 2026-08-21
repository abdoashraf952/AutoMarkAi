<div align="center">

# AutoMark AI

**A unified AI platform for real-estate marketing — one API, one database, one login.**

Conversational CRM · Autonomous Meta ad campaigns · Executive data analytics

`Python 3.12` · `FastAPI` · `LangGraph` · `Google Gemini` · `PostgreSQL + pgvector` · `Next.js 14`

</div>

---

## Contents

| | Section | |
|---|---|---|
| **1** | [Overview](#1-overview) | What it is, architecture, tech stack |
| **2** | [Quick start](#2-quick-start) | Run it in five minutes |
| **3** | [Credentials & API keys](#3-credentials--api-keys) | **How to obtain every key in `.env`** |
| **4** | [Configuration reference](#4-configuration-reference) | Every environment variable |
| **5** | [Architecture](#5-architecture) | Layout, URL map, database, models |
| **6** | [CRM module](#6-crm-module) | ORCAST conversational sales agent |
| **7** | [Campaigns module](#7-campaigns-module) | 19-agent Meta ad pipeline |
| **8** | [Analytics module](#8-analytics-module) | Dataset → executive report |
| **9** | [Frontend](#9-frontend) | Next.js app |
| **10** | [Operations](#10-operations) | Tests, health, logs, troubleshooting |
| **11** | [Known gaps](#11-known-gaps) | Read before deploying |

---

## 1. Overview

AutoMark AI is three production modules sharing one FastAPI application, one
PostgreSQL database, one JWT identity, and one model provider.

| Module | What it does |
|---|---|
| **CRM** | **ORCAST** (Orchestrated CRM Agent for Sales & Tracking) — a conversational real-estate sales agent running on Facebook Messenger, Facebook Page comments, and Vapi voice simultaneously. Qualifies and scores leads, keeps rolling-summary memory, answers from a hybrid RAG knowledge base, syncs to HubSpot, escalates to humans. |
| **Campaigns** | An autonomous multi-agent system that builds, launches, and manages real-estate ad campaigns on Meta — from a few photos and a short conversation. Researches the market, writes the copy, plans budget and audience, enforces Meta's HOUSING rules, publishes, then keeps optimising. |
| **Analytics** | Turns raw data into executive insight in minutes. Upload a CSV/Excel file — or analyse the CRM's own tables — and get statistical profiling, business-domain inference, KPI discovery, evidence-backed insights, chart recommendations, and a downloadable executive report. |

### Architecture at a glance

```
                    ┌──────────────────────────────────────────────────────────┐
   Next.js 14       │                  FastAPI  ·  src/main.py                 │
   frontend/        │                                                          │
        │           │   /messenger  /facebook  /vapi   ← CRM webhooks (Meta/Vapi)
        │  REST/SSE │   /api/auth        ← shared JWT identity                 │
        ├──────────►│   /api/crm         ← CRM admin + database browsing       │
        │           │   /api/campaigns   ← sessions, HITL gates, publish       │
        │           │   /api/analytics   ← upload, analyze, charts, chat       │
        │           │                                                          │
        │           │   ┌────────────┐  ┌────────────┐  ┌──────────────────┐   │
        │           │   │ CRM agent  │  │ Campaign   │  │ Analytics        │   │
        │           │   │ LangGraph  │  │ LangGraph  │  │ LangGraph        │   │
        │           │   │ 10 nodes   │  │ 19 agents  │  │ 8 agents         │   │
        │           │   └─────┬──────┘  └─────┬──────┘  └────────┬─────────┘   │
        │           │         └───────────────┼──────────────────┘             │
        │           │                         ▼                                │
        │           │        src/shared/  db.py · models.py · auth.py          │
        └───────────┴─────────────────────────┬────────────────────────────────┘
                                              ▼
                    ┌─────────────────────────────────────────────┐
                    │  PostgreSQL 16 + pgvector — ONE database    │
                    │  12 tables · init_all() · HNSW + GIN index  │
                    └─────────────────────────────────────────────┘
                                              │
              ┌───────────────┬───────────────┼───────────────┬───────────────┐
              ▼               ▼               ▼               ▼               ▼
         Google Gemini    HubSpot      Meta Marketing      Vapi          Resend
       text·vision·image    CRM        API + Ad Library    voice          email
```

### Tech stack

| Layer | Technology |
|---|---|
| **Agent orchestration** | LangGraph — StateGraph, interrupts, checkpointers, parallel `Send` fan-out |
| **Backend API** | FastAPI + Uvicorn, Server-Sent Events for streaming progress |
| **LLM** | Google Gemini — text, vision, image generation, embeddings (single provider) |
| **Database** | PostgreSQL 16 + pgvector — SQLAlchemy 2.0 (async + sync engines) |
| **Ad platform** | Meta Marketing API via `facebook_business` SDK + Meta Ad Library API |
| **CRM** | HubSpot REST v3 — contacts, deals, notes |
| **Voice** | Vapi (STT/TTS handled platform-side) |
| **Auth** | Email/password — `bcrypt` hashing + `PyJWT` HS256 tokens |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Framer Motion |
| **Languages** | English + Egyptian Arabic (full RTL support) |

---

## 2. Quick start

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12 | 3.11 also works |
| Node.js | 18+ | For the frontend |
| PostgreSQL | 14+ | **Must have the `pgvector` extension** |
| Gemini API key | — | The only mandatory credential ([§3.1](#31-google-gemini--required)) |

Everything else is optional — the app starts and runs without HubSpot, Meta,
Vapi, or email configured. Those integrations degrade gracefully with a warning.

### Option A — Docker (recommended)

```bash
git clone <your-repo-url> && cd AutoMarkAi
cp docker/.env.example docker/.env
# Edit docker/.env: set GEMINI_API_KEY and JWT_SECRET (see §3)

docker compose -f docker/docker-compose.yml up --build
```

`docker/.env` is self-contained: it holds every key for every module (§4),
*plus* the four variables `docker-compose.yml` substitutes directly —
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `NEXT_PUBLIC_API_BASE` —
because Compose auto-loads a `.env` colocated with the compose file for its
own `${VAR}` interpolation. Nothing is left to an inline fallback default;
`docker/.env.example` declares every value the Dockerfile and compose file
touch, so there is nothing to hunt for elsewhere. It is gitignored; only
`docker/.env.example` is committed.

| Service | URL |
|---|---|
| API + interactive docs | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| PostgreSQL | `localhost:5432` |

### Option B — Local

```bash
# 1. PostgreSQL with pgvector — via the "db" service in docker-compose.yml
#    (reads docker/.env for POSTGRES_USER/PASSWORD/DB; §3.2 has a plain
#    `docker run` alternative if you don't want docker-compose involved)
docker compose -f docker/docker-compose.yml up db -d

# 2. Backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # then edit it — see §3
python -m uvicorn src.main:app --reload --port 8000

# 3. Frontend (second terminal)
cd frontend && npm install && npm run dev
```

The schema is created automatically on first boot. **There is no migration
script to run.**

### Verifying the install

```bash
curl http://localhost:8000/health          # {"status":"healthy","version":"4.0.0"}
curl http://localhost:8000/health/deep     # checks PostgreSQL + HubSpot
```

A healthy startup logs:

```
startup.database_ok
startup.crm_graph_compiled
startup.campaign_scheduler_ok
automark.ready
```

---

## 3. Credentials & API keys

This section covers **how to obtain every value in `.env`**.

### What you actually need

| Credential | Required? | Enables | Cost |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | All AI — every module | Free tier available |
| `DATABASE_URL` | **Yes** | Persistence | Free (local/Docker) |
| `JWT_SECRET` | **Yes** | Login | Free (self-generated) |
| Meta credentials | For real ads | Publishing campaigns | Ad spend only |
| Messenger / Page tokens | For CRM chat | Messenger + comments channels | Free |
| `HUBSPOT_ACCESS_TOKEN` | Recommended | Lead sync to CRM | Free tier available |
| `RESEND_API_KEY` *or* Gmail | Recommended | Handoff escalation email | Free tier available |
| `VAPI_API_KEY` | Optional | Voice calls | Paid |
| `LANGCHAIN_API_KEY` | Optional | Tracing/debugging | Free tier available |

> **Minimum viable setup:** a Gemini key, a local PostgreSQL, and a generated
> `JWT_SECRET`. With `META_SIMULATION_MODE=true` you can run the entire campaign
> pipeline end to end — realistic fake Meta responses, no ad account needed.

---

### 3.1 Google Gemini — *required*

Powers every LLM call in all three modules: text, vision, image generation, and
RAG embeddings.

1. Go to **[aistudio.google.com/apikey](https://aistudio.google.com/apikey)**
2. Sign in with a Google account
3. Click **Create API key** → select an existing Google Cloud project or let it create one
4. Copy the key (starts with `AIza…`)

```ini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=models/text-embedding-004
```

> **Note on the free tier.** It is rate-limited per minute and per day. The
> analytics pipeline makes ~7 sequential calls per run and the campaign pipeline
> considerably more, so a long run can hit the limit. If you see `429` errors,
> either wait or enable billing in Google Cloud for the project.

> **Embedding dimension.** `EMBEDDING_DIM=768` must match the `VECTOR(768)`
> column in `document_chunks`. The embeddings module forces
> `outputDimensionality=768`. Changing one without the other breaks RAG.

---

### 3.2 PostgreSQL — *required*

The database **must have the `pgvector` extension** — the CRM knowledge base
uses a `VECTOR(768)` column with an HNSW index.

**Easiest — via docker-compose.yml's `db` service** (extension pre-installed,
reads `docker/.env`, health-checked):

```bash
docker compose -f docker/docker-compose.yml up db -d
```

**Standalone container**, if you don't want docker-compose involved:

```bash
docker run -d --name automark_db -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=automark pgvector/pgvector:pg16
```

> Pick one — both bind port 5432 and the name `automark_db`, so running one
> while the other already exists fails with a container-name conflict.
> `docker rm -f automark_db` clears the way to switch between them (safe only
> if that container's data doesn't matter — check with `docker exec
> automark_db psql -U postgres -d automark -c "\dt"` first).

**Existing PostgreSQL install:** install pgvector
([github.com/pgvector/pgvector](https://github.com/pgvector/pgvector#installation)),
then:

```sql
CREATE DATABASE automark;
\c automark
CREATE EXTENSION IF NOT EXISTS vector;
```

```ini
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/automark
```

The app creates the extension itself on startup if the role has permission, so
the manual `CREATE EXTENSION` is usually unnecessary.

---

### 3.3 JWT secret — *required*

Signs login tokens. **Never ship the default.**

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```ini
JWT_SECRET=<paste the generated value>
JWT_EXPIRE_HOURS=168
```

Changing this invalidates every existing session — all users must log in again.

---

### 3.4 Meta — Facebook & Instagram

Meta credentials serve **two independent purposes** in this project:

| Purpose | Module | Needs |
|---|---|---|
| Publishing ad campaigns | Campaigns | Ad account, Marketing API, `ads_management` |
| Receiving messages & comments | CRM | Page tokens, Messenger product, webhooks |

You can use one Meta app for both, or two separate apps.

#### Step 1 — Create the app

1. Go to **[developers.facebook.com/apps](https://developers.facebook.com/apps)** → **Create App**
2. Choose the **Business** app type
3. From the dashboard, add the products you need:
   - **Marketing API** — for publishing campaigns
   - **Messenger** — for the CRM Messenger channel
   - **Webhooks** — for both Messenger and Page comments

#### Step 2 — App ID and App Secret

**Settings → Basic** in the app dashboard.

```ini
META_APP_ID=<App ID>
META_APP_SECRET=<App Secret — click "Show">
MESSENGER_APP_SECRET=<same App Secret, if using one app>
FB_COMMENTS_APP_SECRET=<same App Secret, if using one app>
```

> `META_APP_ID` is **required** when `META_SIMULATION_MODE=false` —
> `FacebookAdsApi.init()` will not authenticate without it, and it must pair
> with the matching `META_APP_SECRET`.

#### Step 3 — Ad Account ID

Open **[adsmanager.facebook.com](https://adsmanager.facebook.com)**. The account
selector shows `act_123456789012345`.

```ini
META_AD_ACCOUNT_ID=123456789012345     # numeric only — no "act_" prefix
```

#### Step 4 — Page ID

Your Facebook Page → **About → Page transparency**, or Page **Settings**.

```ini
META_PAGE_ID=<numeric Page ID>
MESSENGER_PAGE_ID=<same Page ID>
FB_COMMENTS_PAGE_ID=<same Page ID>
```

#### Step 5 — Access tokens

**For development** — [Graph API Explorer](https://developers.facebook.com/tools/explorer/):
select your app, request permissions, click **Generate Access Token**. These are
short-lived (1–2 hours) and are fine for testing only.

**For anything lasting** — use a **System User token**, which does not expire:

1. **[business.facebook.com/settings](https://business.facebook.com/settings)** → **Users → System Users**
2. **Add** → create a system user with the **Admin** role
3. **Add Assets** → assign your Ad Account *and* your Page, with full control
4. **Generate New Token** → select your app → tick the permissions below → generate

**Permissions required:**

| Permission | Needed for |
|---|---|
| `ads_management` | Creating campaigns, ad sets, creatives, ads |
| `ads_read` | Insights for the operate loop; Ad Library competitor research |
| `pages_manage_posts` | Organic Page posts; uploading photos to the Page |
| `pages_read_engagement` | Reading Page comments |
| `pages_messaging` | Sending and receiving Messenger DMs |
| `business_management` | System-user asset access |

```ini
META_ACCESS_TOKEN=<system user token>
META_AD_LIBRARY_TOKEN=<same token — needs ads_read>
MESSENGER_ACCESS_TOKEN=<Page access token>
FB_COMMENTS_ACCESS_TOKEN=<Page access token>
```

> **Page tokens vs User tokens.** Page writes (organic posts, photo uploads,
> Messenger sends) must use a **Page Access Token**, not the user/system token.
> Get one from **App dashboard → Messenger → Settings → Access Tokens →**
> select your Page → **Generate Token**.

#### Step 6 — Webhooks (CRM channels)

The verify token is **a string you invent** — Meta echoes it back during the
handshake and the app compares it. Any random string works:

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

```ini
MESSENGER_VERIFY_TOKEN=<your invented string>
FB_COMMENTS_VERIFY_TOKEN=<your invented string>
```

Then in **App dashboard → Webhooks**:

| Field | Value |
|---|---|
| Callback URL | `https://YOUR_DOMAIN/messenger/webhook` |
| Verify Token | the string above |
| Subscribe to fields | `messages`, `messaging_postbacks`, `feed` |

Subscribe the app to your Page under **Messenger → Settings → Webhooks →
Add Subscriptions**.

`feed` delivers Page comment events; the CRM filters for
`field=feed, item=comment, verb=add`.

> **Local testing.** Meta requires a public HTTPS URL. Use a tunnel:
> ```bash
> ngrok http 8000
> # then use https://<id>.ngrok-free.app/messenger/webhook as the callback URL
> ```

#### Step 7 — App Review

While your app is in **Development mode**, tokens only work for users with a
role on the app. To serve real customers, submit the permissions above for
**App Review** and switch the app to **Live**.

---

### 3.5 HubSpot

Syncs qualified leads to contacts and deals, and writes escalation notes.

1. **[app.hubspot.com](https://app.hubspot.com)** → **Settings** (gear icon)
2. **Integrations → Private Apps** → **Create a private app**
3. Name it, then open the **Scopes** tab and enable **all five**:

```
crm.objects.contacts.read
crm.objects.contacts.write
crm.objects.deals.read
crm.objects.deals.write
crm.objects.notes.write
```

4. **Create app** → copy the access token (starts with `pat-`)

```ini
HUBSPOT_ACCESS_TOKEN=pat-...
HUBSPOT_BASE_URL=https://api.hubapi.com
```

**Verify it:**

```bash
curl http://localhost:8000/api/crm/hubspot/check
```

A missing scope returns `403` with the exact list to enable. Scope changes take
effect immediately — no restart needed.

---

### 3.6 Vapi — voice calls

1. **[dashboard.vapi.ai](https://dashboard.vapi.ai)** → sign up
2. **API Keys** → copy your private key
3. Create an assistant and set its **Server URL** to `https://YOUR_DOMAIN/vapi/webhook`
4. Set a **Server URL Secret** — Vapi sends it as the `X-Vapi-Secret` header

```ini
VAPI_API_KEY=<private key>
VAPI_WEBHOOK_SECRET=<the server URL secret>
```

This is the one webhook in the project that **does** verify its secret
(constant-time comparison). If `VAPI_WEBHOOK_SECRET` is unset, verification is
skipped and a warning is logged.

---

### 3.7 Email — handoff escalation alerts

When a lead is escalated, the agent emails the full lead detail and conversation
summary. Delivery is attempted in order: **Resend → Gmail 587 → Gmail 465 →
local JSON file**.

#### Option A — Resend (recommended)

Works over HTTPS 443, so corporate firewalls that block SMTP are not a problem.

1. **[resend.com](https://resend.com)** → sign up
2. **API Keys → Create API Key** → copy (starts with `re_`)
3. **Domains** → add and verify your sending domain (DNS records)

```ini
RESEND_API_KEY=re_...
GMAIL_SENDER=alerts@your-verified-domain.com
GMAIL_RECIPIENT=sales-team@your-company.com
```

> **Gotcha:** `GMAIL_SENDER` is used as the **From address for Resend too**, not
> only for Gmail. It must be on a domain you have verified in Resend, or Resend
> rejects the send. For testing without a domain, use `onboarding@resend.dev`.

#### Option B — Gmail SMTP

Requires 2-Step Verification on the Google account.

1. **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**
2. Create an app password (16 characters) — this is **not** your account password

```ini
GMAIL_SENDER=you@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
GMAIL_RECIPIENT=sales-team@your-company.com
```

If every strategy fails, the alert is written to `handoffs/` as JSON so an
escalation is never silently lost.

---

### 3.8 LangSmith — tracing *(optional)*

Records every LangGraph run for inspection — invaluable when debugging a
19-agent pipeline.

1. **[smith.langchain.com](https://smith.langchain.com)** → **Settings → API Keys**
2. Create a key (starts with `lsv2_`)

```ini
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=automark
```

---

### Security checklist

- [ ] `JWT_SECRET` is generated, not the shipped default
- [ ] `.env` and `docker/.env` are gitignored — confirm with `git check-ignore -v .env docker/.env`
- [ ] `META_SIMULATION_MODE=true` until you intend to spend real ad budget
- [ ] `DEBUG=false` in production (`DEBUG=true` opens CORS to `*` and exposes admin routes)
- [ ] `CORS_ORIGINS` lists only your real frontend origin
- [ ] Meta webhooks are behind signature verification ([§11](#11-known-gaps))
- [ ] `/api/crm/admin/*` is firewalled or reverse-proxied — **these routes are unauthenticated**
- [ ] Tokens rotated if they were ever pasted into a chat, ticket, or screenshot

---

## 4. Configuration reference

Everything is read through `src/config.py` — never `os.environ` directly.
Copy `.env.example` to `.env`; it documents every variable in the same grouping.

### Shared

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/automark` | The one database |
| `DB_ECHO` | `false` | Log every SQL statement |
| `JWT_SECRET` | *dev default* | **Change it** |
| `JWT_EXPIRE_HOURS` | `168` | Token lifetime (7 days) |
| `GEMINI_API_KEY` | — | Required |
| `GEMINI_MODEL` | `gemini-2.0-flash` | CRM + analytics model |
| `GEMINI_MODEL_FALLBACK` | — | Secondary model tried if the primary errors |
| `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` | RAG embeddings |
| `GEMINI_TTS_MODEL` | — | Text-to-speech for Messenger voice replies |
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` / `LANGCHAIN_PROJECT` | — | LangSmith credentials |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` | Override for self-hosted LangSmith |
| `APP_HOST` / `APP_PORT` | `0.0.0.0` / `8000` | Bind address |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `console` | `console` or `json` |
| `DEBUG` | `false` | Opens CORS to `*`, exposes admin routes |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated; ignored when `DEBUG=true` |

### CRM

| Variable | Default | Purpose |
|---|---|---|
| `HUBSPOT_ACCESS_TOKEN` | — | Private app token |
| `MESSENGER_*` / `FB_COMMENTS_*` | — | `VERIFY_TOKEN`, `ACCESS_TOKEN`, `APP_SECRET`, `PAGE_ID` |
| `VAPI_API_KEY` / `VAPI_WEBHOOK_SECRET` | — | Voice channel |
| `RERANKER_BACKEND` | `gemini` | `gemini` or `cross-encoder` |
| `RAG_TOP_K` | `5` | Chunks passed to the model |
| `RAG_SIMILARITY_THRESHOLD` | `0.30` | Minimum fused score |
| `EMBEDDING_DIM` | `768` | Must match `VECTOR(768)` |
| `KNOWLEDGE_BASE_PATH` | `src/crm/knowledge_base` | Ingestion source |
| `MAX_CONVERSATION_HISTORY` | `20` | Turns kept verbatim |
| `SUMMARIZATION_MESSAGE_THRESHOLD` | `20` | Turns before summarisation |
| `MAX_AGENT_ITERATIONS` | `6` | Tool-calling loop cap per message |
| `GMAIL_*` / `RESEND_API_KEY` | — | Handoff email |

### Campaigns

| Variable | Default | Purpose |
|---|---|---|
| `META_SIMULATION_MODE` | `true` | **`false` = real ads, real money** |
| `META_ACCESS_TOKEN` | — | System user or user token |
| `META_APP_ID` / `META_APP_SECRET` | — | Required when simulation is off |
| `META_AD_ACCOUNT_ID` | — | Numeric, no `act_` prefix |
| `META_PAGE_ID` | — | Creatives and organic posts |
| `META_AD_LIBRARY_TOKEN` | — | Competitor research; falls back to `META_ACCESS_TOKEN` |
| `MAKE_SPONSORED_PAUSED_AD` | `true` | Create the paid ad (paused) |
| `MAKE_ORGANIC_POST` | `false` | Also post organically to the Page |
| `MIN_QUESTIONS` / `MAX_QUESTIONS` | `3` / `6` | Interview bounds |
| `ENABLE_FOLLOW_UPS` | `true` | LLM follow-up questions |
| `NUM_GENERATED_IMAGES` | `4` | Images per generation |
| `MAX_REGENERATIONS_ALLOWED` | `3` | Creative retry cap |
| `ENABLE_WEB_SEARCH` | `false` | Strategist live trends (DuckDuckGo) |
| `AGENT_LOGGING` | `false` | Per-agent I/O logs to `.agent_logs/` |
| `LIFECYCLE_DIAGNOSIS_HOUR` | `9` | UTC hour for the daily diagnosis |

### Analytics

| Variable | Default | Purpose |
|---|---|---|
| `UPLOAD_DIR` | `./uploads` | Where datasets land |
| `MAX_UPLOAD_MB` | `200` | Upload size cap |
| `ANALYTICS_ROW_SAMPLE` | `10000` | Row cap when loading a CRM table |

### Docker Compose only

Read from `docker/.env`, not the repo-root `.env`. Compose auto-loads a
`.env` colocated with `docker-compose.yml` for its own `${VAR}`
interpolation, and these four are what it substitutes:

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER` | `postgres` | The `db` service's superuser |
| `POSTGRES_PASSWORD` | `postgres` | **Change it for anything beyond local dev** |
| `POSTGRES_DB` | `automark` | Database name — also feeds the `DATABASE_URL` Compose builds for the `api`/`analytics` containers |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Baked into the `web` container at build time — must be reachable from the **browser**, not from inside the Docker network |

### Database URL precedence

`DATABASE_URL` is canonical. The campaign module's legacy `POSTGRES_URL` is
still honoured, but **only when `DATABASE_URL` is left at its default** — so a
stale alias can never silently redirect a configured database. Inside Docker,
Compose overrides `DATABASE_URL` for you from the `POSTGRES_*` variables
above, pointed at the `db` service rather than `localhost`.

---

## 5. Architecture

### Repository layout

```
AutoMarkAi/
├── README.md                   this file
├── requirements.txt            all three modules' dependencies
├── pytest.ini · conftest.py    test config; repo root on sys.path
├── .env.example
│
├── src/
│   ├── main.py                 THE FastAPI app — mounts every module
│   ├── config.py               THE settings object
│   │
│   ├── shared/
│   │   ├── db.py               engines, sessions, init_all()
│   │   ├── models.py           all 12 tables, one SQLAlchemy Base
│   │   ├── auth.py             bcrypt + JWT, app-wide identity
│   │   ├── crm_reader.py       CRM tables → pandas, for Analytics
│   │   └── log_visualizer.py
│   │
│   ├── crm/
│   │   ├── api/                messenger · facebook_comments · vapi · admin
│   │   ├── graph/              orchestrator · nodes · state · prompts
│   │   ├── memory/             postgres_memory.py
│   │   ├── rag/                embeddings · vector_store · retriever
│   │   │                       reranker · ingest
│   │   ├── services/           gemini · hubspot · email
│   │   ├── tools/              handoff · hubspot · lead_scoring
│   │   │                       messaging · rag
│   │   └── knowledge_base/     real-estate markdown corpus
│   │
│   ├── campaigns/
│   │   ├── api.py              sessions, HITL gates, publish
│   │   ├── pipeline_graph.py   the full LangGraph topology
│   │   ├── graph.py            simpler graph for the CLI path
│   │   ├── state.py            CampaignState (shared blackboard)
│   │   ├── llm_client.py       Gemini text + vision + image generation
│   │   ├── meta_client.py      Meta Marketing API (Simulated + Real)
│   │   ├── agent_logger.py     wraps each node, logs I/O
│   │   ├── i18n.py             English / Arabic prompt selection
│   │   ├── real_estate_utils.py · strategy_tools.py
│   │   ├── nodes/              the 19 agent nodes
│   │   ├── compliance/ policy/ prompts/ templates/ memory/
│   │   └── workers/scheduler.py    operate-loop cadence
│   │
│   └── analytics/
│       ├── api.py              REST + SSE interface
│       ├── agents/             8 pipeline agents
│       ├── graph/              workflow.py · nodes.py
│       ├── schemas/            state · dataset · kpi · insight · chat
│       ├── services/           gemini · dataframe · statistics
│       │                       sql_source · storage
│       ├── database/repository.py
│       ├── memory/checkpoint.py
│       └── ui/streamlit_app.py     optional internal UI
│
├── frontend/                   Next.js 14
├── docker/                     Dockerfile · docker-compose.yml · architecture.mmd
├── tests/                      crm/ · campaigns/ · analytics/
└── uploads/                    shared upload directory
```

### URL map

The backend is one FastAPI app. Modules are mounted under prefixes — **except
the CRM webhooks, which keep their original un-prefixed paths** because those
URLs are registered in the Meta and Vapi dashboards.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET`/`POST` | `/messenger/webhook` | ⚠️ none | Meta handshake · Messenger DMs + Page feed |
| `GET`/`POST` | `/facebook/webhook` | ⚠️ none | Meta handshake · Page comment events |
| `POST` | `/vapi/webhook`, `/webhook/vapi` | secret | Vapi voice events |
| `POST` | `/api/auth/register`, `/api/auth/login` | — | Returns a JWT |
| `GET`/`DELETE`/`PATCH` | `/api/crm/admin/db/*` | ⚠️ none | Stats, leads, conversations, escalations, chunks |
| `GET` | `/api/crm/hubspot/check` | none | Connectivity + scope diagnosis |
| `POST`/`GET` | `/api/campaigns/session/*` | JWT | Sessions, HITL gates, publish, operate |
| `GET` | `/api/campaigns/users/me/campaigns` | JWT | The caller's campaigns |
| `POST`/`GET` | `/api/analytics/sessions/*` | JWT | Upload, analyze, stream, result, charts, chat |
| `GET` | `/api/analytics/analyses` | JWT | The caller's past analyses |
| `GET` | `/health`, `/health/deep`, `/docs` | none | Operations |

⚠️ = see [Known gaps](#11-known-gaps).

### One database, one init

All 12 tables are declared on a single SQLAlchemy `Base` in `src/shared/models.py`:

| Group | Tables |
|---|---|
| identity | `users` |
| crm | `conversations`, `leads`, `escalations`, `document_chunks` |
| campaigns | `campaigns` |
| analytics | `sessions`, `analyses`, `kpis`, `insights`, `chat_messages`, `session_snapshots` |

`src/shared/db.py` exposes the only schema entry point:

```python
await init_all()      # CREATE EXTENSION vector, then create all 12 tables
```

It runs from the app lifespan on startup, is idempotent, and is the only place
in the project that creates schema. `init_all_sync()` is the blocking variant
for CLI tools and Streamlit.

**Two engines, one database** — the modules differ in concurrency model, not
in storage:

| Engine | Driver | Used by |
|---|---|---|
| `async_engine` | asyncpg | CRM agent — webhooks, RAG retrieval, conversation memory |
| `sync_engine` | psycopg2 | Campaign pipeline and analytics agents (LangGraph nodes and pandas both block) |

`document_chunks` keeps its pgvector `VECTOR(768)` column, a stored generated
`tsvector`, an HNSW cosine index (`m=16, ef_construction=64`), and a GIN
full-text index — all declared in the model, so `create_all()` emits exactly
the DDL the original hand-written `init_db.sql` did.

**Inspecting data:**

```bash
docker exec -it automark_db psql -U postgres -d automark
\dt
SELECT email, created_at FROM users;
SELECT compound_name, status, meta_campaign_id FROM campaigns;
SELECT source_file, count(*) FROM document_chunks GROUP BY source_file;
```

### Models

**Every LLM call runs on Gemini** — text, vision, image generation, and
embeddings. One API key to manage.

| Purpose | Model | Where |
|---|---|---|
| Campaign text generation | `gemini-2.5-flash` | `campaigns/llm_client.py` → `call_llm()` |
| Cheap/fast tier (summaries) | `gemini-2.5-flash-lite` | `call_llm(..., fast=True)` |
| Image understanding | `gemini-2.5-flash` | `call_llm_vision()` |
| Ad image generation | `gemini-3.1-flash-image` | `generate_ad_images()` |
| CRM + analytics agents | `GEMINI_MODEL` | `crm/services/gemini_service.py` |
| RAG embeddings (768-d) | `GEMINI_EMBEDDING_MODEL` | `crm/rag/embeddings.py` |

The campaign module previously supported Groq as an alternative text provider
via `LLM_PROVIDER`. That has been removed — Gemini already handled vision and
image generation, so a second provider added only another key to manage and a
text-only model that could not read an ad photo. `LLM_PROVIDER` and
`GROQ_API_KEY` are no longer read; if an old `.env` still sets `LLM_PROVIDER` to
anything but `gemini`, the app logs a warning at startup and uses Gemini anyway.

`call_llm()` still returns a `(text, provider)` tuple so existing `llm_used`
bookkeeping keeps working; `provider` is always `"gemini"`. The module also
includes resilient JSON parsing, since LLMs sometimes wrap output in markdown
fences.

### Auth

One account works everywhere. `POST /api/auth/register` and `/api/auth/login`
return a JWT (bcrypt-hashed passwords, HS256, 7-day expiry); send it as
`Authorization: Bearer <token>`.

Analytics sessions carry a `user_id`, so each user only sees their own analyses.
The column is nullable, so rows created before auth existed survive.

`EventSource` cannot set headers, so the two SSE progress streams also accept
`?token=<jwt>`. Every other endpoint requires the header.

---

## 6. CRM module

### Channels

| Channel | Behaviour |
|---|---|
| **Facebook Messenger** | Receives text, voice (transcribed), and images (described). Sends text or TTS audio replies. |
| **Facebook Page Comments** | Replies publicly in the comment thread **and** sends a private Messenger DM to start a direct conversation. |
| **Vapi Voice** | Handles live inbound calls. Vapi manages STT/TTS; the agent returns text. |

**Language:** the agent **always replies in Arabic (العربية)** regardless of the
customer's input language, on all three channels. The rule lives in the system
prompt in `src/crm/graph/prompts.py`. To revert to auto-detect, replace the
`## Language Rule` block with:

```
Detect the language of the user's latest message and ALWAYS reply in that
same language. Never mix languages in a single response.
```

### Per-message flow

1. Load conversation memory from PostgreSQL (rolling summarization)
2. Classify intent — CRM lookup, knowledge-base question, lead qualification, escalation, or general chat
3. Route to the right node — save to HubSpot, search the knowledge base via hybrid RAG, score the lead, or escalate
4. Generate a response with Gemini using function-calling tools
5. Save the turn to memory and deliver the reply back to the originating channel

### Agent pipeline

```
memory_load
  └─► [escalated?]
        ├─► already_escalated → save_memory → messaging_node → END
        └─► intent_classify
              ├─► hubspot_node      → generate_response
              ├─► rag_node          → generate_response
              ├─► lead_scoring_node → [qualified?]
              │     ├─► handoff_node → generate_response
              │     └─► generate_response
              ├─► handoff_node      → generate_response
              └─► generate_response (general)
generate_response → save_memory → messaging_node → END (reply in Arabic)
```

### Lead scoring

Deterministic, 0–100, no LLM:

| Factor | Weight | Values |
|---|---|---|
| Budget | 35% | unknown=0 · low=25 · medium=50 · high=75 · very_high=100 |
| Authority | 30% | unknown=0 · influencer=33 · recommender=66 · decision_maker=100 |
| Engagement | 20% | 0–10 scale (×10) |
| Interest | 15% | 0–10 scale (×10) |

**Temperature bands:** `cold` < 30 · `warm` 30–59 · `hot` 60–79 ·
`qualified` ≥ 80 → triggers automatic handoff to a human.

### Escalation

The agent creates a HubSpot note on the contact, advances the deal stage if the
lead is qualified, and emails the full lead detail plus conversation summary.
Delivery order: **Resend API → Gmail SMTP 587 → Gmail SMTP 465 → local JSON in
`handoffs/`**, so an escalation is never silently lost.

### RAG knowledge base

Documents are chunked, embedded (768-d), and stored in `document_chunks` with
both a dense HNSW vector index and a sparse GIN full-text index. Retrieval fuses
both with **Reciprocal Rank Fusion**, then optionally reranks (Gemini or a
cross-encoder, per `RERANKER_BACKEND`).

**Supported formats:** `.md`, `.txt`, `.pdf`, `.docx`/`.doc`, `.json` (FAQ
arrays), `.png`/`.jpg`/`.jpeg`.

`src/crm/knowledge_base/` ships with Egyptian-market real-estate content:
company overview, villas, apartments, compounds and projects, townhouses and
twins, payment plans and financing, locations and areas, a 30+ Q&A buyer FAQ,
pricing, services, onboarding process, general FAQ, and contact hours.

**Ingest after editing:**

```bash
# add new files only
python -m src.crm.rag.ingest --source ./src/crm/knowledge_base

# re-embed everything from scratch
python -m src.crm.rag.ingest --source ./src/crm/knowledge_base --reset

# or, when DEBUG=true
curl -X POST "http://localhost:8000/api/crm/ingest?reset=true"
```

---

## 7. Campaigns module

A developer, brokerage, or agent creates a professional, HOUSING-compliant Meta
campaign in under two minutes with no marketing experience: chat with **"Mark"**,
upload real unit photos, answer a handful of questions, and a squad of
specialised agents researches the market, writes the copy, plans the budget and
audience, enforces Meta's rules, and publishes.

### The 19 agents, in 6 squads

<details open>
<summary><b>🗣️ Discovery — understand the client</b></summary>

| Node | Role |
|---|---|
| `target_gen_node` | Analyses the unit photos and suggests ranked campaign goals, one recommended |
| `target_ask_node` ⏸ | Pauses for the user to pick the goal |
| `question_gen_node` ⇄ | Adaptive interview: fixed questions (compound, location, unit types, delivery status, price, offer, lead destination, duration) plus LLM follow-ups only when an answer is vague |
| `question_ask_node` ⏸ | Pauses to collect each answer |
| `summarizer_node` | Compresses the conversation into a `rolling_summary`, recalls long-term memory about a returning client |

</details>

<details open>
<summary><b>🔍 Research — understand the market</b></summary>

| Node | Role |
|---|---|
| `audience_node` | Builds a HOUSING-compliant audience: geo-radius around the project city, age 18–65, all genders, broad delivery, price-tier profile |
| `competitor_node` | Pulls live competitor ads from the **Meta Ad Library API** (curated samples in simulation mode) — hooks, offers, formats, run duration |
| `trend_node` | Egypt's seasonal demand windows (post-Eid, back-to-school, year-end) and payday timing |

</details>

<details open>
<summary><b>🧠 Planning — decide the strategy</b></summary>

| Node | Role |
|---|---|
| `orchestrator_node` | The planner. Gemini vision over the photos plus all answers → `campaign_plan` (product type, platform, objective, tone, price tier) |
| `strategy_node` | The Strategist: target persona, channel split, messaging angles, timezone-aware posting schedule (timing computed deterministically, not hallucinated) |

</details>

<details open>
<summary><b>🎨 Creative & media — build the ad</b></summary>

| Node | Role |
|---|---|
| `creative_node` | Multiple ad copies, headlines, and a CTA. **Attaches the user's real unit photos** — no AI-generated people, a hard site-wide rule |
| `media_buying_node` | Budget split across Facebook/Instagram, bid strategy, optimisation goal, estimated reach, daily budget — then hard-overrides any targeting that would break HOUSING |

</details>

<details open>
<summary><b>✅ Review & assembly — human checks + finalise</b></summary>

| Node | Role |
|---|---|
| `photo_select_node` ⏸ | User chooses which uploaded photos go in the ad |
| `text_review_node` ⏸ | User picks and edits the final copy + headline |
| `merge_node` | Pure Python, no LLM. Validates and assembles the `campaign_bundle` — copy ≤125 chars, 3 headlines, CTA coherence, budget-split normalisation, final HOUSING audience override |
| `compliance_node` | The legal gate. Validates against Meta HOUSING rules from a per-market JSON file. Failure blocks publishing |

</details>

<details open>
<summary><b>📈 Operate — manage the live campaign</b></summary>

| Node | Role |
|---|---|
| `diagnose_node` | Reads metrics (real Meta Insights, or synthetic in sim mode) → cost-per-lead, lead quality, ad frequency, learning state, plain-language diagnosis |
| `decision_node` ⏸ | Pure decision function over metrics + price-tier thresholds: hold, scale up/down, pause, refresh creative, take/hand-back manual control. Pauses for approval before any money-moving action |
| `act_node` | Executes the approved decision via the Meta client, records the outcome in the audit log |

</details>

### Graph topology

```
                     ┌────────── route_operate (entry router) ──────────┐
              (discovery/build)                                    (operate)
                     ▼                                                 ▼
        ┌─────────────────────────┐                        ┌────────────────────┐
START → │  target_gen_node        │                        │   diagnose_node    │
        │  target_ask_node  ⏸     │ ← pick campaign goal    │        ↓           │
        │  question_gen_node ⇄    │                        │   decision_node ⏸  │ ← approve
        │  question_ask_node ⏸    │ ← interview loop        │        ↓           │
        │  summarizer_node        │                        │   act_node         │
        └───────────┬─────────────┘                        └─────────┬──────────┘
                    ▼                                                ▼
        ┌─────────────────────────┐                                 END
        │  audience_node          │   RESEARCH
        │  competitor_node        │
        │  trend_node             │
        └───────────┬─────────────┘
                    ▼
        ┌─────────────────────────┐
        │  orchestrator_node      │   PLAN (vision → campaign_plan)
        │  strategy_node          │   STRATEGIST
        └───────────┬─────────────┘
                    ▼  (parallel fan-out)
          ┌─────────┴──────────┐
          ▼                    ▼
  ┌───────────────┐   ┌─────────────────┐
  │ creative_node │   │ media_buying_   │
  │     ↓         │   │ node            │
  │ photo_select⏸ │   └────────┬────────┘
  │     ↓         │            │
  │ text_review⏸  │            │
  └───────┬───────┘            │
          └──────────┬─────────┘
                     ▼
             ┌───────────────┐
             │  merge_node   │   (assemble campaign_bundle)
             └───────┬───────┘
                     ▼
             ┌───────────────┐
             │ compliance_   │   (HOUSING gate)
             │ node          │
             └───────┬───────┘
                     ▼
                    END  →  (user publishes → campaign_phase becomes "operate")

   ⏸ = human-in-the-loop pause    ⇄ = loop until interview done
```

- **Parallel fan-out.** After the Strategist, Creative and Media-buying run at
  the same time (LangGraph `Send`) — neither depends on the other. They
  reconverge at `merge_node`.
- **Two entry points, one graph.** `route_operate` decides on every invocation
  whether this is a new build (start at Discovery) or a live-campaign check-in
  (jump straight to Operate).

### The Supervisor

`nodes/supervisor.py` is a **pure router** — it never calls an LLM or an
external API. It reads shared state and returns the name of the next agent:
`route_operate` (build vs operate), `route_after_orchestrator` (proceed only if
a plan exists), `route_to_subagents` (fan out to Creative + Media),
`route_after_text_review` (loop back to Creative on rejection, else Merge).

### Human-in-the-loop

LangGraph's `interrupt()` pauses the whole graph, sends a question to the
frontend, and resumes from that exact point when the user answers — no work is
repeated. Five gates:

| Gate | Agent | What the user does |
|---|---|---|
| `campaign_target` | `target_ask_node` | Picks the campaign goal |
| `questions` | `question_ask_node` | Answers each interview question |
| `photo_select` | `photo_select_node` | Chooses which photos to use |
| `text_review` | `text_review_node` | Picks and edits the ad copy |
| `approval` | `decision_node` | Approves a money-moving operate action |

**Approval modes:** **Full Manual** (every gate — what the web app uses),
**Guided** (routine choices auto-picked; creative and money decisions still
pause), **Autopilot** (unattended build; only publishing needs the user).

Expensive or irreversible actions never sit inside an interrupting node —
generation happens in non-interrupting nodes and the interrupt only collects a
decision, so pausing and resuming is always safe and never double-charges.

### Campaign lifecycle

**Discovery** (gather the brief) → **Build** (research, plan, create, validate,
assemble) → **Publish** (real Meta IDs saved) → **Operate** (the scheduler
re-enters the graph to diagnose and optimise).

The background scheduler (`workers/scheduler.py`) wakes on a cadence and
re-invokes the graph for any live campaign:

| Sweep | Production | Demo |
|---|---|---|
| Metrics refresh | every 6 h | every 5 min |
| Diagnosis | every 24 h, only at `LIFECYCLE_DIAGNOSIS_HOUR` UTC | every 10 min, no hour check |
| Timer | every 15 min | every 1 min |

> The app currently starts the scheduler with `demo_mode=True` hardcoded in
> `campaigns/api.py` → `start_scheduler()`, so the **demo** column is what runs.
> Change that argument to `False` for production cadences.

### Compliance is defence-in-depth

Real-estate ads fall under Meta's **HOUSING Special Ad Category**, which
prohibits targeting by age, gender, detailed demographics, or interests, and
bans discriminatory copy. Violations get campaigns rejected or accounts banned.
The same rule is enforced at five independent layers:

1. **Prompt level** — Creative and Media-buying prompts instruct the LLM on HOUSING rules
2. **Media-buying override** — hard-sets age 18–65, all genders, removes income targeting
3. **Merge override** — re-applies the HOUSING audience even over the Strategist's persona
4. **Compliance agent** — an explicit gate that can block publishing
5. **Meta client declaration** — declares `special_ad_categories: ["HOUSING"]` on the API call

If any layer is bypassed, the next catches it. The result is surfaced to the user.

### Shared state

All nodes communicate through one `CampaignState` TypedDict (a blackboard).

```
START state      q_generator adds   orchestrator adds  sub-agents add     review adds      merge adds
──────────────   ────────────────   ─────────────────  ───────────────    ─────────────    ──────────────
image_path    →  questions       →  campaign_plan   →  creative_output →  review_stage  →  campaign_bundle
image_mode       user_answers       llm_used           media_output       feedback
budget           errors             errors             llm_used
goal                                                   errors
```

Two reducers make parallel fan-out safe:
`errors: Annotated[list, operator.add]` concatenates rather than overwrites, and
`llm_used: Annotated[dict, _merge_dicts]` merges rather than overwrites.

### Three kinds of memory

| Type | What it holds | Where |
|---|---|---|
| **Working memory** | The current campaign's `CampaignState` | LangGraph checkpointer (Postgres / SQLite / in-memory) |
| **Business records** | User accounts + every campaign with its Meta IDs and full plan | `users`, `campaigns` tables |
| **Long-term client memory** | Summaries of a returning client's past campaigns | `rolling_summary` + `.client_memory/` |

> Graph checkpoints persist to the shared PostgreSQL database
> (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes` — created
> automatically on first use, same `DATABASE_URL` as everything else) as
> long as `langgraph-checkpoint-postgres` is installed — it's in
> `requirements.txt`, so a normal `pip install -r requirements.txt` covers
> it. Without that package it falls back to a SQLite file
> (`.automark_checkpoints.sqlite`), and only falls further back to
> in-memory (lost on restart) if that fails too. Startup logs which one is
> active: `Checkpointer: PostgresSaver`, `SqliteSaver → ...`, or
> `MemorySaver (in-memory, lost on restart)`.

### Simulation vs live

| | `META_SIMULATION_MODE=true` | `META_SIMULATION_MODE=false` |
|---|---|---|
| Meta API calls | Faked, no real ads | Real campaigns created (paused) |
| Competitor research | Curated synthetic data | Live Meta Ad Library |
| Operate-loop metrics | Synthetic | Real Meta Insights |
| Meta credentials | Not required | Required |
| Use for | Demos, development, testing | Production launches |

Gemini is **always** called for real in both modes — only the Meta side is
simulated.

### Using it

1. Landing page → **Create my real estate campaign**
2. Sign up / log in
3. Chat with Mark: language → upload unit photos → optional brochure/floor-plans/logo → budget → campaign goal → short interview
4. Review: select photos, pick and edit the ad copy + headline
5. Publish to Meta (created **paused** for safety), or preview in simulation mode
6. **My Campaigns** → every saved campaign as a card; click for Meta IDs, audience, creative, strategy

---

## 8. Analytics module

Upload a CSV or Excel file — or point it at a CRM table — and get statistical
profiling, business-domain inference, 6–10 KPIs with formulas and current
values, 5–8 evidence-backed insights with recommendations, chart
recommendations with live previews, and a downloadable Markdown executive
report.

### Agent pipeline

```
data_loader → profiling → business_analysis → kpi_discovery
           → insight_generation → visualization → report_generator → END

Follow-up path:
data_loader → chat_orchestrator → END
```

Any node can route to `error_handler`, which preserves the message and ends
cleanly rather than throwing.

### Data sources

| Source | Details |
|---|---|
| File upload | CSV, XLSX, XLS — up to `MAX_UPLOAD_MB` (default 200) |
| SQL database | Any SQLAlchemy-compatible DB via connection string (SELECT-only, 100k row cap) |
| CRM database | Direct load of `leads`, `conversations`, `escalations` |

**The CRM tables are analysable directly.** Because everything shares one
database, the sidebar lists the CRM tables; picking one runs the full pipeline
over live CRM data with no export step. Powered by `src/shared/crm_reader.py`.

### The six tabs

| Tab | Content |
|---|---|
| **Overview** | Stat tiles (rows, columns, quality, duplicates), profiling narrative, quality issues, per-column profile table |
| **KPIs** | Priority-sorted cards with definition, formula, current value, required columns; filter by category |
| **Insights** | Priority-sorted cards with summary, evidence, recommendation, business impact; filter by type |
| **Visualizations** | Live charts rendered from your data, plus the full recommendation table |
| **Report** | Full Markdown executive report with a download button |
| **Chat** | Suggested prompts + follow-up Q&A over the completed analysis |

Because the pipeline blocks, a run executes on a worker thread and pushes
progress over SSE — the same pattern the campaign module uses, so the frontend
reuses its SSE client.

Chart data is aggregated server-side with pandas and returned plot-ready from
`GET /api/analytics/sessions/{id}/charts`, so the raw dataset never reaches the
browser. Charts are inline SVG — no charting dependency — on a palette
validated for colour-vision deficiency against the app's dark surface. The
recommender does not guarantee which axis holds the measure, so axes are
resolved by dtype rather than trusted positionally.

### The original Streamlit UI

Still available as an internal tool against the same database:

```bash
docker compose -f docker/docker-compose.yml --profile streamlit up
# or
streamlit run src/analytics/ui/streamlit_app.py
```

---

## 9. Frontend

Next.js 14 (App Router), React 18, TypeScript, Tailwind, Framer Motion. One app,
one login, four views:

| View | Component |
|---|---|
| Landing | `components/Landing.tsx` |
| Campaign chat | `components/ChatExperience.tsx` |
| My Campaigns | `components/MyCampaigns.tsx` |
| Analytics | `components/analytics/AnalyticsExperience.tsx` + six tab components |

`lib/api.ts` is the typed campaign client, `lib/analytics.ts` the analytics
client, `lib/sse.ts` the SSE helper.

The design language is a warm dark canvas (`#0A0805`) with a gold accent system
(`#C9A84C` prestige primary, `#E8C97A` bright secondary) and glassmorphism
cards — see `tailwind.config.ts`.

```bash
cd frontend
cp .env.local.example .env.local     # set NEXT_PUBLIC_API_BASE if not localhost:8000
npm install
npm run dev                          # dev server
npm run build && npm start           # production
```

---

## 10. Operations

### Tests

```bash
python -m pytest          # 202 tests, no database or API key required
```

`conftest.py` at the repo root puts the project on `sys.path`, so tests run from
any directory. All LLM calls in the suite are mocked.

| Suite | Covers |
|---|---|
| `tests/crm/` | Lead-scoring formula and lookup tables, `AgentResponse`/`GraphState`, RRF fusion, routing functions |
| `tests/campaigns/` | Every pipeline node, the Meta client factory, the Strategist, LLM tiering |
| `tests/analytics/` | Chart-builder axis resolution and type mapping, per-analysis id scoping |

The suite does not cover the database or the live pipeline. To verify those
against a real PostgreSQL and live Gemini:

```bash
docker run -d --name automark_test_db -p 55432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=automark pgvector/pgvector:pg16
```

Then, in the same terminal (adjust the env-var syntax for your shell):

```bash
# macOS / Linux / Git Bash
DATABASE_URL=postgresql://postgres:postgres@localhost:55432/automark python -m uvicorn src.main:app --port 8077
```

```powershell
# Windows PowerShell
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:55432/automark"
python -m uvicorn src.main:app --port 8077
```

```bat
:: Windows cmd.exe
set DATABASE_URL=postgresql://postgres:postgres@localhost:55432/automark
python -m uvicorn src.main:app --port 8077
```

then register a user, upload a CSV, and run an analysis through `/api/analytics`.

### Health & monitoring

| Endpoint | Returns |
|---|---|
| `GET /health` | Liveness — status and version |
| `GET /health/deep` | PostgreSQL connectivity + knowledge-base chunk count, HubSpot status |
| `GET /api/crm/hubspot/check` | HubSpot scope diagnosis with exact fix steps |
| `GET /api/crm/admin/db/stats` | Row counts, lead temperature spread, escalation status spread |

### Logs

Structured logging via `structlog`. Set `LOG_FORMAT=json` for production
aggregation, `console` for human-readable local output.

With `AGENT_LOGGING=true`, `agent_logger.py` wraps every campaign node and
records inputs, outputs, duration, interrupts, and errors to
`.agent_logs/run_<timestamp>.log` and `.jsonl`.

### Troubleshooting

| Symptom | Cause & fix |
|---|---|
| `ConnectionRefusedError` on startup | PostgreSQL is not running, or `DATABASE_URL` points at the wrong port |
| `type "vector" does not exist` | pgvector not installed — use the `pgvector/pgvector:pg16` image or `CREATE EXTENSION vector` |
| `startup.hubspot_misconfigured` | Token valid but missing scopes — hit `/api/crm/hubspot/check` for the exact list ([§3.5](#35-hubspot)) |
| Meta webhook verification fails (403) | `MESSENGER_VERIFY_TOKEN` in `.env` does not match what you typed in the Meta dashboard |
| Publishing fails with an auth error | `META_APP_ID` is empty, or does not pair with `META_APP_SECRET` ([§3.4](#step-2--app-id-and-app-secret)) |
| `429` from Gemini | Free-tier rate limit — wait, or enable billing on the Google Cloud project |
| Frontend calls fail with CORS errors | Add your origin to `CORS_ORIGINS`, or set `DEBUG=true` for local development |
| Analytics run finishes but no charts appear | The recommender returned only `card`/`table` types for that dataset — expected, the Overview tab shows those numbers |
| Campaign conversation lost after restart | Check the startup log for `Checkpointer: ...` — if it says `MemorySaver`, `langgraph-checkpoint-postgres`/`-sqlite` failed to load (see log warning just above it) and neither Postgres nor the SQLite file was reachable |

---

## 11. Known gaps

> **Meta webhook signatures are not verified.** The Messenger and Facebook
> Page-comment webhooks do not check the `X-Hub-Signature-256` header, even
> though `MESSENGER_APP_SECRET` / `FB_COMMENTS_APP_SECRET` are configured.
> Anyone who knows the public URL can post a payload and make the agent process
> a fabricated message — sending real replies, creating leads, and consuming
> Gemini quota. The Vapi webhook *does* verify its secret. **Put the two Meta
> webhooks behind signature verification before exposing them publicly.**

> **The CRM admin routes are unauthenticated.** Everything under
> `/api/crm/admin/db/*` reads and deletes lead, conversation, and escalation
> data without a token. Firewall them or place them behind a reverse-proxy auth
> layer in production.

> **Checkpoint packages are pinned off the langgraph-checkpoint 2.x line
> deliberately.** `langgraph==0.3.34` resolves `langgraph-checkpoint==2.1.2`;
> the 3.x releases of `langgraph-checkpoint-sqlite`/`-postgres` require a
> newer `langgraph-checkpoint` than that and fail to import
> (`cannot import name 'DeltaChannelHistory'` is the exact symptom). If you
> ever bump `langgraph` itself, re-check these three pins together.

---

<div align="center">

Built with **LangGraph** · **FastAPI** · **Next.js** · **Google Gemini** · **Meta Marketing API**

</div>
