# AutoMark AI — Advanced Agentic Architecture Plan

> **Purpose.** This document is the implementation plan for evolving AutoMark AI
> from its current **linear, one-shot campaign builder** into the **advanced
> multi-agent media-buying system** described in
> [`real-estate-media-buying-plan.md`](real-estate-media-buying-plan.md).
>
> **What we keep.** The discovery interview's **mechanism** stays — the curated
> fixed-question list with optional LLM follow-ups (`nodes/question_generator.py`),
> which already plays the plan's *Discovery agent*. We are **enhancing**, not
> replacing it: making the interview as **efficient and complete** as possible so
> it asks every *critical* real-estate question and nothing it can infer
> (Section 5.2). It is **the first squad** of the new graph; everything
> downstream is rebuilt around it.
>
> **What we change.** The current pipeline ends at "build one campaign bundle and
> publish once." The new architecture turns that single shot into a **living,
> supervised loop**: research → plan → compliant creative → launch → diagnose →
> edit → act, with Meta's AI tried first and a manual fallback when it
> underperforms, all under step-by-step optional approval.

This plan is written against the **real codebase** (the files in
[`backend/`](backend/) and [`frontend/`](frontend/)), not a greenfield. It maps
every new capability to a concrete change in *this* project and gives a phased
path that never breaks the working demo.

---

## 0. Instructions for the implementing agent (read this first)

> This section turns the rest of the document from *architecture vision* into an
> *actionable brief*. Read it before writing any code.

### Build scope — what to implement now

**Implement only the demo footing.** Everything runs in a single FastAPI
process, in-memory, with `META_SIMULATION_MODE=true`. Do **not** introduce
Postgres, pgvector, Celery, Redis, AWS, RDS Proxy, Terraform, or any live Meta
spend. Where this document describes those (Sections 9, 13, 14 of the source
plan), treat them as the *future production target* and leave clearly marked
extension points (a function/interface), not implementations.

**Start with Phases 0 + 1 only** (Section 15). Do not attempt Phases 2–6 in the
same change. Each phase is a separate, reviewable deliverable.

### Do NOT touch (frozen carry-overs)

These already work and are explicitly out of scope for modification:

- `backend/nodes/question_generator.py` — keep the interview **mechanism**
  (fixed questions + at-most-one follow-up + the checkpoint-safe `gen`/`ask`
  split). You **may** add/refine the **question set** per Section 5.2
  (efficiency + critical coverage), but do not redesign *how* the interview
  works.
- `backend/real_estate_utils.py` — price-tier smart defaults.
- `backend/i18n.py` + `backend/templates/locales/` — the bilingual pattern. Any
  new user-facing string must be added in **both** `en/` and `ar/`.
- The HOUSING hard-overrides in `media_buying.py` / `merge.py` / `meta_client.py`
  — keep them working until the compliance gate (Phase 2) fully subsumes them.

### Environment facts (or the first test run will fail)

- **Run everything from the repo parent**, `d:\work\NTI\FinalProject_AutoMarkAI\`,
  because imports use the `AutoMarkAi.backend.…` package path.
- Run the backend as: `uvicorn AutoMarkAi.backend.api:app --reload` (from that
  parent dir — **not** from inside `backend/`).
- Run tests as: `python -m pytest AutoMarkAi/backend/tests` from that parent dir.
- **Regression bar:** the existing test suite (30 tests) must stay green after
  every phase. Add new tests for new behavior; never delete a passing test to
  make a change "pass."

### Prefer additive over reorg

Section 14 shows a target `agents/<squad>/` + `graph/` + `tools/` layout. **Do
not do a big-bang file move.** Instead:

- Add new squads as **new files** next to the existing `nodes/` (e.g.
  `nodes/supervisor.py`, `nodes/approvals.py`), keeping current imports intact.
- The directory reorg in Section 14 is the *eventual* shape; reach it later, one
  module at a time, only once the new structure has earned its keep. Treat it as
  aspirational, not a Phase-0 task.

### Uncertainties to resolve before coding (don't guess)

- The `facebook-business` SDK may not expose Advantage+ / Ad Library cleanly.
  For now, implement those **only against the simulated Meta client** with
  synthetic data; stub the real path behind the existing Sim/Real abstraction.
- Confirm the LangGraph version supports compiled sub-graphs-as-nodes; if not,
  keep the supervisor as a single router node with conditional edges (the
  existing pattern) rather than nested compiled graphs.

### Definition of done for the first hand-off (Phases 0 + 1)

1. A `supervisor_route(state)` function exists and the graph routes through it;
   the **routing change alone is behavior-preserving** (Phase 0 — the interview
   questions are sharpened separately in Phase 1).
2. The Discovery interview covers all **14 critical** real-estate questions
   (Section 5.2) and stays efficient (selects + smart-default inference + one
   follow-up); added questions are bilingual and the mechanism is unchanged.
3. `approval_mode` (`full_manual` | `guided` | `autopilot`) and a
   `request_approval()` helper exist; Guided mode runs the build with fewer
   stops; Full Manual reproduces today's interrupt set exactly.
4. `feature_flags` exist on state (even if most are unused yet).
5. Frontend shows an **Approval Queue** card and a `/mode` control; new strings
   are bilingual.
6. All existing tests pass; new tests cover `supervisor_route`, the
   approval-mode branching, and the expanded interview coverage.

---

## Table of contents

0. [Instructions for the implementing agent](#0-instructions-for-the-implementing-agent-read-this-first)
1. [Where we are vs. where we're going](#1-where-we-are-vs-where-were-going)
2. [Design stances (carried over + new)](#2-design-stances-carried-over--new)
3. [Target architecture overview](#3-target-architecture-overview)
4. [The supervisor graph (new topology)](#4-the-supervisor-graph-new-topology)
5. [The agent roster, mapped onto this codebase](#5-the-agent-roster-mapped-onto-this-codebase)
6. [Control plane: approval, autopilot, scheduler](#6-control-plane-approval-autopilot-scheduler)
7. [The Meta-AI-first / manual-fallback loop](#7-the-meta-ai-first--manual-fallback-loop)
8. [State schema evolution](#8-state-schema-evolution)
9. [Memory: short-term + long-term](#9-memory-short-term--long-term)
10. [Compliance & tracking (building on today's 3 layers)](#10-compliance--tracking-building-on-todays-3-layers)
11. [Tools & integrations](#11-tools--integrations)
12. [API & frontend impact](#12-api--frontend-impact)
13. [Persistence, background jobs & scheduling](#13-persistence-background-jobs--scheduling)
14. [Target repository layout](#14-target-repository-layout)
15. [Phased migration plan](#15-phased-migration-plan)
16. [What we deliberately keep from the old architecture](#16-what-we-deliberately-keep-from-the-old-architecture)
17. [Risks & mitigations](#17-risks--mitigations)

---

## 1. Where we are vs. where we're going

### Today (linear, one-shot)

The current graph ([`pipeline_graph.py`](backend/pipeline_graph.py)) is a single
forward pass that ends at publish:

```
target_gen → target_ask → question_gen ⇄ question_ask
  → orchestrator → strategy
  → fan-out (creative ‖ media_buying)
  → photo_select → text_review → merge → END → publish once
