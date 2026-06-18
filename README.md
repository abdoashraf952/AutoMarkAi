# AutoMark AI — Meta Ad Campaign Generator

AutoMark AI is an **AI-powered pipeline** that takes a product image, a budget, and a campaign goal, and produces a complete **Meta (Facebook/Instagram) ad campaign** — real generated ad images, ad copies, headlines, audience targeting, and budget allocation — then **publishes it directly to Meta** as a paused sponsored ad and an organic page post.

---

## What Does It Do?

You give it three things:

| Input | Example |
| --- | --- |
| Product image | `watch.jpg` |
| Budget (USD) | `500` |
| Campaign goal | `"get WhatsApp leads for luxury watch"` |

It asks you 4 product-specific questions, lets you review and approve the generated image and ad copy, then publishes to Meta:

- **Product analysis** — what the product is, visual description
- **Campaign strategy** — platform (Instagram/Facebook/both), objective, tone
- **Ad image** — either your original photo, or your photo enhanced by Gemini AI
- **Ad creative** — ad copies, headlines, CTA button text
- **Media buying plan** — budget split per platform, daily budget, audience targeting, placements, bid strategy, estimated reach
- **Meta publish** — paused sponsored campaign (Campaign → Ad Set → Creative → Ad) and organic page post

---

## Two Ways to Run

The project is split into a **FastAPI backend** (this folder) and a **Next.js frontend** (`../web`).

| Mode | Command | Features |
| --- | --- | --- |
| **FastAPI + Next.js** (primary) | `uvicorn api:app --reload --port 8000` then `cd ../web && npm run dev` | Full conversational flow — Q&A, image review, copy review, Meta publish |
| **CLI** (fallback) | `python main.py --image X --budget Y --goal Z` | Single invocation, no review steps, no publish |

---

## Architecture Overview

The system has **two graph variants** built on LangGraph:

### Pipeline Graph (full pipeline, `pipeline_graph.py`)

```
User Input (image + budget + goal + image_mode)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│               question_generator_node                         │
│  • Analyzes product image + goal with Gemini Vision           │
│  • Generates 4 product-specific questions                     │
│  • INTERRUPT → waits for user answers                         │
└──────────────────────┬───────────────────────────────────────┘
                       │  (answers appended to orchestrator prompt)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                   orchestrator_node                           │
│  • Analyzes image with Gemini Vision + Q&A context            │
│  • Decides platform, objective, tone, target audience         │
│  • Produces: campaign_plan                                    │
└──────────────────────┬───────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │  Fan-out (parallel)     │
          ▼                         ▼
┌──────────────────┐     ┌──────────────────────┐
│  creative_node   │     │  media_buying_node    │
│ • Writes ad      │     │ • Allocates budget    │
│   copies         │     │   per platform        │
│ • Writes         │     │ • Defines audience    │
│   headlines      │     │   targeting           │
│ • Sets CTA       │     │ • Picks bid strategy  │
│ • Sources image: │     │ • Estimates reach     │
│   use_original → │     │                       │
│   encodes photo  │     │                       │
│   enhance_with_  │     │                       │
│   ai → Gemini    │     │                       │
│   image model    │     │                       │
└────────┬─────────┘     └──────────┬────────────┘
         │                          │
         ▼                          │
┌──────────────────────────────┐    │
│         review_node          │    │
│ • INTERRUPT → image review   │    │
│   use_original: confirm only │    │
│   enhance_with_ai: approve / │    │
│   re-enhance with feedback   │    │
│ • INTERRUPT → text review    │    │
│   (copies, headlines, CTA)   │    │
│                              │    │
│  If text rejected → loops    │    │
│  back to creative_node       │    │
└──────────┬───────────────────┘    │
           │  (when all approved)   │
           └─────────┬──────────────┘
                     │  Fan-in
                     ▼
          ┌─────────────────────────┐
          │       merge_node        │
          │ • Validates all outputs │
          │ • Fixes CTA mismatches  │
          │ • Normalizes budget     │
          │ • Assembles final JSON  │
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │     Publish to Meta     │
          │ (user-triggered button) │
          │ • create_campaign       │
          │ • create_ad_set         │
          │ • create_ad_creative    │
          │ • create_ad (PAUSED)    │
          │ • publish_post          │
          └─────────────────────────┘
```

### CLI Graph (simplified, no interrupts)

```
START → orchestrator_node → [fan-out] → creative_node ─┐
                                      → media_buying_node ─┴→ merge_node → END
```

The CLI graph skips `question_generator_node`, `review_node`, and the Meta publish step.

---

## File Structure

