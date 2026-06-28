# AutoMark AI 🏢

**An autonomous, multi-agent AI system that builds, launches, and manages real-estate ad campaigns on Meta (Facebook & Instagram) — from a few photos and a short conversation.**

AutoMark AI lets a real-estate developer, brokerage, or agent create a professional, fully-compliant Meta advertising campaign in under two minutes — with no marketing experience. The user chats with **“Mark”**, uploads real unit photos, answers a handful of questions, and a squad of specialised AI agents researches the market, writes the ad copy, plans the budget and audience, enforces Meta’s HOUSING advertising rules, and publishes the campaign. After launch, the system keeps watching the campaign and recommends optimisations.

---

## Table of Contents

1. [What it does](#what-it-does)
2. [System architecture (high level)](#system-architecture-high-level)
3. [Technology stack](#technology-stack)
4. [Repository layout](#repository-layout)
5. [Prerequisites](#prerequisites)
6. [Environment configuration (`.env`)](#environment-configuration-env)
7. [Database setup (PostgreSQL)](#database-setup-postgresql)
8. [Running the app](#running-the-app)
9. [Using the app](#using-the-app)
10. [Operating modes (simulation vs live)](#operating-modes-simulation-vs-live)
11. [Debugging & agent logs](#debugging--agent-logs)
12. [Testing](#testing)
13. [Further documentation](#further-documentation)

---

## What it does

- **Conversational onboarding** — a chat assistant (“Mark”) collects the campaign brief in plain English or Egyptian Arabic.
- **Vision analysis** — reads the uploaded unit photos to understand what is being sold.
- **Market research** — pulls competitor ads from the **Meta Ad Library**, builds a HOUSING-compliant audience plan, and maps Egypt’s seasonal real-estate demand windows.
- **Creative generation** — writes multiple ad copies, headlines, and a call-to-action; attaches the user’s **real** unit photos (no AI-generated people — strictly enforced).
- **Media planning** — allocates the budget across Facebook/Instagram, sets the bid strategy, and computes the daily spend.
- **Compliance gate** — validates every campaign against Meta’s **HOUSING Special Ad Category** rules before anything can be published.
- **Human-in-the-loop** — the user reviews and approves the goal, interview answers, photo selection, and ad copy at each step.
- **Publishing** — creates the real campaign, ad set, creative, and ad on Meta (paused for safety), plus an optional organic page post.
- **Operate loop** — after launch, a scheduler periodically diagnoses performance (cost-per-lead, lead quality, ad fatigue) and proposes actions (scale, pause, refresh creative), asking for approval before spending money.
- **Accounts & history** — users sign up, and every campaign (with its Meta IDs and full plan) is saved to their account and viewable on a **My Campaigns** page.

---

## System architecture (high level)

AutoMark AI is built on **LangGraph**: a stateful, multi-agent graph where each node is a specialised agent that reads and writes a single shared `CampaignState`. A central **Supervisor** routes between agents; **human-in-the-loop interrupts** pause the graph for user input; and a **checkpointer** persists graph state so paused conversations can resume.

```
                       ┌──────────────────────────────────────────────┐
   Next.js Frontend    │                 FastAPI Backend              │
  (conversational UI)  │                                              │
        │  REST / SSE   │   ┌────────────┐      ┌──────────────────┐  │
        ├──────────────►│   │ LangGraph  │◄────►│  CampaignState   │  │
        │               │   │ Supervisor │      │  (shared memory) │  │
        │               │   └─────┬──────┘      └──────────────────┘  │
        │               │         │  routes to 19 agent nodes         │
        │               │  Discovery → Research → Plan → Creative →   │
        │               │  Media → Merge → Compliance → (Operate)     │
        │               │         │                                   │
        │               │   ┌─────┴──────┐  ┌──────────┐  ┌────────┐  │
        │               │   │ LLM client │  │ Meta API │  │ Postgres│ │
        │               │   │ Gemini/Groq│  │  client  │  │  + JWT  │ │
        │               │   └────────────┘  └──────────┘  └────────┘  │
        │               └──────────────────────────────────────────────┘
```

> 📐 **For the full agentic architecture** — every agent, the graph topology, the design patterns, and the data flow — see **[`Module_1_Agentic_Architecture.md`](Module_1_Agentic_Architecture.md)**.

---

## Technology stack

| Layer | Technology |
|---|---|
| **Agent orchestration** | LangGraph 1.2 (StateGraph, interrupts, checkpointers) |
| **Backend API** | FastAPI + Uvicorn, Server-Sent Events (SSE) for streaming |
| **Text LLM** | Configurable: **Google Gemini** (`gemini-2.5-flash`, default) or **Groq** (`openai/gpt-oss-120b`) |
| **Vision (image understanding)** | Google Gemini (multimodal) |
| **Image generation** | Gemini image model (available, but not used for real-estate creative) |
| **Ad platform** | Meta Marketing API via `facebook_business` SDK + Meta Ad Library API |
| **Database** | PostgreSQL (business records via `psycopg2`; LangGraph checkpoints) |
| **Auth** | Email/password — `bcrypt` hashing + `PyJWT` tokens |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Framer Motion |
| **Languages** | English + Egyptian Arabic (full RTL support) |

---

## Repository layout

```
FinalProject_AutoMarkAI/
├── README.md                          ← this file
├── Module_1_Agentic_Architecture.md   ← agentic architecture deep-dive
├── debug_agents.py                    ← standalone per-agent I/O harness
├── AutoMarkAi/
│   ├── backend/
│   │   ├── api.py                 ← FastAPI app: sessions, auth, campaigns, publish
│   │   ├── pipeline_graph.py      ← the full LangGraph topology (web app graph)
│   │   ├── graph.py               ← simpler graph used by the CLI entry point
│   │   ├── main.py                ← CLI entry point
│   │   ├── state.py               ← CampaignState schema (shared memory)
│   │   ├── llm_client.py          ← Gemini/Groq text + vision + image gen
│   │   ├── meta_client.py         ← Meta Marketing API (Simulated + Real)
│   │   ├── db.py                  ← PostgreSQL business tables (users, campaigns)
│   │   ├── auth.py                ← bcrypt + JWT
│   │   ├── agent_logger.py        ← wraps each node, logs I/O to .agent_logs/
│   │   ├── i18n.py                ← English / Arabic prompt selection
│   │   ├── real_estate_utils.py   ← price-tier & geo helpers
│   │   ├── strategy_tools.py      ← timezone, scheduling, web-search helpers
│   │   ├── nodes/                 ← the 19 agent nodes (see architecture doc)
│   │   ├── research/ compliance/ policy/ memory/ prompts/ templates/
│   │   └── workers/scheduler.py   ← operate-loop cadence scheduler
│   └── frontend/
│       ├── app/                   ← Next.js pages (page.tsx, layout.tsx)
│       ├── components/            ← chat UI, cards, AuthModal, MyCampaigns…
│       ├── hooks/                 ← useCampaignChat, useAuth
│       └── lib/                   ← typed API client, types, SSE, copy
└── AutoMarkAi/.env                ← configuration (see below)
```

---

## Prerequisites

- **Python 3.11+** (developed on 3.11.5)
- **Node.js 18+** (developed on 22.5.1)
- **PostgreSQL 14+**
- API keys: a **Google Gemini** key (required), optionally a **Groq** key, and **Meta** credentials if running in live mode.

---

## Environment configuration (`.env`)

All backend configuration lives in **`AutoMarkAi/.env`**. The most important settings:

```ini
# --- LLM provider ---
LLM_PROVIDER=gemini                 # "gemini" (default) or "groq"
GEMINI_API_KEY=your_gemini_key      # required (text, vision, image)
GROQ_API_KEY=your_groq_key          # required only if LLM_PROVIDER=groq

# --- Meta Marketing API ---
META_SIMULATION_MODE=false          # true = fake responses (no real ads / no keys needed)
META_ACCESS_TOKEN=...               # user/system token with ads_management + pages_manage_posts
META_APP_SECRET=...
META_AD_ACCOUNT_ID=...              # numeric, no "act_" prefix
META_PAGE_ID=...                    # Facebook Page for creatives & organic posts
META_AD_LIBRARY_TOKEN=...           # competitor research (can equal META_ACCESS_TOKEN)

# --- Database & auth ---
POSTGRES_URL=postgresql://postgres:PASSWORD@localhost:5432/automark_db
JWT_SECRET=change-me-in-production

# --- Behaviour tuning ---
MIN_QUESTIONS=4
MAX_QUESTIONS=15
ENABLE_FOLLOW_UPS=true
NUM_GENERATED_IMAGES=1
MAKE_SPONSORED_PAUSED_AD=1
MAKE_ORGANIC_POST=1
LIFECYCLE_DIAGNOSIS_HOUR=9          # UTC hour the daily diagnosis fires (live mode)
AGENT_LOG=true                      # write per-agent I/O logs to .agent_logs/
```

> 💡 **Just want to try it without Meta credentials?** Set `META_SIMULATION_MODE=true`. The whole pipeline runs end-to-end with realistic fake responses — no real ads are created and no Meta keys are needed. You still need a Gemini key for the LLM/vision agents.

---

## Database setup (PostgreSQL)

The database serves **two roles**: it stores your **business records** (users, campaigns, Meta IDs) and — if a LangGraph Postgres checkpointer package is installed — the **agent runtime state**.

**1. Install PostgreSQL** from [postgresql.org/download](https://www.postgresql.org/download/) (remember the `postgres` password).

**2. Create the database** — open the “SQL Shell (psql)” and run:

```sql
CREATE DATABASE automark_db;
\q
```

**3. Point the app at it** — set `POSTGRES_URL` in `.env`:

```ini
POSTGRES_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/automark_db
```

**4. Tables are created automatically** on backend startup (`users`, `campaigns`). You’ll see in the logs:

```
INFO db: PostgreSQL connection pool initialised
INFO db: schema ready (users + campaigns)
```

**Viewing your data** — use **pgAdmin 4** (ships with PostgreSQL), **DBeaver** (free), or the CLI:

```sql
psql -U postgres -d automark_db
\dt                                   -- list tables
SELECT email, created_at FROM users;
SELECT compound_name, status, meta_campaign_id, created_at FROM campaigns;
```

> ℹ️ **(Optional) Persistent agent state across restarts.** LangGraph’s graph checkpoints fall back to in-memory by default (lost on restart). To persist resumable conversations in Postgres too, install:
> ```bash
> pip install langgraph-checkpoint-postgres
> ```
> The business tables (`users`, `campaigns`) always use Postgres regardless.

---

## Running the app

Two terminals. Run the **backend from the repository root** (`FinalProject_AutoMarkAI/`) so the `AutoMarkAi.backend...` package path resolves.

### 1. Install dependencies (first time only)

**Backend** (from the repo root):

```bash
pip install fastapi "uvicorn[standard]" python-multipart python-dotenv pydantic \
    langgraph langgraph-checkpoint \
    google-generativeai google-genai groq pillow requests \
    facebook_business \
    psycopg2-binary bcrypt PyJWT
```

**Frontend**:

```bash
cd AutoMarkAi/frontend
npm install
```

### 2. Start the backend (Terminal 1, from repo root)

```bash
uvicorn AutoMarkAi.backend.api:app --reload --port 8000
```

Ready when you see `Application startup complete`. API docs are at **http://localhost:8000/docs**.

### 3. Start the frontend (Terminal 2)

```bash
cd AutoMarkAi/frontend
npm run dev
```

Open **http://localhost:3000**.

> The frontend talks to `http://localhost:8000` by default. To change it, set `NEXT_PUBLIC_API_BASE` in the frontend environment.

---

## Using the app

1. **Landing page** → click **“Create my real estate campaign”**.
2. **Sign up / log in** (email + password). After auth you return to the landing page as a logged-in user.
3. **Chat with Mark**: choose language → upload unit photos → (optional) upload brochure/floor-plans/logo → set budget → pick a campaign goal → answer a short interview.
4. **Review**: the agents build the plan; you select which photos to use and pick/edit the ad copy + headline.
5. **Publish**: review the assembled campaign and publish to Meta (created **paused** for safety) — or just preview it in simulation mode.
6. **My Campaigns**: open from the top-right nav to see all your saved campaigns as cards; click any card for the full detail (Meta IDs, audience, creative, strategy).

---

## Operating modes (simulation vs live)

| | `META_SIMULATION_MODE=true` | `META_SIMULATION_MODE=false` |
|---|---|---|
| Meta API calls | Faked (no real ads) | Real campaigns created (paused) |
| Competitor research | Curated synthetic data | Live Meta Ad Library |
| Operate-loop metrics | Synthetic, generated | Real Meta Insights |
| Meta credentials | Not required | Required |
| Use for | Demos, development, testing | Production / real launches |

The Gemini (or Groq) LLM is **always** called for real in both modes — only the Meta side is simulated.

---

## Debugging & agent logs

- **Runtime agent logs** — with `AGENT_LOG=true`, every agent’s inputs and outputs are written to `.agent_logs/run_<timestamp>.log` (human-readable) and `.jsonl` (machine-readable) during normal operation. Open these after a session to see exactly what each agent received and produced, step by step.
- **Standalone harness** — `python debug_agents.py` runs the pipeline in a terminal, printing each agent’s I/O and pausing for you to answer interrupts manually. Useful for inspecting one agent in isolation.

---

## Testing

The backend ships with a pytest suite under `AutoMarkAi/backend/tests/`:

```bash
# from the repo root
python -m pytest AutoMarkAi/backend/tests -q
```

---

## Further documentation

| Document | Contents |
|---|---|
| **[Module_1_Agentic_Architecture.md](Module_1_Agentic_Architecture.md)** | Full agentic architecture: every agent, graph topology, design patterns |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Product overview |
| [Advanced_Agentic_Architecture.md](Advanced_Agentic_Architecture.md) | Extended architecture notes |
| [STRATEGY_AGENT_OVERVIEW.md](STRATEGY_AGENT_OVERVIEW.md) | Deep-dive on the Strategist agent |
| [real-estate-media-buying-plan.md](real-estate-media-buying-plan.md) | Media-buying methodology |

---

*Built with LangGraph, FastAPI, Next.js, Google Gemini, and the Meta Marketing API.*