```

It builds **one** campaign and hands it to Meta. There is no concept of *launch
vs. test*, no reading results back, no daily decisions, no Advantage+-vs-manual
control, no memory across sessions, and no approval modes — the human is in the
loop only at three fixed interrupts (goal, photos, copy).

### Target (supervised, looping)

The new system keeps that build flow as its **"create a campaign" path** but
wraps it in a **supervisor** that also owns the *operate* lifecycle:

```
            ┌──────────────── SUPERVISOR (router + guardrails + decision log) ──────────────┐
            │                                                                                │
 Discovery ─┤→ Research → Plan → Creative → Compliance gate → Build → Launch/Schedule        │
 (KEPT)     │                                                      │                         │
            │                                          ┌───────────┴──────────┐              │
            │                                          ▼                      ▼               │
            │                                   See & Diagnose  ←──────  Edit & Act  ──┐       │
            │                                     (every cycle)        (after approval)│       │
            │                                          └──────────── loops back ───────┘       │
            └────────────────────────────────────────────────────────────────────────────────┘
                         Approval Gateway · Autopilot Orchestrator · Scheduler
```

The defining shift: **the campaign becomes a long-lived object the system
manages over days**, not a bundle it emits once. That single change is what
pulls in everything else in the plan (memory, scheduling, persistence,
diagnosis, the autopilot loop).

---

## 2. Design stances (carried over + new)

| # | Stance | Status |
|---|--------|--------|
| 1 | **Real estate first** — HOUSING rules, lead-gen funnel, EGP, Egyptian Arabic | ✅ already true; deepened |
| 2 | **Checkpoint-safe generation** — no side effects in interrupting nodes | ✅ keep as a hard rule everywhere |
| 3 | **Compliance as code** — HOUSING enforced programmatically | ✅ keep; promote to a dedicated squad in the critical path |
| 4 | **The playbook is the policy engine** — thresholds/decisions are named disciplines, not improvisation | 🆕 add a typed **policy store** + retrievable field-guide knowledge |
| 5 | **Meta's AI first, agents second** — Advantage+ default, manual fallback | 🆕 add the **Autopilot Orchestrator** |
| 6 | **Human in the loop, as much or as little as they want** — 3 approval modes | 🆕 add the **Approval Gateway** (today's 3 interrupts are the "Full Manual" subset) |
| 7 | **Money logic is deterministic; AI is for judgment** | 🆕 split budget/threshold/timer math into a non-AI **deterministic toolkit** |
| 8 | **Everything optional** — capabilities are switches | 🆕 add a **feature-flag / optionality** layer |

Stances 1–3 are *already* how the code is built; the migration's job is to add
4–8 without regressing them.

---

## 3. Target architecture overview

Four layers, each with one responsibility. This is the plan's Section 6 adapted
to our actual stack (FastAPI + LangGraph + Groq/Gemini + a Meta client with a
simulation mode), not the full AWS production footprint — which we keep as the
**north star** (Section 13) but reach in phases.

| Layer | Responsibility | In this codebase |
|-------|----------------|------------------|
| **Interface** | Chat intake, uploads, the **approval queue**, live status, reports | `frontend/` + `backend/api.py` (SSE) |
| **Orchestration (Supervisor)** | Route by phase & live state, enforce HOUSING/account-health guardrails before any Meta write, open approval interrupts, write the decision log | new `backend/graph/supervisor.py` wrapping today's `pipeline_graph.py` |
| **Squads (sub-graphs)** | Discovery, Research, Creative, Compliance & Tracking, Buying, Lifecycle & Experimentation, Analysis | `backend/nodes/` reorganized into `backend/agents/<squad>/` |
| **Tools** | Meta APIs, Gemini text/vision/image, web research, CRM delivery, **deterministic toolkit** | `backend/tools/` (formalizes today's `meta_client.py`, `llm_client.py`, `strategy_tools.py`) |
| **Memory & scheduling** | Checkpoints, rolling summary, long-term client memory, cadences | `backend/memory/` + a scheduler (Section 13) |

```
┌───────────────────────────┐      HTTP + SSE      ┌──────────────────────────────────────┐
│   Next.js Frontend         │ ───────────────────▶ │  FastAPI Backend                     │
│  chat · uploads · APPROVAL │ ◀─────────────────── │  ┌────────────────────────────────┐  │
│  QUEUE · status · reports  │                      │  │ SUPERVISOR (LangGraph)         │  │
└───────────────────────────┘                      │  │  routing · guardrails · log    │  │
                                                    │  └───┬───────────┬────────────┬───┘  │
                                                    │      ▼           ▼            ▼       │
                                                    │  Discovery   Research      Buying ... │
                                                    │  (KEPT)      Creative      Lifecycle  │
                                                    │              Compliance    Analysis   │
                                                    │  ┌──────── Control plane ───────────┐ │
                                                    │  │ Approval · Autopilot · Scheduler │ │
                                                    │  └──────────────────────────────────┘ │
                                                    └───────┬──────────┬───────────┬─────────┘
                                                            ▼          ▼           ▼
                                                       Groq (text)  Gemini      Meta API
                                                                    (vision/img) (sim/live)
                                                            │
                                                      Memory & checkpoints
                                                  (MemorySaver now → Postgres later)
