# Module 1 — Agentic Architecture of AutoMark AI

> **Purpose of this document.** This is a complete, plain-language explanation of how AutoMark AI’s multi-agent system is built and how it works. Read it top to bottom to understand the architecture, then use the section structure (and the “💡 Slide idea” callouts) to build the PowerPoint presentation. Each major section maps cleanly to one or two slides.

---

## Table of Contents

1. [The big idea in one paragraph](#1-the-big-idea-in-one-paragraph)
2. [Why a multi-agent system?](#2-why-a-multi-agent-system)
3. [The core framework: LangGraph](#3-the-core-framework-langgraph)
4. [Shared memory: the `CampaignState`](#4-shared-memory-the-campaignstate)
5. [The agent roster (19 agents)](#5-the-agent-roster-19-agents)
6. [The graph topology (how agents connect)](#6-the-graph-topology-how-agents-connect)
7. [The Supervisor (routing brain)](#7-the-supervisor-routing-brain)
8. [Human-in-the-loop: interrupts & approval modes](#8-human-in-the-loop-interrupts--approval-modes)
9. [The four phases of a campaign’s life](#9-the-four-phases-of-a-campaigns-life)
10. [Key design patterns](#10-key-design-patterns)
11. [The LLM layer (Gemini & Groq)](#11-the-llm-layer-gemini--groq)
12. [Compliance as a first-class citizen](#12-compliance-as-a-first-class-citizen)
13. [Memory & persistence](#13-memory--persistence)
14. [Observability: agent logging](#14-observability-agent-logging)
15. [End-to-end example walkthrough](#15-end-to-end-example-walkthrough)
16. [Summary: what makes this “agentic”](#16-summary-what-makes-this-agentic)

---

## 1. The big idea in one paragraph

AutoMark AI turns the messy, expert job of launching a real-estate ad campaign into a guided two-minute conversation. Instead of one giant AI prompt trying to do everything, the work is split among **19 specialised agents**, each an expert at one task — interviewing the client, analysing photos, researching competitors, writing copy, planning the budget, checking legal compliance, publishing to Meta, and monitoring performance. These agents are wired together as a **graph**: they pass a single shared “campaign file” between them, the system pauses to ask the human for decisions at the right moments, and a central **Supervisor** decides who runs next. The result feels like a single smart assistant, but under the hood it’s a coordinated team.

> 💡 **Slide idea:** One headline slide — *“From a 2-minute chat to a live Meta campaign, run by a team of 19 AI specialists.”*

---

## 2. Why a multi-agent system?

A single LLM prompt that tries to “make me an ad campaign” fails in practice: it hallucinates budgets, ignores legal rules, can’t pause for human approval, and is impossible to debug. AutoMark AI instead uses the **separation-of-concerns** principle that works in human organisations — give each part of the job to a dedicated specialist.

| Single-prompt approach ❌ | Multi-agent approach ✅ |
|---|---|
| One prompt does everything → unreliable | Each agent has one job → reliable and testable |
| No place to insert human approval | Natural pause points between agents |
| Hard to debug “what went wrong” | Inspect each agent’s input/output |
| Can’t enforce hard rules | Dedicated compliance & validation agents |
| All-or-nothing | Resume from where it paused |

> 💡 **Slide idea:** Side-by-side comparison table — *“Why not just one big prompt?”*

---

## 3. The core framework: LangGraph

The whole system is built on **LangGraph**, a framework for building stateful, multi-agent applications as a **graph**.

- **Nodes** = agents. Each node is a Python function that takes the shared state, does its job (often calling an LLM or an external API), and returns its updates.
- **Edges** = the flow. They define which agent runs after which. Edges can be **conditional** — a routing function decides the next agent based on the current state.
- **Shared state** = the single source of truth that flows through every node (see §4).
- **Interrupts** = the ability to pause the graph mid-run to wait for human input, then resume exactly where it left off.
- **Checkpointer** = saves the state at every step, so a paused conversation survives and can be resumed.

Think of it as a flowchart where every box is an AI specialist and the arrows are decisions about who goes next.

> 💡 **Slide idea:** *“LangGraph in 5 words: nodes are agents, edges are decisions.”* with the node/edge/state/interrupt icons.

---

## 4. Shared memory: the `CampaignState`

Every agent reads from and writes to **one shared dictionary** called `CampaignState` (defined in `state.py`). This is the system’s working memory — the “campaign file” that travels down the assembly line, each agent stamping its contribution onto it.

Selected fields, grouped by what produces them:

| Group | Fields (examples) | Written by |
|---|---|---|
| **Inputs** | `image_paths`, `budget`, `language`, `goal` | User / API |
| **Discovery** | `campaign_target_options`, `real_estate_data`, `lead_destination` | Interview agents |
| **Research** | `audience_plan`, `competitor_findings`, `demand_windows` | Research squad |
| **Plan** | `campaign_plan`, `strategy_output` | Orchestrator, Strategist |
| **Creative & media** | `creative_output`, `media_output` | Creative, Media-buying |
| **Final** | `campaign_bundle` | Merge agent |
| **Compliance** | `compliance_result` | Compliance agent |
| **Operate** | `metric_snapshots`, `latest_diagnosis`, `decisions_log`, `learning_state` | Lifecycle agents |
| **Published** | `meta_campaign_id`, `meta_adset_id` | Publish step |
| **Memory** | `rolling_summary`, `client_memory_ref` | Summarizer |

A subtle but important detail: some fields use **custom reducers** so that when agents run *in parallel*, their writes merge instead of overwriting each other. For example, `errors` accumulates (list-append) and `llm_used` merges (dict-merge).

> 💡 **Slide idea:** A diagram of the “campaign file” passing through agents, each adding a section. Title: *“One shared state, many contributors.”*

---

## 5. The agent roster (19 agents)

The agents are organised into **squads** by the stage of work they perform.

### 🗣️ Discovery squad — *understand the client*
| Agent (node) | Role |
|---|---|
| **`target_gen_node`** | Analyses the unit photos and suggests ranked campaign goals (leads, awareness, etc.), one recommended. |
| **`target_ask_node`** | Pauses to let the user pick the campaign goal. |
| **`question_gen_node`** | Runs a smart interview: asks a curated list of fixed questions (compound name, location, unit types, delivery status, price, offer, lead destination, duration), and generates **LLM follow-up questions** only when an answer is vague or interesting. |
| **`question_ask_node`** | Pauses to collect each interview answer. |
| **`summarizer_node`** | Compresses the conversation into a `rolling_summary` and recalls any long-term memory about a returning client. |

### 🔍 Research squad — *understand the market*
| Agent (node) | Role |
|---|---|
| **`audience_node`** | Builds a HOUSING-compliant audience plan: geo-radius around the project’s city, age 18–65, all genders, broad delivery (no demographic narrowing), price-tier profile. |
| **`competitor_node`** | Pulls live competitor real-estate ads from the **Meta Ad Library API** (or curated samples in simulation mode) — their hooks, offers, formats, and how long they’ve been running. |
| **`trend_node`** | Supplies Egypt’s seasonal real-estate demand windows (post-Eid, back-to-school, year-end) and payday timing, so launches hit peak demand. |

### 🧠 Planning squad — *decide the strategy*
| Agent (node) | Role |
|---|---|
| **`orchestrator_node`** | The planner. Uses **Gemini vision** to analyse the photos plus all interview answers, and produces the `campaign_plan` (product type, platform, objective, tone, price tier). |
| **`strategy_node`** (Strategist) | Builds the marketing strategy: target persona, channel split, messaging angles, and a timezone-aware posting schedule (computed by deterministic helpers so timing facts aren’t hallucinated). |

### 🎨 Creative & media squad — *build the ad*
| Agent (node) | Role |
|---|---|
| **`creative_node`** | Writes multiple ad copies, headlines, and a CTA. **Attaches the user’s real unit photos** — no AI-generated people (a hard, site-wide rule for real-estate authenticity). |
| **`media_buying_node`** | Plans budget split across Facebook/Instagram, bid strategy, optimisation goal, estimated reach, and daily budget — then hard-overrides any targeting that would break HOUSING rules. |

### ✅ Review & assembly squad — *human checks + finalise*
| Agent (node) | Role |
|---|---|
| **`photo_select_node`** | Pauses to let the user choose which uploaded photos go in the ad. |
| **`text_review_node`** | Pauses to let the user pick and edit the final copy + headline. |
| **`merge_node`** | Pure-Python (no LLM). Validates and assembles everything into the final `campaign_bundle` — enforcing limits (copy ≤125 chars, 3 headlines), CTA coherence, budget-split normalisation, and a final HOUSING audience override. |
| **`compliance_node`** | The legal gate. Validates the bundle against Meta’s HOUSING Special Ad Category rules (loaded from a per-market JSON file). If it fails, publishing is blocked. |

### 📈 Operate squad — *manage the live campaign*
| Agent (node) | Role |
|---|---|
| **`diagnose_node`** | Reads performance metrics (real Meta Insights, or synthetic in sim mode), computes cost-per-lead, lead quality, ad frequency, and the “learning” state — then writes a plain-language diagnosis. |
| **`decision_node`** | A pure decision function: given the metrics and the price-tier policy thresholds, it decides what to do (hold, scale up/down, pause, refresh creative, take/hand-back manual control) and **pauses for approval** before any money-moving action. |
| **`act_node`** | Executes the approved decision via the Meta client and records the outcome in the audit log. |

> 💡 **Slide idea:** A 2×3 grid of the six squads, each with its agents listed. Title: *“19 agents, 6 squads, one campaign.”*

---

## 6. The graph topology (how agents connect)

The agents are wired into a directed graph (in `pipeline_graph.py`). Here is the full flow:

```
                         ┌─────────── route_operate (entry router) ───────────┐
                         │                                                     │
              (discovery/build)                                          (operate)
                         │                                                     │
                         ▼                                                     ▼
            ┌─────────────────────────┐                          ┌────────────────────┐
   START →  │  target_gen_node        │                          │   diagnose_node    │
            │  target_ask_node  ⏸     │  ← pick campaign goal     │        ↓           │
            │  question_gen_node ⇄     │                          │   decision_node ⏸  │ ← approve action
            │  question_ask_node ⏸     │  ← interview loop         │        ↓           │
            │  summarizer_node        │                          │   act_node         │
            └───────────┬─────────────┘                          └─────────┬──────────┘
                        ▼                                                   ▼
            ┌─────────────────────────┐                                   END
            │  audience_node          │   RESEARCH SQUAD
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

   ⏸ = human-in-the-loop pause point
   ⇄ = loop (interview repeats until done)
```

Two things worth highlighting:

- **Parallel fan-out.** After the Strategist, the Creative and Media-buying agents run **at the same time** (LangGraph `Send`), because neither depends on the other. They reconverge at `merge_node`.
- **Two entry points, one graph.** A single routing function (`route_operate`) decides, on every invocation, whether this is a *new build* (start at the discovery squad) or a *live-campaign check-in* (jump straight to the operate squad). The same graph serves both the build flow and the ongoing management flow.

> 💡 **Slide idea:** Recreate the diagram above as a clean flowchart. This is the centrepiece architecture slide.

---

## 7. The Supervisor (routing brain)

The **Supervisor** (`nodes/supervisor.py`) is the system’s traffic controller. Crucially, it is a **pure router** — it never calls an LLM or an external API. It only reads the shared state and returns the **name of the next agent to run**. Its routing functions include:

- `route_operate` — entry router: build path vs. operate path.
- `route_after_orchestrator` — proceed to the Strategist only if a plan exists.
- `route_to_subagents` — fan out to Creative + Media-buying in parallel.
- `route_after_text_review` — loop back to Creative if the user rejected the copy, otherwise proceed to Merge.

This keeps decision-making centralised and cheap, and makes the flow easy to reason about and modify.

> 💡 **Slide idea:** *“The Supervisor decides WHO runs next — it never does the work itself.”*

---

## 8. Human-in-the-loop: interrupts & approval modes

A defining feature of AutoMark AI is that the human stays in control. LangGraph’s **`interrupt()`** mechanism lets an agent **pause the entire graph**, send a question to the frontend, and wait. When the user answers, the graph **resumes from that exact point** (thanks to the checkpointer) — no work is repeated.

There are five interrupt points (“gates”):

| Gate | Agent | What the user does |
|---|---|---|
| `campaign_target` | `target_ask_node` | Picks the campaign goal |
| `questions` | `question_ask_node` | Answers each interview question |
| `photo_select` | `photo_select_node` | Chooses which photos to use |
| `text_review` | `text_review_node` | Picks & edits the ad copy |
| `approval` | `decision_node` | Approves a money-moving operate action |

How often the system pauses is governed by the **approval mode**:

- **Full Manual** — every gate pauses for the user (maximum control). *This is the mode the web app uses.*
- **Guided** — routine choices are auto-picked; creative and money decisions still pause.
- **Autopilot** — the whole build runs unattended; only publishing needs the user.

A neat engineering detail: the agents are designed so that **expensive or irreversible actions never sit inside an interrupting node**. Generation happens in non-interrupting nodes; the interrupt only collects a decision. That makes pausing and resuming always safe.

> 💡 **Slide idea:** *“The AI proposes, the human approves.”* with the five gates and the three approval modes.

---

## 9. The four phases of a campaign’s life

The `campaign_phase` field tracks where a campaign is in its lifecycle:

1. **Discovery** — gather the brief (goal + interview).
2. **Build** — research, plan, create, validate, assemble.
3. **(Publish)** — the user launches it; real Meta IDs are saved.
4. **Operate** — the scheduler periodically re-enters the graph to diagnose and optimise the live campaign.

The **operate loop** is what makes the system feel autonomous after launch. A background **scheduler** (`workers/scheduler.py`) wakes up on cadences (metrics every 6 h, a daily diagnosis, a 15-minute timer sweep) and re-invokes the graph for any live campaign — which routes straight to `diagnose → decision → act`.

> 💡 **Slide idea:** A horizontal lifecycle bar: *Discovery → Build → Publish → Operate (∞ loop)*.

---

## 10. Key design patterns

These are the engineering ideas that make the architecture robust — good material for a “how it’s built well” slide.

1. **Specialised agents (separation of concerns)** — one job per agent.
2. **Shared-state blackboard** — all agents collaborate through one `CampaignState`.
3. **Central routing (Supervisor)** — flow logic is separate from work logic.
4. **Human-in-the-loop interrupts** — pause/resume at decision points.
5. **Checkpoint-safe nodes** — costly work is kept out of interrupting nodes, so resuming never double-charges or re-generates.
6. **Parallel fan-out** — independent agents (Creative + Media) run concurrently.
7. **Deterministic guards around LLMs** — facts that must be correct (budgets, timezones, compliance, char limits) are computed in plain Python, not left to the LLM.
8. **Defence-in-depth compliance** — the same rule (HOUSING) is enforced at five independent layers (see §12).
9. **Simulation/Live duality** — the same code runs with fake or real Meta calls behind one flag.
10. **Configurable LLM provider** — swap Gemini ↔ Groq via one env var.

> 💡 **Slide idea:** A “10 design principles” slide — these double as talking points for why the system is production-grade.

---

## 11. The LLM layer (Gemini & Groq)

All AI text generation goes through one module (`llm_client.py`) with a **configurable provider**:

- **Text generation** — `LLM_PROVIDER` selects **Gemini** (`gemini-2.5-flash`, default) or **Groq** (`openai/gpt-oss-120b`). Every text agent (interview, strategy, creative, media) uses this.
- **Vision (image understanding)** — always **Gemini**, because reading a photo needs a multimodal model. This powers the Orchestrator’s photo analysis.
- **Image generation** — a Gemini image model is available, but **not used for real-estate creative**: authenticity demands the agency’s real photos. A hard, non-negotiable rule strips any request to generate humans from every image prompt.

The module also includes resilient JSON parsing (LLMs sometimes wrap output in markdown), so structured agent outputs are reliable.

> 💡 **Slide idea:** *“One LLM gateway: Gemini for vision + text, Groq optional for text, no AI people in real-estate images.”*

---

## 12. Compliance as a first-class citizen

Real-estate ads fall under Meta’s **HOUSING Special Ad Category**, which **prohibits** targeting by age, gender, detailed demographics, or interests, and bans discriminatory copy. Violations get campaigns rejected or accounts banned. AutoMark AI therefore treats compliance as **defence-in-depth — five independent layers**:

1. **Prompt level** — the Creative and Media-buying prompts instruct the LLM on HOUSING rules.
2. **Media-buying override** — hard-sets age 18–65, all genders, removes income targeting.
3. **Merge override** — re-applies the HOUSING audience even over the Strategist’s persona.
4. **Compliance agent** — an explicit gate that checks targeting and copy against per-market rules and can **block publishing**.
5. **Meta client declaration** — declares `special_ad_categories: ["HOUSING"]` to Meta on the API call.

If any layer would be bypassed, the next one catches it. The compliance result is also surfaced to the user.

> 💡 **Slide idea:** A 5-layer shield diagram. Title: *“Compliance you can’t accidentally skip.”*

---

## 13. Memory & persistence

The system has **three kinds of memory**, intentionally separated:

| Type | What it holds | Where |
|---|---|---|
| **Working memory** | The current campaign’s `CampaignState` | LangGraph checkpointer (Postgres / SQLite / in-memory) |
| **Business records** | User accounts + every campaign with its Meta IDs and full plan | PostgreSQL tables (`users`, `campaigns`) |
| **Long-term client memory** | Summaries of a returning client’s past campaigns | `rolling_summary` + client store |

This separation matters: the **checkpointer** lets a paused conversation resume; the **business database** lets a user log in later and see all their campaigns on the *My Campaigns* page; the **client memory** lets Mark greet a returning client already knowing their history. Accounts use email/password with **bcrypt**-hashed passwords and **JWT** tokens.

> 💡 **Slide idea:** *“Three memories: resume the chat, remember the user, remember the client.”*

---

## 14. Observability: agent logging

Because debugging a 19-agent system is hard, AutoMark AI **wraps every agent** with a logger (`agent_logger.py`). During normal operation it records each agent’s **inputs, outputs, duration, interrupts, and errors** to timestamped files (`.agent_logs/run_*.log` and `.jsonl`). There’s also a standalone harness (`debug_agents.py`) that runs the pipeline in a terminal and prints each agent’s I/O step by step. This makes the system **transparent** — you can always answer “what did each agent see and produce?”

> 💡 **Slide idea:** *“Every agent’s thinking is logged — full transparency for debugging and analysis.”*

---

## 15. End-to-end example walkthrough

Putting it all together — what happens when a user creates a campaign for a compound called *“SouthMed”*:

1. **Login** → user authenticated, a campaign record is created.
2. **Chat** → language = Arabic, uploads 3 villa photos, budget = 500.
3. **Target agent** suggests goals; user picks *“Generate sales leads.”* ⏸
4. **Interview agents** ask: developer/brokerage? compound name? location? unit types? off-plan or ready? price? offer? lead destination? — with the occasional smart follow-up. ⏸ (each)
5. **Summarizer** compresses the brief.
6. **Research squad** pulls competitor ads from the Ad Library, builds a North-Coast geo audience, and notes the summer demand window.
7. **Orchestrator** reads the photos + answers → `campaign_plan` (premium tier, Instagram-led, MESSAGES objective).
8. **Strategist** builds the persona, channels, and Thursday-evening posting schedule.
9. **Creative + Media-buying** run in parallel: ad copies/headlines + the real photos; budget split + daily budget + bid strategy.
10. **Photo & copy review** → user selects photos and edits the headline. ⏸
11. **Merge** assembles the `campaign_bundle`; **Compliance** confirms HOUSING rules pass. ✅
12. **Publish** → real Meta campaign, ad set, creative, ad (paused) + organic post; Meta IDs saved to the user’s account.
13. **Operate loop** → days later, the scheduler diagnoses performance and proposes “scale budget +20%”, which the user approves. ⏸

> 💡 **Slide idea:** Turn these 13 steps into an animated build-up, or a single “journey” infographic.

---

## 16. Summary: what makes this “agentic”

AutoMark AI is genuinely *agentic* — not just an LLM with extra steps — because it has all the hallmarks:

- **Multiple autonomous specialists** that each decide how to do their own job.
- **A shared world model** (`CampaignState`) they collaborate through.
- **A planner/router** (Supervisor) that orchestrates them dynamically based on state.
- **Tool use** — real external actions: Gemini vision, Meta Ad Library, Meta Marketing API, a database.
- **Human-in-the-loop control** at the right moments.
- **A perception → planning → action → feedback loop** that continues after launch (the operate phase).
- **Guardrails** (compliance, validation, deterministic facts) so autonomy never means recklessness.

In one line: **AutoMark AI is a supervised team of AI specialists that perceives, plans, acts, and learns — to take a real-estate ad from a photo to a live, compliant, self-optimising Meta campaign.**

> 💡 **Closing slide idea:** The one-line summary above, over the squad diagram.

---

### Appendix — quick reference for the deck

**Tech stack:** LangGraph · FastAPI · Next.js/React · Google Gemini · Groq · Meta Marketing API · PostgreSQL.

**By the numbers:** 19 agents · 6 squads · 5 human gates · 5 compliance layers · 4 lifecycle phases · 3 memory types · 2 languages (EN/AR) · 1 shared state.

**Agent count breakdown:** Discovery 5 · Research 3 · Plan 2 · Creative/Media 2 · Review/Assembly 4 · Operate 3 = **19**.
