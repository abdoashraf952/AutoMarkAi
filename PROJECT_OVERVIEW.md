# AutoMark AI — Project Overview

> **AutoMark AI** is an AI-powered assistant that turns a few photos and simple
> answers into a ready-to-publish **Meta (Facebook & Instagram) ad campaign** for
> **Egyptian real estate developers and brokers** — no marketing experience needed.

---

## 1. The Business

### The problem

Real estate agencies in Egypt spend heavily on Meta ads, but getting a campaign
live well is hard:

- **Marketing expertise is scarce.** Sales teams know the units; they don't know
  audience targeting, bidding, ad copy, or Meta's policies.
- **Agencies/freelancers are expensive and slow.** A single campaign can take days
  of back-and-forth and cost thousands of pounds before a single ad runs.
- **Real estate has special rules.** Meta classifies housing ads under a
  **Special Ad Category (HOUSING)** that forbids age/gender targeting. Get it
  wrong and the ad is rejected — or the account is flagged.
- **Authenticity matters.** Buyers want to see the *actual* units. AI-generated or
  heavily edited imagery erodes trust and can be misleading.

### The solution

AutoMark AI is a friendly chatbot — **"Mark"** — that walks the user through a
short, plain-language conversation and does the expert work behind the scenes:

1. The user uploads **real photos** of their units and their marketing assets
   (logo, brochure, floor plans, etc.).
2. Mark asks a curated set of **real estate questions** (compound name, location,
   unit types, price, payment plan, current offer, where leads should go, how long
   to run) — one at a time, with smart follow-ups when an answer needs detail.
3. The system generates a complete campaign: **ad copy + headlines** written for
   the Egyptian market, **audience targeting** that is automatically
   HOUSING-compliant, **budget and bidding strategy**, and a **posting schedule**.
4. The user reviews and tweaks the copy, picks which photos to feature, and
   **publishes to Meta in one tap**.

### Who it's for

- **Real estate developers** launching or promoting a compound/project.
- **Brokers and sales offices** running lead-generation campaigns.
- **Marketing teams** that want a fast, compliant first draft they can refine.

### What makes it valuable

| Value | How AutoMark delivers it |
|-------|--------------------------|
| **Speed** | A full campaign in minutes, not days. |
| **No expertise required** | Plain-language chat; no jargon (no CPL/CTR/ROAS). |
| **Compliance built in** | HOUSING rules enforced automatically (18–65, all genders, broad geo). |
| **Authentic creative** | Uses the agency's real unit photos — never AI-faked imagery. |
| **Localized** | Egyptian-Arabic and English copy; EGP pricing; local market defaults. |
| **Smart by default** | Targeting, tone, and platform split auto-inferred from the unit price tier. |
| **Safe to try** | Simulation mode lets users run the whole flow without touching a live ad account. |

### How the campaign is shaped automatically

The unit's **starting price** drives a set of smart defaults so the campaign fits
the buyer segment without the user configuring anything:

| Price tier (EGP) | Buyer profile | Tone | Platform split |
|------------------|---------------|------|----------------|
| Under 2M | First-time buyers, young couples | Warm, family-oriented | FB 60 / IG 40 |
| 2M – 5M | Mid-income families, upgraders | Modern, aspirational | FB 50 / IG 50 |
| 5M – 15M | Upper professionals, executives | Exclusive, lifestyle | IG 60 / FB 40 |
| Above 15M | High-net-worth, investors | Exclusive, aspirational | IG 70 / FB 30 |

---

## 2. The Technical Part

### High-level architecture

AutoMark AI is a two-service application:

```
┌─────────────────────────┐        HTTP + SSE        ┌────────────────────────────┐
│   Next.js Frontend       │ ───────────────────────▶ │   FastAPI Backend          │
│  (conversational chat UI)│ ◀─────────────────────── │  (LangGraph pipeline)      │
└─────────────────────────┘                          └────────────┬───────────────┘
                                                                   │
                                          ┌────────────────────────┼───────────────────────┐
                                          ▼                        ▼                       ▼
                                   Groq (text LLM)         Gemini (vision)          Meta Marketing API
                                   copy / strategy /       photo understanding      (simulated or live)
                                   media buying            for planning
```

- **Frontend** — a guided chatbot that renders exactly the right input control for
  each step of the conversation (option cards, multi-photo uploader, file uploads,
  copy editor, photo picker).
- **Backend** — a **LangGraph** state machine with **human-in-the-loop** pauses
  (interrupts). It orchestrates several specialized LLM "agents" and waits for the
  user at each decision point.
- **LLM split** — **Groq** handles text (ad copy, strategy, media buying for low
  latency/cost); **Gemini** handles vision (understanding the uploaded unit photos
  to build the plan).
- **Meta integration** — a client abstraction with a **Simulated** mode (realistic
  fake responses, no credentials needed) and a **Real** mode (live Meta Marketing
  API via the `facebook-business` SDK).

### Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js (App Router), React, TypeScript, Tailwind CSS, Framer Motion |
| Backend | Python, FastAPI, LangGraph, Server-Sent Events (SSE) |
| Text LLM | Groq (with fallback) |
| Vision LLM | Google Gemini (multimodal) |
| Ads API | Meta Marketing API (`facebook-business`), simulation + live modes |
| State | LangGraph `MemorySaver` checkpointer; in-memory session store |

### The pipeline (LangGraph)

The campaign is built by a graph of nodes. Generation nodes never contain a
user-interrupt, so resuming a paused graph never re-runs (or re-bills) an LLM call.