```

---

## 4. The supervisor graph (new topology)

Today's graph is a fixed chain of edges. The new graph is a **supervisor +
sub-graphs**: the supervisor is a *router, not a worker*. It reads the shared
state and decides which squad runs next based on **phase** and **live condition**
(e.g. "this ad set is still in the learning phase → hold, skip optimization"),
pausing at the Approval Gateway whenever the active mode requires a decision.

```
                                   ┌─────────────┐
                          ┌───────▶│ SUPERVISOR  │◀────────┐  (re-entered each cycle;
                          │        │   router    │         │   resumes from checkpoint)
                          │        └──────┬──────┘         │
        phase=discovery   │               │ phase=*        │ phase=operate
                          │   ┌───────────┼───────────┐    │
                          │   ▼           ▼           ▼    │
                    ┌─────┴────┐   ┌──────────┐  ┌────────┴─────┐
                    │DISCOVERY │   │ RESEARCH │  │  LIFECYCLE   │
                    │ (KEPT:   │   │ audience │  │  diagnose →  │
                    │ target+  │   │competitor│  │  decide →    │
                    │ interview)│  │ trend    │  │  edit/act    │
                    └──────────┘   └────┬─────┘  └──────┬───────┘
                                        ▼               │
                                 ┌──────────┐           │
                                 │   PLAN    │          │ proposes actions
                                 │(orchestr.+│          ▼
                                 │ strategy) │   ┌──────────────┐
                                 └────┬──────┘   │ APPROVAL     │ (mode-gated)
                                      ▼          │ GATEWAY      │
                            ┌──────────────────┐ └──────┬───────┘
                            │ CREATIVE (copy,  │        ▼
                            │ photos, reference)│  ┌──────────┐
                            └────────┬─────────┘  │ EXECUTE   │ → Meta API
                                     ▼            │ (Meta     │   (sim/live)
                            ┌──────────────────┐  │ writes)   │
                            │ COMPLIANCE GATE  │  └──────────┘
                            │ (mandatory)      │
                            └────────┬─────────┘
                                     ▼
                            ┌──────────────────┐
                            │ BUILD + LAUNCH   │──▶ Autopilot Orchestrator
                            │ (or SCHEDULE)    │    (Advantage+ first)
                            └──────────────────┘