```
AutoMarkAi/
│
├── api.py                    ← FastAPI backend — REST endpoints + SSE streaming
├── main.py                   ← CLI entry point (no review, no publish)
├── graph.py                  ← CLI graph — no interrupts, no checkpointer
├── pipeline_graph.py         ← Full graph — MemorySaver, all nodes (used by api.py)
├── state.py                  ← Shared state schema (TypedDict)
├── llm_client.py             ← LLM abstraction — Groq for all text/vision, Gemini for image gen
├── meta_client.py            ← Meta Marketing API client (simulated + real)
│
├── nodes/
│   ├── question_generator.py ← Node 0: vision → questions + interrupt for answers
│   ├── orchestrator.py       ← Node 1: vision + Q&A context → campaign_plan
│   ├── creative.py           ← Node 2: text + image sourcing (original or Gemini image edit)
│   ├── media_buying.py       ← Node 3: text → budget, audience, placements
│   ├── review.py             ← Node 4: split interrupt nodes — image review, regen, pick, text review
│   └── merge.py              ← Node 5: pure Python validation + JSON assembly
│
├── prompts/
│   ├── question_generator.py ← Prompts for question_generator_node
│   ├── orchestrator.py       ← Prompts for orchestrator_node
│   ├── creative.py           ← Prompts for creative_node
│   └── media_buying.py       ← Prompts for media_buying_node
│
├── tests/
│   ├── test_nodes.py         ← Unit tests for core pipeline nodes
│   ├── test_new_nodes.py     ← Unit tests for question generator, review, creative
│   ├── test_meta_client.py   ← Unit tests for Meta client (simulated + real)
│   └── sample_input/
│       ├── watch.jpg         ← Sample luxury watch image
│       ├── peugeot-508.jpg   ← Sample car image
│       ├── T-shirt.png       ← Sample apparel image
│       └── keyborad.jpeg     ← Sample electronics image
│
├── requirements.txt          ← Python dependencies
├── .env.example              ← Template for environment variables
└── .env                      ← API keys and config (never commit this file)

test_api.py                   ← End-to-end API test script (project root)
```

---

## Node-by-Node Breakdown

### Node 0 — `question_generator_node` (`nodes/question_generator.py`)

**Role:** Warms up the pipeline by generating product-specific research questions before the orchestrator runs.

**How it works:**

1. Receives `image_path` and `goal` from the initial state
2. Calls **Gemini Vision** with the product image and a marketing analyst prompt
3. Parses the response into exactly 4 question strings (falls back to 4 generic questions if the LLM response is invalid)
4. Calls `interrupt()` — pauses the graph and sends the questions to the UI
5. Resumes when the user submits their answers

**LLM used:** Groq vision (`meta-llama/llama-4-scout-17b-16e-instruct`).

**Only in:** full pipeline graph. Skipped in CLI.

**Interrupt payload:**

```json
{
  "stage": "questions",
  "questions": ["Q1?", "Q2?", "Q3?", "Q4?"]
}
```

**Resume payload expected:**

```json
{"answers": {"0": "answer", "1": "answer", "2": "answer", "3": "answer"}}
```

---

### Node 1 — `orchestrator_node` (`nodes/orchestrator.py`)

**Role:** The "brain" of the pipeline. Analyzes the product image and builds the campaign strategy.

**How it works:**

1. Receives image path, budget, goal, and (in the full pipeline) the user Q&A from state
2. Formats the Q&A answers as a structured block and appends them to the prompt
3. Calls **Groq's vision model** (image + text) to produce a JSON campaign plan

**LLM used:** Groq vision (`meta-llama/llama-4-scout-17b-16e-instruct`).

**Output — `campaign_plan`:**

```json
{
  "product_type": "Luxury Watch",
  "product_description": "An elegant gold-bezeled timepiece with a minimalist dial.",
  "platform": "instagram",
  "objective": "MESSAGES",
  "tone": "Sophisticated and exclusive",
  "target_audience_hint": "Affluent adults aged 28-50 interested in luxury lifestyle",
  "budget": 500.0,
  "currency": "USD"
}
```

---

### Node 2 — `creative_node` (`nodes/creative.py`)

**Role:** The "creative agency". Writes all ad text assets and sources the ad image based on the user's selected image mode.

**Image modes:**

| Mode | What Happens |
| --- | --- |
| `use_original` | User's uploaded photo is base64-encoded and used directly as the ad image |
| `enhance_with_ai` | User's uploaded photo is passed to the Gemini image model as a visual reference; the model enhances it into an ad-ready image |

**How it works:**