```
START
  → target_gen → target_ask        [interrupt: pick campaign goal]
  → question_gen ⇄ question_ask     [interrupt loop: real estate interview]
  → orchestrator                    [Gemini: read photos → campaign plan + price tier]
  → strategy                        [persona, channels, dayparting]
  → fan-out:
       creative                     [Groq: ad copy + headlines; attaches real photos]
       media_buying                 [Groq: budget, bids, HOUSING-compliant audience]
  → photo_select                    [interrupt: choose which photos to feature]
  → text_review                     [interrupt: pick/edit copy + headline]
  → merge                           [assemble final campaign bundle] → END
                                    → publish to Meta (HOUSING category)
```

### The real estate interview

Instead of free-form AI questions (which can miss critical details), the interview
uses a **curated, fixed question list** with **optional LLM follow-ups**:

- A fixed list covers the essentials: compound name, location, unit types, starting
  price, payment plan, current offer, lead destination, and campaign duration.
- After each answer, an LLM decides whether **one short follow-up** would add value
  (e.g. the user mentioned a unique feature) — otherwise it moves on.
- Questions support **free-text**, **single-select**, and **multi-select** with an
  **"Other"** option, each with a recommended choice where helpful.
- Answers populate `real_estate_data`, which flows into the plan, copy, and the
  final campaign bundle.

### HOUSING compliance (defense in depth)

Real estate ads must obey Meta's HOUSING Special Ad Category. The system enforces
this at **three layers** so a non-compliant campaign can't slip through:

1. **Prompts** instruct the LLMs to never narrow age/gender.
2. **The media-buying and merge nodes** apply a hard override:
   `age_min = 18`, `age_max = 65`, `genders = ["all"]`, no income/ZIP targeting.
3. **The Meta client** declares `special_ad_categories: ["HOUSING"]` on campaign
   creation.

### Key API endpoints (backend)

| Endpoint | Purpose |
|----------|---------|
| `POST /session` | Create a session. |
| `POST /session/{id}/upload-asset` | Upload logo / brochure / floor plans / etc. |
| `POST /session/{id}/start` | Start the pipeline with the unit photos. |
| `GET  /session/{id}/stream` | SSE stream of live progress events. |
| `POST /session/{id}/answer` | Answer the campaign goal or an interview question. |
| `POST /session/{id}/select-photos` | Choose which photos appear in the ad. |
| `POST /session/{id}/text-decision` | Pick and edit the final copy + headline. |
| `POST /session/{id}/publish` | Publish to Meta (sponsored ad + organic post). |

### The final output: the campaign bundle

The pipeline produces a single structured `campaign_bundle` containing everything
needed to publish:

- **`campaign`** — platform, objective, tone, and `special_ad_categories: ["HOUSING"]`.
- **`real_estate_project`** — compound name, location, unit types, price, payment
  plan, offer, lead destination, duration, and inferred price tier.
- **`creative`** — copies, headlines, CTA, and the selected real unit photos.
- **`media`** — budget split, daily budget (total ÷ duration), HOUSING-compliant
  audience, placements, bid strategy.
- **`strategy`** — target persona, channel mix, and an advisory posting schedule.

### Repository layout

```
AutoMarkAi/
├── backend/
│   ├── api.py                 # FastAPI app: sessions, SSE, endpoints
│   ├── pipeline_graph.py      # LangGraph topology
│   ├── state.py               # Shared pipeline state schema
│   ├── i18n.py                # Locale loader (en / ar)
│   ├── llm_client.py          # Groq + Gemini wrappers
│   ├── meta_client.py         # Meta API: Simulated + Real clients
│   ├── real_estate_utils.py   # Price-tier smart defaults
│   ├── nodes/                 # Pipeline nodes (orchestrator, strategy,
│   │                          #   creative, media_buying, question_generator,
│   │                          #   review, merge)
│   ├── templates/locales/     # en/ and ar/ prompt templates + UI strings
│   └── tests/                 # Pytest suite
└── frontend/
    ├── app/                   # Next.js routes
    ├── components/            # Chat UI, step controls, result cards
    ├── hooks/useCampaignChat  # Conversation state machine
    └── lib/                   # API client, types, copy (en/ar)
```

### Running it

```bash
# Backend (from the repository parent directory)
uvicorn AutoMarkAi.backend.api:app --reload

# Frontend
cd AutoMarkAi/frontend
npm install
npm run dev
```

**Environment / configuration (`.env`):**

- `GROQ_API_KEY`, `GEMINI_API_KEY` — LLM providers.
- `META_SIMULATION_MODE` — `true` (default, safe demo) or `false` (live Meta API).
- Meta live credentials: `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`, `META_PAGE_ID`, …
- Optional tuning: `ENABLE_FOLLOW_UPS` (interview follow-ups), `ENABLE_WEB_SEARCH`
  (live trend lookups for strategy).

### Design principles worth highlighting

- **Human-in-the-loop, not full automation.** The user approves goal, photos, and
  copy — Mark proposes, the user decides.
- **Checkpoint-safe generation.** Costly LLM/vision calls live in non-interrupting
  nodes, so resuming a paused conversation never re-bills work.
- **Compliance as code.** HOUSING rules are enforced programmatically, not left to
  the model's discretion.
- **Bilingual by design.** Every prompt and UI string exists in English and
  Egyptian Arabic, switchable at the first step.
- **Safe by default.** Simulation mode means the entire experience can be
  demonstrated end-to-end without a live ad account.