```

**Implementation note.** LangGraph supports this directly: each squad is a
**compiled sub-graph** added as a node; the supervisor is a node with
`add_conditional_edges` that returns the next squad's name from a deterministic
router function (AI only for genuinely ambiguous routing). The existing
`route_after_gen` / `_route_after_orchestrator` / `_route_to_subagents`
functions are the seed of this router — we generalize them into one
`supervisor_route(state)`.

The **build path** (Plan → Creative → Compliance → Build) is essentially
today's graph, lightly refactored. The **operate path** (Launch → Diagnose →
Edit/Act, looping) is entirely new and is what the rest of this document is
mostly about.

---

## 5. The agent roster, mapped onto this codebase

Each squad below names: what it does, the **existing file** it grows from (or
"new"), and whether it runs an LLM or is deterministic. Squads are sub-graphs so
each is independently testable.

### 5.1 Control plane

| Agent | Role | From |
|-------|------|------|
| **Supervisor** | Routes by phase/state; enforces guardrails before any Meta write; writes decision log | new `graph/supervisor.py` (generalizes today's route fns) |
| **Approval Gateway** | Pauses at each configured gate; surfaces a one-tap decision | new `graph/approvals.py` (today's 3 interrupts are its Full-Manual preset) |
| **Autopilot Orchestrator** | Owns Advantage+-first / manual-fallback loop | new `graph/autopilot.py` |
| **Scheduler** | Fires cadences (diagnosis, timer sweeps) + client-scheduled launches | new `workers/scheduler.py` |

### 5.2 Discovery squad — **KEPT mechanism, sharpened coverage**

| Agent | Role | From |
|-------|------|------|
| **Discovery agent** | Run the most **efficient, complete** real-estate interview: the curated fixed-question list + at most one LLM follow-up per topic. Keep the proven mechanism; ensure it covers every *critical* question and asks nothing it can infer. | `nodes/question_generator.py` — **enhance, don't replace the mechanism** |
| **Offer/Listing agent** | Structure the offer (off-plan vs ready, payment plan, USPs) from `real_estate_data` | new; reads interview output + `real_estate_utils.get_price_tier` |

> **Note.** There is **no separate data-analysis agent.** Turning the interview
> answers into the campaign plan is done directly by the orchestrator + strategy
> nodes (the Plan step in Section 4) — we do not need a dedicated analysis agent
> now.

**Discovery agent requirements (apply to `question_generator.py`):**

*Effective — ask every critical question.* A real-estate lead-gen campaign needs
all of the following before it can be planned well. Audit the current
`FIXED_QUESTIONS` and add whatever is missing:

| # | Critical question | Why it changes the campaign | In current set? |
|---|---|---|---|
| 1 | Campaign goal (leads / calls / viewings / awareness) | objective + optimization goal | ✅ asked first (`target_ask`) |
| 2 | Advertiser type (developer / brokerage / individual agent) | trust signals, copy voice, license display | ➕ add |
| 3 | Compound / project name | naming throughout | ✅ |
| 4 | Location (city/district + catchment) | geo-radius targeting | ✅ |
| 5 | Unit types | creative + audience framing | ✅ |
| 6 | Status: off-plan vs ready + delivery/handover timeline | urgency angle, payment framing | ➕ add (today only implied by payment plan) |
| 7 | Starting price (EGP) | drives the price-tier smart defaults | ✅ |
| 8 | Payment plan (down-payment %, installment years) | the #1 hook in EG real estate | ✅ |
| 9 | Standout features / amenities (USPs) | the message-match that does the targeting under HOUSING | ➕ add |
| 10 | Target buyer (investor / end-user / first-home / upgrader) | angle + tone, cross-checked against price tier | ➕ add |
| 11 | Current offer / promotion | the lead magnet | ✅ |
| 12 | Budget | deterministic budget/scaling math | ✅ asked separately |
| 13 | Campaign duration | daily budget = total ÷ duration | ✅ |
| 14 | Lead destination (WhatsApp / form / call / landing) | conversion location | ✅ |

*Efficient — ask the fewest questions that get there.* Completeness must not cost
friction:

- **Infer, don't ask.** Anything derivable from the price tier
  (`real_estate_utils.get_price_tier`) — tone, platform split, likely buyer,
  recommended offer — is a *smart default*, not a question. Only confirm when the
  inference is genuinely low-confidence.
- **Selects over typing.** Prefer `single_select` / `multi_select` with a
  **recommended** option and an "Other" escape, so most answers are one tap.
- **One follow-up max per topic**, and only when the answer is vague or reveals
  something worth exploring (keep the existing `_decide_follow_up` rule).
- **Never re-ask** what an uploaded asset or an earlier answer already supplied.
- **Order for momentum:** most-engaging first (goal, name, location), numbers and
  terms in the middle, lead destination + duration last.

Keep everything bilingual (en/ar) and keep the checkpoint-safe split
(`question_gen` generates, `question_ask` interrupts).

### 5.3 Research squad — **new**

| Agent | Role | LLM? |
|-------|------|------|
| **Audience agent** | HOUSING-compliant targeting: geo-radius, broad delivery, creative-as-filter, first-party retargeting pools — **never** demographics/ZIP | judgment + deterministic geo |
| **Competitor agent** | Mine Meta **Ad Library API** for running competitor housing ads (hooks, offers, formats, run-length = winner signal) | LLM synthesis |
| **Trend & Demand agent** | Seasonality / demand windows (paydays, launch seasons) feeding scheduling | LLM + web (`ENABLE_WEB_SEARCH` already exists) |

### 5.4 Creative squad — **grows from `nodes/creative.py`**

| Agent | Role | From |
|-------|------|------|
| **Creative Direction** | Concept/angle on AIDA, property-led | `nodes/creative.py` |
| **Copy agent** | Fair-housing-compliant AIDA copy + CTA; validators block preference language ("perfect for families"), hashtags in paid, excess emojis | `nodes/creative.py` + new validators |
| **Photo handling** | Use the agency's **real** unit photos; user picks which to feature | ✅ `nodes/review.py::photo_select_node` — keep |
| **(Optional) Image gen / reference regen** | Nano Banana behind a feature flag; off by default to preserve authenticity | new, flag-gated |

> **We keep the authenticity stance**: real photos remain the default and AI
> image generation stays **off** by default (Optionality matrix). The plan
> allows it as a switch; our default respects "buyers want the actual units."

### 5.5 Compliance & Tracking squad — **promotes today's HOUSING logic to a gate**

| Agent | Role | From |
|-------|------|------|
| **Compliance / Special Ad Category** | Declare HOUSING; enforce geo-radius, no demographics, fair-housing copy/visual checks; block evasion flags | consolidates the hard-overrides now in `media_buying.py` + `merge.py` + `meta_client.py` |
| **Lead Form agent** | Build Instant Forms (More Volume vs Higher Intent), qualifying questions, verification; read submissions | new |
| **Pixel & Events agent** | Verify Pixel/CAPI lead events, dedup, Event Match Quality, offline conversions | new (live mode) |

### 5.6 Buying squad — **grows from `nodes/media_buying.py`**

| Agent | Role | LLM? |
|-------|------|------|
| **Campaign Architect / Budget** | Leads objective; Advantage+ or manual structure; geo-radius ad sets; **deterministic** budget & scaling math (daily = total ÷ duration already exists in `merge.py`) | deterministic math + LLM structure |
| **Bid agent** | Bid strategy / cost controls aligned to target CPL | judgment |
| **Optimization agent (cadence)** | Pull metrics, compute lead-gen ratios, flag anomalies; **never act during learning** | mostly deterministic |

### 5.7 Lifecycle & Experimentation squad — **new, the heart of "operate"**

| Agent | Role |
|-------|------|
| **Lifecycle / Decision agent** | Daily continue / scale (+25%) / reduce / pause / restart-clean / reschedule decision in lead-gen terms; never stop-restarts a winner (Appendix B logic) |
| **Testing / Experiment agent** | Isolated-variable testing (budget, creative, location); minimum durations; Fix→Test→Analyze→Scale |
| **Retargeting agent** | Three first-party retargeting cases (form-openers, video viewers, past leads); kept manual for precision |

### 5.8 Analysis & Reporting squad — **new**

| Agent | Role |
|-------|------|
| **Reporting agent** | Plain-language daily report (CPL, qualified-lead rate, funnel, decisions + why) — **no jargon**, matching today's UX promise |
| **Insights agent** | Delivery rankings, retargeting-pool growth, creative-fatigue calls |
| **Landing / Funnel agent** | For website forms: on-site funnel drop-off; for Instant Forms: per-field drop-off |

---

## 6. Control plane: approval, autopilot, scheduler

### 6.1 Approval Gateway (generalizes today's interrupts)

Today the human is forced to decide at exactly three points. The Gateway turns
that into a **configurable mode**:

| Mode | Asks approval at… | Maps to |
|------|-------------------|---------|
| **Full Manual** | every step (plan, each creative, compliance, launch, every budget/pause/scale) | superset of today's 3 interrupts |
| **Guided (default)** | the plan, the final creative, and all money-moving/irreversible steps | the recommended default |
| **Auto-Pilot** | only spend changes above a threshold + new launches | proven clients |

**Implementation.** A small helper `request_approval(state, item)` that either
(a) raises a LangGraph `interrupt` with an approval payload (and the frontend
shows it in an **approval queue**), or (b) auto-approves and logs, depending on
`state["approval_mode"]` and the item's risk class (creative / money / schedule).
The existing `interrupt({...})` calls in `review.py` and `question_generator.py`
become the Full-Manual presets of this single mechanism.

### 6.2 Autopilot Orchestrator — see Section 7.

### 6.3 Scheduler

Drives the cadences that make "operate" possible — see Section 13. In the demo
(single process, in-memory) this is an `asyncio` task loop; in production it's
Celery beat / EventBridge. The graph itself is **cadence-agnostic**: the
scheduler just re-invokes the supervisor on a saved thread, which resumes from
the checkpoint — exactly the checkpoint-safe pattern we already rely on.

---

## 7. The Meta-AI-first / manual-fallback loop

This is the single biggest *new behavior* and the reason the plan exists. It is
owned by the **Autopilot Orchestrator**:

```
   ┌─ Launch on Advantage+ Leads (Meta AI: audience · placement · budget) ─┐
   │                                                                       │
   ▼                                                                       │
 Evaluate vs. the playbook's targets over the learning window              │
 (CPL · qualified-lead rate · exits learning · frequency · fatigue)        │
   │                                                                       │
   ├── meets/beats ──▶ KEEP on Advantage+, scale per playbook ─────────────┤
   │                                                                       │
   └── fails ───────▶ TAKE THE HAND: disable automation, rebuild manual    │
                      (geo-radius ad sets · isolated tests · manual loop)   │
                                          │                                 │
                       Retargeting ALWAYS manual (first-party pools)        │
                                          │                                 │
                       Reversible: hand back if a clean auto chance appears ┘