1. Checks if `state["feedback"]["creative"]` is set (redo pass from review) — if so, appends it to the prompt
2. Calls `call_llm()` to generate copies, headlines, CTA, and a `visual_prompt` string
3. Depending on `image_mode`:
   - `use_original`: reads and encodes the uploaded file directly
   - `enhance_with_ai`: calls `enhance_ad_image(image_path, visual_prompt)` using the Gemini image model; falls back to `generate_ad_images()` on error

**LLM used for text:** Groq (`llama-3.3-70b-versatile`).

**Model used for images (the only Gemini usage):**
- Generation & enhancement: Gemini 3.1 Flash Image (`gemini-3.1-flash-image`) via the `google-genai` SDK

**Output — `creative_output`:**

```json
{
  "copies": [
    "Elevate your style. Discover timeless craftsmanship made for the extraordinary.",
    "Every second is precious. Own the watch that honours yours.",
    "Luxury you can feel. Message us to claim yours today."
  ],
  "headlines": ["Luxury Redefined", "Own Your Moment", "Timeless Elegance"],
  "cta": "Send Message",
  "visual_prompt": "A close-up of a gold luxury watch on marble, soft studio lighting…",
  "generated_images": ["<base64_png>"]
}
```

---

### Node 3 — `media_buying_node` (`nodes/media_buying.py`)

**Role:** The "media buyer". Runs **in parallel** with `creative_node`. Decides how to spend the budget and who to target.

**LLM used:** Groq (`llama-3.3-70b-versatile`).

**Output — `media_output`:**

```json
{
  "budget_split": {"instagram": 1.0, "facebook": 0.0},
  "daily_budget_usd": 71.43,
  "audience": {
    "age_min": 30, "age_max": 65,
    "genders": ["all"],
    "interests": ["Luxury watches", "Horology", "High-end timepieces"],
    "locations": ["US"],
    "income_tier": "top_10_percent"
  },
  "placement": ["feed", "stories"],
  "bid_strategy": "COST_CAP",
  "bid_amount_usd": 14.29,
  "optimization_goal": "CONVERSATIONS",
  "estimated_reach": {"min": 8000, "max": 20000},
  "reasoning": "Instagram-only for luxury product; COST_CAP for mid-range budget."
}
```

**Media buying rules enforced by the prompt:**

- `budget_split` values must sum to `1.0`
- `daily_budget_usd` = total budget ÷ 7 (assumes 7-day campaign)
- `bid_strategy`: budget < $200 → `LOWEST_COST_WITHOUT_CAP`, $200–$1000 → `COST_CAP`, > $1000 → `LOWEST_COST_WITH_BID_CAP`
- `bid_amount_usd`: required when strategy is `COST_CAP` or `LOWEST_COST_WITH_BID_CAP` (~20% of daily budget); null otherwise
- `locations`: ISO-3166-1 alpha-2 country codes (e.g. `["US", "GB"]`)

---

### Node 4 — review nodes (`nodes/review.py`)

**Role:** Human-in-the-loop quality gate. Implemented as **four separate graph
nodes** so that each image generation is its own checkpointed super-step:

| Node | Interrupt? | Side effects |
| --- | --- | --- |
| `image_review_node` | yes (`image_review`) | none — just captures the decision and routes |
| `image_regen_node` | no | regenerates the rejected image(s) **exactly once** |
| `image_pick_node` | yes (`max_regenerations_exceeded`) | none — builds the picker from stored history |
| `text_review_node` | yes (`text_review`) | none |

> **Why split?** The old monolithic `review_node` ran a `while` loop with several
> `interrupt()` calls and image generation *between* them. On every resume,
> LangGraph re-executes the node from the top and **replays every prior
> generation** — silently re-billing the image API and producing different
> images, so the "pick from history" gallery showed freshly generated images
> instead of the real ones. Moving generation into its own interrupt-free node
> fixes that: a resume only re-runs the interrupting node (which has no side
> effects), so a generation never repeats.

**Only in:** full pipeline graph. Not present in CLI.

**Phase 1 — Image Review:**

Behaviour depends on `image_mode`:

| Mode | Behaviour |
| --- | --- |
| `use_original` | Shows the photo for confirmation only — no regeneration option (`can_regenerate: False`) |
| `enhance_with_ai` | Shows the enhanced image with approve/feedback; a rejection routes to `image_regen_node` which re-enhances using the original photo + feedback; loops up to `MAX_REGENERATIONS_ALLOWED` times |

When the regeneration limit is exceeded (or the user asks to "see all versions"): `image_pick_node` sends a `max_regenerations_exceeded` interrupt showing the original photo + every previously generated image — user picks one. **No new image is generated here.**