```

**Why it fits us.** The decision is **data-driven and deterministic** (compare
measured CPL/qualified-lead-rate against typed thresholds in the policy store),
which suits our "money logic is deterministic" stance. The Meta client already
abstracts simulation vs. live, so in **simulation mode** the orchestrator can be
demonstrated end-to-end with synthetic metrics — no live spend needed.

**Concrete additions:**
- `tools/meta/advantage_plus.py` — enable/disable Advantage+ on a campaign.
- `policy/thresholds.py` — typed CPL / qualified-lead-rate / learning-exit
  constants (the "book as policy engine").
- `agents/lifecycle/autopilot_decision.py` — pure function:
  `(metrics, policy) → KEEP | TAKE_HAND | HAND_BACK` + rationale.

---

## 8. State schema evolution

Today's `CampaignState` ([`state.py`](backend/state.py)) is built for a one-shot
build. The operate loop needs durable, evolving fields. **Additive** changes
(nothing removed, so the build path keeps working):

```python
# --- Operate lifecycle (new) ---
campaign_phase: str            # discovery | research | plan | creative |
                               # compliance | build | launch | operate
approval_mode: str             # full_manual | guided | autopilot
pending_approval: dict | None  # item awaiting a gate decision
feature_flags: dict            # optionality matrix (image_gen, video, retargeting…)

# --- Research (new) ---
audience_plan: dict            # geo-radius, retargeting pools, creative-as-filter
competitor_findings: list      # Ad Library hooks/offers/formats
demand_windows: list           # seasonality / payday windows

# --- Live campaign management (new) ---
control_mode: str              # advantage_plus | manual
metric_snapshots: list[dict]   # time-series CPL, qualified-lead rate, frequency…
learning_state: str            # learning | exited | unstable
decisions_log: list[dict]      # every action + rationale (audit trail)
lead_records: list[dict]       # delivered leads (hashed PII) + quality feedback

# --- Memory (new) ---
rolling_summary: str           # short-term, folds old turns
client_memory_ref: str | None  # pointer to long-term per-client store
```

The existing fields (`real_estate_data`, `campaign_plan`, `strategy_output`,
`creative_output`, `media_output`, `campaign_bundle`, `image_paths`,
`campaign_duration_days`, `lead_destination`, etc.) all remain.

---

## 9. Memory: short-term + long-term

Two layers, matching plan Section 9:

- **Short-term (within a thread)** — the graph state + a **rolling summary**,
  persisted by the checkpointer. We already use `MemorySaver`; we add a
  summarizer node that folds old interview/diagnosis turns into
  `rolling_summary` once a token threshold is crossed, so a weeks-long campaign
  stays cheap. Runs on the **cheap model tier**.
- **Long-term (across sessions)** — durable per-client knowledge: what they
  sell, their areas and price bands, which offers/creatives worked, their
  compliance constraints, past outcomes. Retrieved (semantic + recency) at the
  start of any new thread and injected into context, so Mark begins **already
  knowing the client**.

**Migration reality.** In the demo this is a JSON/SQLite store keyed by client;
in production it's pgvector in the shared Postgres. The interface (a
`memory.recall(client_id)` / `memory.merge(client_id, summary)` pair) is the
same in both, so the demo path doesn't have to be rewritten — only the backing
store swaps.

---

## 10. Compliance & tracking (building on today's 3 layers)

We **already** enforce HOUSING in three places (prompts → node hard-override →
Meta client declaration). The new architecture **doesn't replace this — it
promotes it to a first-class gate in the critical path** so nothing reaches a
Meta write without passing it:

1. **Keep** the prompt-level instructions, the `age_min=18 / age_max=65 /
   genders=["all"]` hard-override (now in `media_buying.py` + `merge.py`), and
   `special_ad_categories: ["HOUSING"]` in `meta_client.py`.
2. **Consolidate** them into one `agents/compliance/special_ad_category.py` gate
   node that runs **before BUILD** and re-validates the full campaign:
   targeting (geo-radius, no demographics, no ZIP/income), copy (no preference
   language, no personal-attribute "you" framing), and imagery (won't trip
   Meta's auto-detection as evasion).
3. **Add** the Lead Form + Pixel/CAPI checks (live mode) so lead events fire and
   deduplicate before spend.
4. **Per-market config.** Move the radius/restriction numbers into
   `compliance/<market>.json` so the rules are data, not code (today they're
   hard-coded for Egypt; this generalizes cleanly).

The compliance checklist (plan Appendix C) becomes an automated assertion list
the gate runs and logs.

---

## 11. Tools & integrations

Formalize today's clients into a `tools/` layer; **deterministic tools never
call a model**.

| Tool group | Purpose | From |
|------------|---------|------|
| **Meta Marketing API** | Create/manage campaigns, ad sets, ads; budgets, bids, schedules; read insights | `meta_client.py` (Sim + Real) |
| **Meta Ad Library API** | Competitor research (running ads, run-length) | new |
| **Meta Pixel + CAPI** | Lead-event tracking, dedup, offline conversions | new (live) |
| **Meta Lead Ads / Instant Forms** | Build + read native forms | new |
| **Advantage+ controls** | Toggle Meta AI for the autopilot loop | new |
| **Groq (text)** | Copy, strategy, media-buying, follow-up, diagnosis | `llm_client.py` |
| **Gemini (vision)** | Photo understanding, creative QC, housing-imagery awareness | `llm_client.py` |
| **Web research** | Trend/demand/competitor context | `strategy_tools.py` (`ENABLE_WEB_SEARCH`) |
| **CRM / Lead Center connector** | Real-time lead delivery + quality feedback | new |
| **Deterministic toolkit** | Budget/scaling math, thresholds, learning/timer checks, overlap detection | extract from `merge.py` + `strategy_tools.py` |

> **Model routing note.** The plan assumes one provider (Gemini, tiered). We keep
> our **Groq-text + Gemini-vision split** but adopt the plan's principle: a
> *cheap tier* for high-frequency low-judgment work (routing, summarization,
> reporting, follow-up decisions) and a *workhorse tier* for copy/synthesis/
> vision — with model IDs in config so they swap without code changes (we
> already have `GROQ_TEXT_MODEL`, `LLM_PROVIDER`).

---

## 12. API & frontend impact

### New / changed endpoints

| Endpoint | Purpose | Status |
|----------|---------|--------|
| `POST /session` … `/upload-asset` … `/start` | Intake + uploads | ✅ keep |
| `GET /session/{id}/stream` | SSE progress | ✅ keep, extend event types |
| `POST /session/{id}/answer` / `select-photos` / `text-decision` | Build-path interrupts | ✅ keep |
| `POST /session/{id}/approval` | **Resolve an Approval Gateway item** (approve/edit/reject) | 🆕 |
| `GET  /session/{id}/report` | Diagnosis + decisions report | 🆕 |
| `POST /session/{id}/mode` | Set approval mode / feature flags | 🆕 |
| `GET  /session/{id}/leads` | Delivered leads (live mode) | 🆕 |
| `POST /session/{id}/schedule` | Schedule a launch/post | 🆕 |

### Frontend

- The existing chat **stays the build experience**.
- Add an **Approval Queue** surface (a card type) — the Gateway's pending items
  with one-tap approve / edit / reject. This generalizes the existing
  `CopyCard` / `PhotoSelectGrid` decision components.
- Add a lightweight **campaign dashboard** (status, latest diagnosis, decisions
  log) for the operate loop — plain language, no CPL/CTR jargon in the default
  view (consistent with today's "no jargon" promise), with details on demand.
- New `ChatPhase`s: `research`, `compliance_review`, `live`, `diagnosis`,
  `approval`. The hook (`useCampaignChat`) gains a parallel "campaign is now
  running" mode.

---

## 13. Persistence, background jobs & scheduling

This is where the demo and the production target diverge — we name both so the
team knows the destination.

| Concern | Demo (now → next) | Production target (plan §10–14) |
|---------|-------------------|-------------------------------|
| Checkpoints | `MemorySaver` (in-memory) | Postgres checkpointer |
| Session store | in-memory dict in `api.py` | Postgres relational state |
| Long-term memory | JSON/SQLite | pgvector (hybrid retrieval) |
| Metrics history | in-state list | partitioned time-series tables + materialized views |
| Scheduler | `asyncio` loop | Celery beat (single) / EventBridge — exactly-once |
| Cadences | diagnosis on demand | 6-h optimization · daily diagnosis · ~15-min timer sweep |

**Cadences that the operate loop needs** (plan §11.1):

| Job | Cadence | Notes |
|-----|---------|-------|
| Metrics optimization | every 6 h | Meta read + snapshot; AI only on anomalies |
| Daily diagnosis | once/day after attribution settles | the Lifecycle decision per ad set |
| Timer sweep | ~15 min | scheduled launches due? scheduled scale-ups? |
| Conversation summarization | on end / threshold | structured summary → long-term memory |

**Key design point that makes this cheap & safe:** every cadence is just
"re-invoke the supervisor on this saved thread." Because interrupting nodes have
no side effects and generation is checkpoint-safe, a 6-hours-later wake-up
**resumes exact state** instead of rebuilding it — the same property that lets
today's pipeline resume an interview. We get the operate loop's durability *for
free* from a pattern we already enforce.

---

## 14. Target repository layout

The plan's monorepo (its §18) adapted to our two-service shape. `agents/` mirrors
the squads; `graph/` holds orchestration; deterministic logic and policy live
outside the agents.

```
AutoMarkAi/
├── backend/
│   ├── api.py                      # FastAPI: sessions, SSE, approvals, reports
│   ├── graph/
│   │   ├── supervisor.py           # router · guardrails · decision log
│   │   ├── approvals.py            # Approval Gateway (modes)
│   │   ├── autopilot.py            # Advantage+-first / manual-fallback loop
│   │   ├── state.py                # shared CampaignState (extended, §8)
│   │   └── checkpoints.py          # MemorySaver now → Postgres later
│   ├── agents/
│   │   ├── discovery/              # ★ question_generator.py (enhanced) + offer
│   │   ├── research/               # audience, competitor (Ad Library), trend
│   │   ├── creative/               # direction, copy(+validators), photo_select(KEPT)
│   │   ├── compliance/             # special_ad_category(GATE), lead_form, pixel_events
│   │   ├── buying/                 # campaign_architect/budget, bid, optimization
│   │   ├── lifecycle/              # decision, testing/experiment, retargeting
│   │   └── analysis/               # reporting, insights, funnel
│   ├── tools/
│   │   ├── meta/                   # marketing_api, ad_library, pixel_capi, lead_ads, advantage_plus
│   │   ├── llm/                    # groq(text) + gemini(vision) wrappers (from llm_client.py)
│   │   ├── research/               # web search/fetch
│   │   ├── crm/                    # lead delivery connector
│   │   └── deterministic/          # budget math, thresholds, timers, overlap
│   ├── memory/                     # rolling summary + long-term client store
│   ├── policy/                     # typed thresholds (CPL, learning-exit, scaling %)
│   ├── compliance/                 # per-market HOUSING rules (data, not code)
│   ├── real_estate_utils.py        # ★ price-tier smart defaults (KEPT)
│   ├── i18n.py / templates/        # ★ bilingual prompts + UI strings (KEPT)
│   └── tests/
├── frontend/                       # chat (KEPT) + Approval Queue + campaign dashboard
└── workers/                        # scheduler (asyncio now → Celery/EventBridge later)
```

★ = carried over from today essentially unchanged.

---

## 15. Phased migration plan

Each phase ships something demonstrable and **never breaks the working build
path**. This mirrors the plan's rollout (§19) but scoped to *this* codebase.

### Phase 0 — Introduce the supervisor (no behavior change, no file move)
- Add a single `supervisor_route(state)` (new file alongside `nodes/`, e.g.
  `nodes/supervisor.py`) and route `pipeline_graph.py` through it. **Do not move
  existing node files** — additive only (see Section 0). Optionally extract
  deterministic budget math into a `tools/deterministic/` helper *if* it can be
  done without touching node behavior.
- **Exit check:** all 30 existing tests still pass; demo behaves identically;
  new test covers `supervisor_route`.

### Phase 1 — Discovery sharpening + Approval Gateway + optionality
- **Sharpen the Discovery interview** per Section 5.2: audit `FIXED_QUESTIONS`,
  add the missing critical questions (advertiser type; status + delivery
  timeline; USPs/amenities; target buyer), and keep it efficient (selects +
  smart-default inference + one follow-up). Bilingual. Mechanism unchanged.
- Introduce `approval_mode` + `request_approval()`. Today's 3 interrupts become
  the Full-Manual preset; add Guided default. Add `feature_flags`.
- Frontend: Approval Queue card + a `/mode` control.
- **Exit check:** the interview covers all 14 critical fields; Guided mode runs
  the build with fewer stops; Full Manual reproduces today's interrupts exactly.

### Phase 2 — Compliance gate
- Consolidate HOUSING overrides into the `compliance/special_ad_category` gate
  in the critical path; move radius/rules into `compliance/egypt.json`.
- **Exit check:** no campaign can build without passing the gate; gate decisions
  are logged.

### Phase 3 — Research squad
- Add Audience (geo-radius + retargeting pools), Competitor (Ad Library), Trend
  agents. Feed `audience_plan` into media-buying.
- **Exit check:** plan cites competitor hooks + a defensible geo-radius.

### Phase 4 — Operate loop (the big one)
- Add Buying-as-Advantage+, the **Autopilot Orchestrator**, the **Lifecycle**
  decision agent, the **Optimization** cadence, and **Analysis/Reporting**.
- Add the scheduler (asyncio) + metric snapshots in state. Drive it all in
  **simulation mode** with synthetic metrics first.
- **Exit check:** a simulated campaign launches on Advantage+, gets diagnosed,
  and either scales or "takes the hand" — entirely without live spend.

### Phase 5 — Persistence & memory
- Swap `MemorySaver` → Postgres checkpointer; add long-term per-client memory
  (pgvector); move session store to Postgres.
- **Exit check:** a campaign survives a process restart and resumes; a returning
  client is recognized.

### Phase 6 — Live + production hardening
- Pixel/CAPI + Lead Forms + CRM delivery in live mode; circuit breaker + spend
  caps; observability; per-market config. Optional: image/video generation,
  Google Ads channel (flags).
- **Exit check:** plan §15 alarms fire correctly; spend is bounded.

---

## 16. What we deliberately keep from the old architecture

The new plan is production-grade but generic; these are the things *this*
product already does well, and they are **non-negotiable carry-overs**:

- **The discovery interview mechanism** — fixed questions + optional LLM
  follow-ups + the checkpoint-safe gen/ask split. We keep *how* it works and
  sharpen *what* it asks (Section 5.2): efficient, and complete on every critical
  real-estate question.
- **Price-tier smart defaults** (`real_estate_utils.py`) — starting price →
  buyer profile, tone, platform split, recommended offer. This is genuine
  domain logic the generic plan lacks; it feeds the Offer/Listing + Audience
  agents.
- **Authentic creative by default** — real unit photos, AI image generation
  **off** by default. The plan permits generation; our default keeps trust.
- **Checkpoint-safe generation** — costly LLM/vision calls never sit in
  interrupting nodes. This is exactly what makes the new operate-loop cadences
  cheap and safe; we generalize it, we don't abandon it.
- **Bilingual by design** — every prompt + UI string in English and Egyptian
  Arabic. All new agents inherit the `i18n` + `templates/locales/` pattern.
- **Simulation mode** — `META_SIMULATION_MODE`. This is now even *more* valuable:
  the entire autopilot/diagnose/act loop can be demoed end-to-end with synthetic
  metrics and zero live spend.
- **No-jargon UX** — plain language to the user (no CPL/CTR/ROAS in the default
  view). The new reporting agent keeps this promise; KPIs live under the hood.
- **The campaign bundle** — the structured `campaign_bundle` stays the build
  path's output; the operate loop adds live state alongside it, not instead.

---

## 17. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Big-bang rewrite breaks the working demo | Phased plan; Phase 0 is a no-behavior-change refactor; every phase keeps all tests green |
| HOUSING violation slips through during refactor | Compliance promoted to a **mandatory gate** in the critical path; existing 3-layer overrides kept until the gate subsumes them |
| Operate loop spends real money on a bad decision | Build & demo entirely in **simulation mode** first; deterministic thresholds; spend caps + circuit breaker before any live toggle |
| Acting during the learning phase | Deterministic `learning_state` guard defaults to **hold** |
| Cadences re-bill LLM calls on every wake-up | Checkpoint-safe pattern: generation in non-interrupting nodes; cadences only resume saved state |
| State schema churn | All §8 changes are **additive**; build path keeps its existing fields |
| Memory drift across sessions | Structured (not free-text) summaries, **merged** not appended, on a cheap model |
| Provider coupling (Groq/Gemini) | Keep model IDs in config; `tools/llm/` abstracts the split so a provider can be swapped |
| Single-process demo can't schedule reliably | `asyncio` loop now; documented path to Celery-beat-single / EventBridge for exactly-once in production |

---

## Closing note

The interview stays exactly as it is — it's the part that already works like a
real estate professional asking the right questions. Everything *after* it grows
from "emit one campaign and stop" into "**run the campaign like a media buyer**":
research the market, build it compliantly, launch on Meta's AI, watch the
numbers, and take the hand when the automation underperforms — under whatever
level of human approval the client wants. We get there in phases, each one
demonstrable in simulation mode, none of them breaking the build path we already
trust.