**Phase 2 — Text Review (single interrupt):**

- User approves or provides a single feedback string
- Approved → `review_stage = "done"` → graph proceeds to `merge_node`
- Rejected → `review_stage = "redo_creative"` → graph loops back to `creative_node` with the feedback stored in state

**Interrupt payloads:**

```
Image review:   {"stage": "image_review", "images": ["<b64>"], "regen_count": 0,
                 "max_regens": 2, "can_regenerate": true|false}
Resume with:    {"approved": [true], "feedback": {0: "make it brighter"}}

Text review:    {"stage": "text_review", "copies": [...], "headlines": [...], "cta": "..."}
Resume with:    {"approved": false, "feedback": "Make the tone more urgent"}

Max regens:     {"stage": "max_regenerations_exceeded", "image_history": ["<b64>", ...], "message": "..."}
Resume with:    {"chosen_index": 0}
```

---

### Node 5 — `merge_node` (`nodes/merge.py`)

**Role:** The "quality controller". Validates and fixes both sub-agent outputs, then assembles the final bundle.

**Guard (full pipeline only):** If `review_stage` is set but not `"done"`, `merge_node` skips with `return {}`. The real merge runs only after the review nodes complete.

**What it validates and fixes:**

| Check | Fix Applied |
| --- | --- |
| Fewer than 3 copies | Pads with `"[Copy placeholder]"` |
| Copy exceeds 125 chars | Truncates to 125 chars |
| Fewer than 3 headlines | Pads with `"[Headline placeholder]"` |
| Headline exceeds 40 chars | Truncates to 40 chars |
| CTA doesn't match objective | Overrides CTA to the correct value |
| `budget_split` doesn't sum to 1.0 | Normalizes all values proportionally |

**Output — `campaign_bundle`** (final JSON):

```json
{
  "meta": {
    "generated_at": "2026-06-16T10:02:18Z",
    "llm_used": {"orchestrator": "gemini", "creative": "groq", "media_buying": "gemini"},
    "warnings": []
  },
  "product": {"type": "Luxury Watch", "description": "..."},
  "campaign": {"platform": "instagram", "objective": "MESSAGES", "tone": "..."},
  "creative": {
    "copies": [...], "headlines": [...], "cta": "Send Message",
    "visual_prompt": "...",
    "generated_images": ["<base64_png>"]
  },
  "media": {"budget_split": {...}, "daily_budget_usd": 71.43, "audience": {...}, ...}
}
```

---

## FastAPI Backend (`api.py`)

`api.py` exposes the full pipeline as a REST API with SSE streaming. It is the interface the Next.js frontend (`../web`) connects to. Internally it drives the LangGraph defined in `pipeline_graph.py` — all nodes, interrupts, and checkpointing live there.

### Starting the server

```bash
cd AutoMarkAi
uvicorn api:app --reload --port 8000
```

Interactive docs (Swagger UI): `http://localhost:8000/docs`

### Endpoints

| # | Method | Path | Tag | What it does |
|---|--------|------|-----|--------------|
| 1 | `GET` | `/health` | Utilities | Health check — returns `{"status": "ok"}` |
| 2 | `POST` | `/upload-image` | Utilities | Pre-upload a product image; returns `file_id` |
| 3 | `POST` | `/session` | Session | Create a new session; returns `session_id` |
| 4 | `POST` | `/session/{id}/start` | Session | Upload image + start pipeline; blocks until first interrupt (`questions`) |
| 5 | `GET` | `/session/{id}/stream` | Session | **SSE stream** — live progress events as the graph runs |
| 6 | `GET` | `/session/{id}/state` | Session | Current stage + interrupt data (no base64 blobs) |
| 7 | `GET` | `/session/{id}/images` | Session | Base64 ad images for the current stage or final bundle |
| 8 | `POST` | `/session/{id}/answers` | Human-in-the-loop | Submit answers to product questions; advances graph to image review |
| 9 | `POST` | `/session/{id}/image-decision` | Human-in-the-loop | Approve or regenerate the ad image |
| 10 | `POST` | `/session/{id}/pick-image` | Human-in-the-loop | Pick from history after max regenerations exceeded |
| 11 | `POST` | `/session/{id}/text-decision` | Human-in-the-loop | Approve or request changes to ad copy |
| 12 | `POST` | `/session/{id}/publish` | Publish | Publish campaign to Meta (requires stage `done`) |
| 13 | `GET` | `/session/{id}/result` | Publish | Final campaign bundle + publish result |

### Full request/response flow

```
POST /session                     → {"session_id": "..."}
POST /session/{id}/start          → {"stage": "questions", "data": {"questions": [...]}}
  (user reads questions)
POST /session/{id}/answers        → {"stage": "image_review", "data": {...}}
  (user views images via GET /session/{id}/images)
POST /session/{id}/image-decision → {"stage": "text_review", "data": {"copies": [...], "headlines": [...]}}
POST /session/{id}/text-decision  → {"stage": "done", "data": {}}
POST /session/{id}/publish        → {"success": true, "result": {"campaign": {...}, "ad": {...}, "post": {...}}}
GET  /session/{id}/result         → {"bundle": {...}, "publish_result": {...}}
```

### SSE streaming (Next.js example)

Connect to `/session/{id}/stream` with `EventSource` to receive live progress while the graph runs in the background. Events arrive between each POST call:

```javascript
const source = new EventSource(`http://localhost:8000/session/${sessionId}/stream`);
source.onmessage = (e) => {
  const event = JSON.parse(e.data);
  // event.event: "progress" | "interrupt" | "done" | "ping"
  // event.stage: "questions_ready" | "planning" | "creative" | "image_review" | "text_review" | "done" | ...
  console.log(event);
};
```

### Request body schemas

**`POST /session/{id}/start`** — multipart/form-data:
```
goal        string   "get WhatsApp leads for luxury watch"
budget      float    500.0
image_mode  string   "use_original" | "enhance_with_ai"
image       file     product photo (jpg/png/webp)
```

**`POST /session/{id}/answers`** — JSON:
```json
{"answers": {"0": "answer1", "1": "answer2", "2": "answer3", "3": "answer4"}}
```

**`POST /session/{id}/image-decision`** — JSON:
```json
{"action": "approve"}
{"action": "regenerate", "feedback": {"0": "make the background white"}}
```

**`POST /session/{id}/pick-image`** — JSON (only after `max_regenerations_exceeded`):
```json
{"chosen_index": 0}
```

**`POST /session/{id}/text-decision`** — JSON:
```json
{"action": "approve"}
{"action": "edit", "feedback": "Make the tone more urgent and shorten the copies"}
```

**`POST /session/{id}/publish`** — JSON:
```json
{"make_sponsored_ad": true, "make_organic_post": true}
```

---

## Testing the API (`test_api.py`)

`test_api.py` (project root) is an end-to-end test script that walks through the entire happy path automatically.

### Setup

```bash
# Install test dependency (if not already installed)
pip install Pillow requests
```

### Usage

```bash
# Terminal 1 — start the server
cd AutoMarkAi
uvicorn api:app --reload --port 8000

# Terminal 2 — run the full test
cd ..                        # back to project root
python test_api.py
```

### Options

```
--base-url    Server URL (default: http://localhost:8000)
--image       Path to a real product image (default: generates a synthetic test image)
--goal        Campaign goal text (default: "get WhatsApp leads for gaming keyboards")
--budget      Budget in USD (default: 500.0)
--image-mode  "use_original" or "enhance_with_ai" (default: "use_original")
```

**Examples:**

```bash
# Use a real product image
python test_api.py --image AutoMarkAi/tests/sample_input/watch.jpg --goal "sell luxury watches"

# Test the enhance_with_ai image mode
python test_api.py --image AutoMarkAi/tests/sample_input/keyborad.jpeg --image-mode enhance_with_ai

# Test against a deployed server
python test_api.py --base-url https://your-api.example.com
```

### What the test covers

| Step | Endpoint | Assertion |
|------|----------|-----------|
| 1 | `GET /health` | status == ok |
| 2 | `POST /upload-image` | returns file_id |
| 3 | `POST /session` | returns session_id |
| 4 | `POST /session/{id}/start` | stage == questions |
| 5 | `GET /session/{id}/state` | stage == questions |
| 6 | `POST /session/{id}/answers` | stage == image_review |
| 7 | `GET /session/{id}/images` | count > 0 |
| 8 | `POST /session/{id}/image-decision` | stage == text_review (or handles max_regen) |
| 9 | `POST /session/{id}/text-decision` | stage == done |
| 10 | `GET /session/{id}/result` | bundle present with product/campaign/media |
| 11 | `POST /session/{id}/publish` | returns success + campaign IDs |

The script prints colored status codes, elapsed time per step, generated questions, ad copies, and publish IDs. Expected total runtime: **2–5 minutes** (dominated by LLM + image generation calls).

---

## Meta Client (`meta_client.py`)

Wraps the Meta Marketing API v25.0 with two implementations behind a common interface.

### `get_meta_client()` — Factory function

Returns the active client based on `META_SIMULATION_MODE` in `.env`:

```
META_SIMULATION_MODE=true  (default) → SimulatedMetaClient
META_SIMULATION_MODE=false           → RealMetaClient
```

### `SimulatedMetaClient`

Returns realistic-looking fake responses (14-digit IDs, proper timestamps) with no network calls. Safe for development and demos — no credentials required.

### `RealMetaClient`

Calls the live Meta Marketing API v25.0 using the `facebook-business` Python SDK.

**Publish sequence:**

```
create_campaign(bundle)        → Campaign (PAUSED)
  └─ create_ad_set(bundle, campaign_id)    → AdSet (PAUSED, with targeting + bid)
       └─ create_ad_creative(bundle)       → AdCreative (uploads image to ad library)
            └─ create_ad(bundle, ...)      → Ad (PAUSED)
publish_post(bundle)           → Page Photo post (organic)
```

**Targeting built in `create_ad_set`:**

- `geo_locations.countries`: from `audience.locations` (ISO-3166-1 alpha-2), defaults to `["US"]`
- `flexible_spec.interests`: LLM-generated interest names resolved to Meta numeric IDs via the targeting search API
- `bid_strategy`: valid Meta API v25.0 values — `LOWEST_COST_WITHOUT_CAP`, `LOWEST_COST_WITH_BID_CAP`, `COST_CAP`
- Falls back to `LOWEST_COST_WITHOUT_CAP` if a capped strategy is chosen but no `bid_amount_usd` is provided

**Objective normalization:** LLM-generated objective strings (e.g. `MESSAGES`, `CONVERSIONS`) are automatically mapped to ODAX values (`OUTCOME_ENGAGEMENT`, `OUTCOME_SALES`, etc.).

---

## LLM Client (`llm_client.py`)

Four functions for different model types:

### `call_llm(prompt, system_prompt, node_name)` — Text generation

Used by `creative_node` and `media_buying_node`. Runs on Groq
(`llama-3.3-70b-versatile`). Gemini is reserved exclusively for image
generation, so there is no Gemini fallback for text.

```
Call Groq llama-3.3-70b-versatile
  ├── Success → return (text, "groq")
  └── Failure → raise RuntimeError
```

### `call_llm_vision(image_path, prompt, system_prompt)` — Image + text

Used by `orchestrator_node` and `question_generator_node`. Runs on Groq's
vision model (`meta-llama/llama-4-scout-17b-16e-instruct`); the image is
downscaled and sent as a base64 data URL.

### `generate_ad_images(prompt, n)` — Image generation

Used when `image_mode = "enhance_with_ai"` and no source image is available, or as fallback.

```
Call Gemini 3.1 Flash Image ("gemini-3.1-flash-image", Nano Banana 2) via google-genai SDK
  response_modalities=[TEXT, IMAGE]
  ├── Success → list of n base64-encoded PNG strings
  └── Failure → raise RuntimeError
```

### `enhance_ad_image(image_path, prompt, n)` — Image enhancement

Used by `creative_node` and `review_node` when `image_mode = "enhance_with_ai"`.

```
Load user's photo as PIL Image
Call Gemini 3.1 Flash Image with contents=[image, prompt]
  response_modalities=[TEXT, IMAGE]
  ├── Success → list of n base64-encoded PNG strings
  └── Failure → raise RuntimeError (creative_node falls back to generate_ad_images)
```

> Both functions share the same `_gemini_image_call()` helper. The model receives the user's actual photo as a real input (not just a style hint), so the enhanced image preserves the product subject while applying ad-ready styling and composition.

---

## Shared State (`state.py`)

All nodes communicate through a single `CampaignState` TypedDict. LangGraph passes this automatically.

```
START state         q_generator adds    orchestrator adds   sub-agents add      review adds         merge adds
───────────────     ───────────────     ─────────────────   ──────────────────  ──────────────      ──────────────
image_path      →   questions       →   campaign_plan   →   creative_output →   review_stage    →   campaign_bundle
image_mode          user_answers        llm_used            media_output        feedback
budget              errors              errors              llm_used
goal                                                        errors
```

**Special reducers:**

- `errors: Annotated[list, operator.add]` — errors from parallel nodes are **concatenated**, not overwritten
- `llm_used: Annotated[dict, _merge_dicts]` — dicts from parallel nodes are **merged**, not overwritten

**State fields:**

| Field | Type | Set by | Purpose |
| --- | --- | --- | --- |
| `image_path` | `str` | api.py (`/start`) | Path to user-uploaded temp image file |
| `image_mode` | `str` | api.py (`/start`) | `"use_original"` or `"enhance_with_ai"` |
| `budget` | `float` | api.py (`/start`) | Total campaign budget in USD |
| `goal` | `str` | api.py (`/start`) | Free-text campaign objective |
| `questions` | `list[str]` | question_generator_node | 4 product-specific questions |
| `user_answers` | `dict` | question_generator_node | Answers keyed by index string |
| `campaign_plan` | `dict` | orchestrator_node | Platform, objective, tone, etc. |
| `creative_output` | `dict` | creative_node | Copies, headlines, CTA, images |
| `media_output` | `dict` | media_buying_node | Budget split, targeting, bid strategy |
| `feedback` | `dict` | review_node | `{"creative": str}` for text redo |
| `review_stage` | `str` | review_node | `"redo_creative"` or `"done"` |
| `campaign_bundle` | `dict` | merge_node | Final assembled output |
| `errors` | `list` | all nodes | Concatenated error strings |
| `llm_used` | `dict` | LLM nodes | `{node_name: "gemini"|"groq"}` |

---

## Frontend (Next.js — `../web`)

The user-facing app is a conversational (chatbot) Next.js front-end in `../web`
that drives this backend over HTTP + SSE. It decomposes the backend's coarse
stages into fine conversational phases, but the **stage contract is the same**
one the API exposes:

| Backend stage | What the frontend shows | Resume call |
| --- | --- | --- |
| `questions` | Generated questions, asked one at a time | `POST /session/{id}/answers` |
| `image_review` | Ad image with approve / regenerate / "see all versions" | `POST /session/{id}/image-decision` |
| `max_regenerations_exceeded` | Gallery of the original photo + every previously generated image | `POST /session/{id}/pick-image` |
| `text_review` | Copies, headlines, CTA with approve / edit | `POST /session/{id}/text-decision` |
| `done` | Full campaign bundle + ad preview + publish button | `POST /session/{id}/publish` |

Run it with `cd ../web && npm install && npm run dev` (configure
`NEXT_PUBLIC_API_BASE` in `web/.env.local`). See `../web/README.md` for details.

---

## Setup

```bash
# 1. Enter the project directory
cd AutoMarkAi

# 2. (Optional) Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy the env template and fill in your API keys
cp .env.example .env
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

### Required

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Groq API key — used for **all** text and vision→text generation |
| `GEMINI_API_KEY` | Google AI Studio key — used **only** for ad image generation/enhancement |

### Optional (but recommended)

| Variable | Default | Purpose |
| --- | --- | --- |
| `NUM_GENERATED_IMAGES` | `1` | Number of ad image variants to generate |
| `MAX_REGENERATIONS_ALLOWED` | `2` | Max image re-enhancement retries in the review step |

### Meta API (only needed for real publishing)

| Variable | Purpose |
| --- | --- |
| `META_SIMULATION_MODE` | `true` = safe demo mode (default); `false` = live Meta API |
| `META_ACCESS_TOKEN` | User or system token with `ads_management` permission |
| `META_APP_ID` | From [developers.facebook.com](https://developers.facebook.com) |
| `META_APP_SECRET` | From [developers.facebook.com](https://developers.facebook.com) |
| `META_AD_ACCOUNT_ID` | Numeric ID without `act_` prefix |
| `META_PAGE_ID` | Facebook Page ID (used for ad creatives and organic posts) |
| `MAKE_SPONSORED_PAUSED_AD` | `1` = create the paused ad; `0` = skip (real mode only) |
| `MAKE_ORGANIC_POST` | `1` = create an organic page post; `0` = skip (real mode only) |

---

## API Keys

**Gemini API Key (required):**

1. Go to [https://aistudio.google.com](https://aistudio.google.com)
2. Sign in → click **Get API key**
3. Set `GEMINI_API_KEY=<your_key>` in `.env`
4. Free tier: ~15 RPM / 1,500 RPD for text+vision

**Groq API Key (optional — text fallback):**

1. Go to [https://console.groq.com](https://console.groq.com)
2. Sign up → **API Keys** → **Create API Key**
3. Set `GROQ_API_KEY=<your_key>` in `.env`
4. Free tier: ~30 RPM for `llama-3.3-70b-versatile`

**Meta API credentials (required for real publishing):**

1. Go to [https://developers.facebook.com](https://developers.facebook.com) and create an app
2. Add the **Marketing API** product
3. Generate a user access token with `ads_management`, `ads_read`, `pages_manage_posts`, `pages_read_engagement` permissions
4. Find your Ad Account ID in Meta Ads Manager (the number after `act_`)
5. Find your Page ID in your Facebook Page settings

> **Note on image generation:** Gemini 3.1 Flash Image (`gemini-3.1-flash-image`) may require billing enabled on your Google AI Studio account. If quota is exceeded, `creative_node` logs a warning and stores `generated_images: []` — the rest of the pipeline continues normally.

---

## Running the Backend + Frontend

Start the API:

```bash
uvicorn api:app --reload --port 8000
```

Then start the Next.js frontend in a second terminal:

```bash
cd ../web
npm install
npm run dev          # opens http://localhost:3000
```

The frontend guides you through every stage (Q&A → image review → copy review → publish).

**Demo mode (default):** Meta publish is simulated — no Meta credentials needed (`META_SIMULATION_MODE=true`).

**Live mode:** Set `META_SIMULATION_MODE=false` and fill in all Meta variables in `.env`.

---

## Running the CLI (fallback)

```bash
python main.py \
  --image ./tests/sample_input/watch.jpg \
  --budget 500 \
  --goal "get WhatsApp leads for luxury watch"
```

**Arguments:**

| Argument | Required | Description |
| --- | --- | --- |
| `--image` | Yes | Path to product image (`.jpg`, `.jpeg`, `.png`, `.webp`) |
| `--budget` | Yes | Total campaign budget in USD |
| `--goal` | Yes | Free-text description of the campaign objective |

The CLI skips question generation, review steps, and Meta publishing. On success, prints a summary and saves the bundle to `./output/campaign_bundle_<timestamp>.json`.

---

## Running Tests

```bash
pytest tests/ -v
```

All tests mock all LLM, image generation, and Meta API calls — **no API keys required**.

| Test file | What It Covers |
| --- | --- |
| `test_nodes.py` | Core pipeline nodes: orchestrator, creative, media buying, merge, Groq text |
| `test_new_nodes.py` | question_generator, the split review nodes (route/regen/pick/text paths), creative feedback redo |
| `test_meta_client.py` | SimulatedMetaClient returns correct structure; RealMetaClient calls SDK methods |

---

## Rate Limit Notes

The full pipeline makes up to **5 LLM calls per run** (more on redo passes):

| Call | Provider | Notes |
| --- | --- | --- |
| `question_generator_node` | Groq vision | 1 call |
| `orchestrator_node` | Groq vision | 1 call |
| `creative_node` (text) | Groq | 1 call per run |
| `creative_node` (image) | Gemini 3.1 Flash Image | 1 call; only in `enhance_with_ai` mode |
| `media_buying_node` | Groq | 1 call |

| Provider | Free Tier Limit | Behavior When Hit |
| --- | --- | --- |
| Groq llama-3.3-70b / llama-4-scout | ~30 RPM | Raises `RuntimeError` |
| Gemini 3.1 Flash Image | Billing-dependent | `generated_images` set to `[]`, pipeline continues |

---

## How to Extend

**Add a new node:**

1. Create `nodes/my_node.py` with a `my_node(state: dict) -> dict` function
2. Add prompt templates to `prompts/my_node.py`
3. In `pipeline_graph.py`: `builder.add_node("my_node", my_node)` and wire edges

**Add a new review step:**

1. Add a new interrupt-only node in `nodes/review.py` (keep any generation/side
   effects in a separate interrupt-free node so resumes never replay them)
2. Wire it into `pipeline_graph.py`
3. Add a new `POST /session/{id}/my-decision` endpoint in `api.py` (FastAPI)
4. Call `_assert_stage(session, "my_stage")` and `_advance(session, Command(resume=...))` inside it
5. Handle the new stage in the Next.js frontend (`../web`)

**Change the image generation model:**

- Edit `llm_client.py` — update the `GEMINI_IMAGE_MODEL` constant

**Change the LLM text / vision model:**

- Edit `llm_client.py` — update `GROQ_MODEL` or `GROQ_VISION_MODEL` constants

**Add a new output field:**

1. Return it from the relevant node
2. Add it to `CampaignState` in `state.py`
3. Include it in `campaign_bundle` inside `merge_node`
4. Expose it via `GET /session/{id}/result` in `api.py` and render it in the frontend

**Switch to real Meta publishing:**

1. Fill in all Meta variables in `.env`
2. Set `META_SIMULATION_MODE=false`
3. Use `MAKE_SPONSORED_PAUSED_AD=1` and `MAKE_ORGANIC_POST=1` to control what gets created

**Deploy the FastAPI backend:**

The API is a standard ASGI app — deploy with any ASGI-compatible host:

```bash
# Production server (no --reload)
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 1

# With gunicorn + uvicorn workers
gunicorn api:app -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

> Use `--workers 1` — the in-memory session store is not shared between processes. For multi-worker deployments, replace `_sessions` with a Redis-backed store.
