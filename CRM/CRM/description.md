# ORCAST — AutoMark AI CRM Agent: Technical Documentation

ORCAST is an AI-driven CRM agent built on FastAPI, LangGraph, and Google Gemini 2.5. It receives customer messages from three channels (Facebook Messenger DMs, Facebook Page Comments, and Vapi voice calls), routes them through a deterministic 10-node StateGraph, and responds with contextually grounded replies — optionally creating or updating HubSpot contacts, searching a hybrid RAG knowledge base, scoring leads, and escalating to human agents when warranted. All conversation state is persisted in PostgreSQL with rolling-summarisation, and every LLM call is traced through LangSmith.

---

## Table of Contents

1. [Architecture Diagram](#architecture-diagram)
2. [config.py — Application Settings](#configpy--application-settings)
3. [main.py — FastAPI Entry Point](#mainpy--fastapi-entry-point)
4. [app/graph/state.py — Shared Graph State](#appgraphstatepy--shared-graph-state)
5. [app/graph/orchestrator.py — Graph Builder](#appgraphorchestatorpy--graph-builder)
6. [app/graph/nodes.py — Node Implementations](#appgraphnodespy--node-implementations)
7. [app/graph/prompts.py — System Prompt and Tool Schemas](#appgraphpromptspy--system-prompt-and-tool-schemas)
8. [app/tools/hubspot_tool.py — CRM Dispatcher](#apptoolshubspot_toolpy--crm-dispatcher)
9. [app/tools/lead_scoring_tool.py — Deterministic Scorer](#apptoolslead_scoring_toolpy--deterministic-scorer)
10. [app/tools/handoff_tool.py — Human Escalation](#apptoolshandoff_toolpy--human-escalation)
11. [app/tools/rag_tool.py — Knowledge Base Search](#apptoolsrag_toolpy--knowledge-base-search)
12. [app/tools/messaging_tool.py — Channel Delivery](#apptoolsmessaging_toolpy--channel-delivery)
13. [app/services/gemini_service.py — Intelligence Layer](#appservicesgemini_servicepy--intelligence-layer)
14. [app/services/hubspot_service.py — HubSpot HTTP Client](#appserviceshubspot_servicepy--hubspot-http-client)
15. [app/memory/postgres_memory.py — Rolling-Summarisation Memory](#appmemorypostgres_memorypy--rolling-summarisation-memory)
16. [app/rag/embeddings.py — Gemini Embeddings Wrapper](#appragembeddingspy--gemini-embeddings-wrapper)
17. [app/rag/retriever.py — Hybrid Retriever](#appragretrieverpy--hybrid-retriever)
18. [app/rag/reranker.py — Gemini Reranker](#appragrerankpy--gemini-reranker)
19. [app/rag/ingest.py — Document Ingestion Pipeline](#appragragingspy--document-ingestion-pipeline)
20. [app/api/messenger.py — Messenger Adapter](#appapimessengerpy--messenger-adapter)
21. [app/api/facebook_comments.py — Page Comments Adapter](#appapiafacebook_commentspy--page-comments-adapter)
22. [app/api/vapi.py — Vapi Voice Adapter](#appapivapi_py--vapi-voice-adapter)
23. [tests/ — Test Suite](#tests--test-suite)
24. [Why These Techniques](#why-these-techniques)

---

## Architecture Diagram

```mermaid
flowchart TD
    %% Inbound channels
    MSG([Facebook Messenger DM]) -->|POST /messenger/webhook| MW[messenger.py\nnormalise]
    CMT([Facebook Page Comment]) -->|POST /messenger/webhook\nchanges.field=feed| FC[facebook_comments.py\nnormalise]
    VAP([Vapi Voice Call]) -->|POST /vapi/webhook| VP[vapi.py\nextract_event]

    MW --> RG[run_graph\norchestrator.py]
    FC --> RG
    VP --> RG

    %% Graph entry
    RG --> N1[memory_load\nload from PostgreSQL]

    N1 --> RD{status ==\n'escalated'?}
    RD -->|yes| AE[already_escalated\nreturn canned reply]
    RD -->|no| IC[intent_classify\nGemini with_structured_output]

    %% Intent routing
    IC --> IR{intent?}
    IR -->|crm_request| HN[hubspot_node\nfind_or_create_contact]
    IR -->|knowledge_question| RN[rag_node\nhybrid retrieval + rerank]
    IR -->|lead_qualification| LS[lead_scoring_node\ndeterministic score]
    IR -->|escalation| HD[handoff_node\nHubSpot note + DB record]
    IR -->|general_conversation| GR[generate_response\nGemini bind_tools]

    %% Post-scoring routing
    LS --> SQ{temperature ==\n'qualified'?}
    SQ -->|yes| HD
    SQ -->|no| GR

    HN --> GR
    RN --> GR
    HD --> GR
    AE --> SM

    GR --> SM[save_memory\nappend user + assistant turns]
    SM --> MN[messaging_node\nsend_reply to channel]
    MN --> END([END])

    %% External integrations
    HN -.->|HTTPS| HS[(HubSpot API\ncrm/v3/objects/contacts)]
    HD -.->|HTTPS| HS
    RN -.->|pgvector| PG[(PostgreSQL\ndocument_chunks)]
    SM -.->|asyncpg| PG2[(PostgreSQL\nconversations / leads)]
    GR -.->|LangChain| GM[Gemini 2.5 Flash\nChatGoogleGenerativeAI]
    IC -.->|LangChain| GM
    MN -->|voice TTS| GTS[Gemini TTS REST API]
    GTS -->|WAV| MSG
```

---

## config.py — Application Settings

### Overview

`config.py` is the single authoritative source for all configuration. Every other module imports `settings` from here. It uses `pydantic-settings` `BaseSettings`, which merges `.env` file values, environment variables, and typed defaults in one pass. The `.env` file path is resolved relative to `config.py`'s own location, not the process CWD — a deliberate choice so that `pytest` invoked from any directory picks up the same credentials.

### Line-by-line walkthrough

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
```
`pathlib.Path` is used to compute the absolute path to `.env`. `pydantic-settings` is the pydantic v2 successor to `pydantic.BaseSettings` — it validates and coerces all env values according to the annotated types.

```python
_ENV_FILE = Path(__file__).parent / ".env"
```
`__file__` resolves to the absolute path of `config.py` at import time, so `.parent` is always the `CRM/CRM/` directory. Alternatives rejected: `os.path.join(os.getcwd(), ".env")` is CWD-dependent and breaks when `pytest` is run from the project root.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
```
`case_sensitive=True` prevents `gemini_api_key` from accidentally matching `GEMINI_API_KEY`. `extra="ignore"` means unrecognised vars in `.env` are silently dropped rather than raising a `ValidationError` — important because the `.env` may carry personal shell exports.

```python
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = ""
    GEMINI_MODEL_FALLBACK: str = ""
    GEMINI_EMBEDDING_MODEL: str = ""
    GEMINI_TTS_MODEL: str = ""
```
Five Gemini model slots. `GEMINI_MODEL` is the primary (e.g. `gemini-2.5-flash`). `GEMINI_MODEL_FALLBACK` is tried if the primary throws. `GEMINI_TTS_MODEL` is separate because TTS models use a different endpoint and don't support standard `GenerationConfig` fields.

```python
    EMBEDDING_DIM: int = 768
```
768 is the output dimensionality forced on Gemini embedding REST calls. The HNSW index in PostgreSQL is created at this dimension; changing it requires dropping and recreating the index. pgvector supports up to 2000 dimensions for HNSW.

```python
    MAX_CONVERSATION_HISTORY: int = 20
    SUMMARIZATION_MESSAGE_THRESHOLD: int = 20
```
After 20 turns, `postgres_memory.summarize()` is triggered automatically. The rolling summary replaces the raw buffer, keeping the system prompt short and controlling token costs.

```python
if settings.GEMINI_API_KEY:
    os.environ.setdefault("GOOGLE_API_KEY", settings.GEMINI_API_KEY)
```
LangChain's `ChatGoogleGenerativeAI` reads `GOOGLE_API_KEY` from the environment. Setting it here means callers don't need to pass `google_api_key=` everywhere — though we still do for explicitness.

```python
os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.LANGCHAIN_TRACING_V2 else "false"
```
LangSmith tracing is opt-in. Writing the string `"false"` (not empty string) is required because LangChain's SDK checks for the string `"true"`.

---

## main.py — FastAPI Entry Point

### Overview

`main.py` wires together the FastAPI application, structured logging, lifespan startup/shutdown, and HTTP routers for all three channels. It also hosts admin and health endpoints gated behind `settings.DEBUG`. The file is intentionally thin — no business logic lives here.

### Line-by-line walkthrough

```python
def configure_logging() -> None:
    renderer = structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer()
    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.LOG_LEVEL)),
        ...
    )
```
`structlog` is chosen over stdlib `logging` for structured (key=value) log output that plugs into log aggregators (Datadog, CloudWatch) without parsing. `ConsoleRenderer` in development gives coloured, human-readable output. `JSONRenderer` in production emits one JSON object per log line. `make_filtering_bound_logger` drops log calls below `LOG_LEVEL` at the callsite rather than in a handler — zero overhead for suppressed levels.

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    from app.db import init_db
    await init_db()
    from app.graph.orchestrator import compiled_graph
    ...
    yield
    await close_pool()
```
`asynccontextmanager` lifespan replaces deprecated `@app.on_event("startup")`. `init_db()` creates tables (pgvector extension, `conversations`, `leads`, `escalations`, `document_chunks`) on first run — idempotent via `CREATE TABLE IF NOT EXISTS`. Importing `compiled_graph` at startup forces LangGraph to compile the `StateGraph` once; any wiring error surfaces immediately rather than on the first request. `sys.exit(1)` on DB failure prevents a partially-started server from silently accepting requests.

```python
app = FastAPI(
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)
```
`/docs` and `/redoc` are disabled in production to prevent schema enumeration. The Swagger UI is still available to developers locally.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],
    ...
)
```
CORS is wide-open in development (browser testing), closed in production. Meta and Vapi webhooks are server-to-server — they don't send CORS preflight — so this only affects browser-based admin tools.

```python
@app.get("/health/deep")
async def deep_health_check() -> dict:
    # checks PostgreSQL + pgvector chunk count + HubSpot HTTP reachability
```
The deep health check is called by deployment platforms (ECS, Railway, Render) to gate traffic. It distinguishes `"healthy"` (all checks pass) from `"degraded"` (some checks fail but the server is alive), allowing load balancers to keep the instance in rotation while surfacing partial failures.

```python
@app.post("/admin/simulate")
async def simulate_message(...) -> dict:
    message = UnifiedMessage(...)
    response = await run_graph(message)
```
`/admin/simulate` is the primary local testing endpoint — it bypasses all webhook signature verification and lets engineers inject arbitrary messages into the graph. Only reachable when `DEBUG=True`.

---

## app/graph/state.py — Shared Graph State

### Overview

`GraphState` is the single mutable object that flows through every LangGraph node. It is a `TypedDict` with `total=False`, meaning every key is optional. Nodes return partial dicts (`{**state, "key": new_value}`) rather than mutating state in place — LangGraph merges these partials into the accumulated state after each node completes.

### Key fields

| Field | Type | Purpose |
|---|---|---|
| `user_id` | `str` | Identifies the conversation; primary key in `conversations` and `leads` tables |
| `source` | `str` | `"messenger"` / `"facebook_comments"` / `"vapi"` — controls reply delivery |
| `input_type` | `str` | `"text"` / `"voice"` / `"image"` — voice input triggers TTS on reply |
| `user_message` | `str` | Always plain text, regardless of original media type |
| `intent` | `str` | Classified intent from `intent_classify` node |
| `intent_data` | `dict` | Structured extraction: `rag_query`, `crm_data`, `lead_signals`, `escalation_reason` |
| `tool_results` | `list[dict]` | Accumulates tool call results; fed to `generate_response` as context |
| `tools_called` | `list[str]` | Names of tools invoked this turn; returned in `AgentResponse` |
| `lead_profile` | `dict` | Merged view of the `leads` table row for this user |
| `response` | `str` | Final text set by `generate_response` or `already_escalated` |
| `escalated` | `bool` | True if this turn triggered a human handoff |
| `lead_updated` | `bool` | True if the leads table was written this turn |

```python
class AgentResponse(BaseModel):
    user_id: str
    source: str
    message: str
    tools_called: list[str]
    lead_updated: bool
    escalated: bool
    timestamp: datetime
```
`AgentResponse` is what `run_graph()` returns to channel adapters. It is a Pydantic model rather than a raw dict so callers get typed access and automatic serialisation in `/admin/simulate`.

---

## app/graph/orchestrator.py — Graph Builder

### Overview

`orchestrator.py` contains `build_graph()`, which wires all 10 nodes into a `StateGraph(GraphState)` and compiles it to a runnable. The compiled graph is a module-level singleton (`compiled_graph = build_graph()`) — this is the LangGraph equivalent of a FastAPI app object: built once, called many times. `run_graph()` is the single entrypoint for every channel adapter.

### Line-by-line walkthrough

```python
graph = StateGraph(GraphState)
graph.add_node("memory_load", nodes.memory_load)
# ... 9 more add_node calls
graph.set_entry_point("memory_load")
```
`StateGraph(GraphState)` binds the state schema to the graph at compile time. Every node must accept and return a `GraphState`-compatible dict. Adding all nodes before any edges is required — LangGraph validates all edge targets exist at compile time.

```python
graph.add_conditional_edges(
    "memory_load",
    nodes.route_after_memory,
    {"already_escalated": "already_escalated", "intent_classify": "intent_classify"},
)
```
`add_conditional_edges` takes a routing function (`route_after_memory`) that returns a string key, and a dict mapping keys to node names. This is the main extension point for adding new paths without touching existing nodes — add a key to the dict and a new node, leaving all existing paths unchanged.

```python
graph.add_edge("hubspot_node", "generate_response")
graph.add_edge("rag_node", "generate_response")
graph.add_edge("handoff_node", "generate_response")
```
Static edges for nodes that always proceed to `generate_response`. Using `add_edge` rather than `add_conditional_edges` makes the graph topology legible and avoids accidentally creating dead-end paths.

```python
graph.add_conditional_edges(
    "lead_scoring_node",
    nodes.route_after_scoring,
    {"handoff_node": "handoff_node", "generate_response": "generate_response"},
)
```
The only intra-flow branch: a qualified lead (score ≥ 80) skips directly from scoring to handoff. This avoids generating a response before escalating, which would confuse the customer.

```python
graph.add_edge("already_escalated", "save_memory")
graph.add_edge("generate_response", "save_memory")
graph.add_edge("save_memory", "messaging_node")
graph.add_edge("messaging_node", END)
```
The final three edges are always the same regardless of path. `save_memory` writes both turns before any delivery attempt, ensuring durability even if delivery fails.

```python
compiled_graph = build_graph()
```
LangGraph's `compile()` validates the graph (no orphan nodes, no missing edge targets, reachable `END`), then returns a `CompiledStateGraph` that can be `ainvoke`d concurrently.

```python
async def run_graph(message: UnifiedMessage) -> AgentResponse:
    initial_state: GraphState = {
        "user_id": message.user_id,
        "source": message.source,
        "input_type": message.input_type,
        "user_message": message.content,
        "metadata": message.metadata,
    }
    final_state = await compiled_graph.ainvoke(initial_state)
```
Only five keys are seeded — all others default to `None` or empty via `total=False`. `ainvoke` runs the graph to completion and returns the final accumulated state.

---

## app/graph/nodes.py — Node Implementations

### Overview

`nodes.py` implements the ten async functions that are registered as LangGraph nodes. Two of them (`intent_classify` and `generate_response`) make LLM calls; the rest are either pure Python or wrappers around tool functions. All accept an optional `RunnableConfig` parameter — required by LangGraph's node signature contract even when the config is not used — and are decorated with `@traceable` for LangSmith.

### memory_load (lines 116–128)

```python
async def memory_load(state: GraphState, ...) -> GraphState:
    memory = await postgres_memory.load(state["user_id"], source=state["source"])
    return {
        **state,
        "status": memory["status"],
        "summary": memory["summary"],
        "recent_messages": memory["recent_messages"],
        "lead_profile": memory["lead"],
        "tool_results": [],
        "tools_called": [],
        "escalated": False,
        "lead_updated": False,
    }
```
Resetting `tool_results` and `tools_called` to empty lists here prevents any stale state from a previous graph run leaking in (a risk when the compiled graph singleton is reused across concurrent requests). Each `ainvoke` call gets its own state dict, but defensive initialisation is cheap.

### route_after_memory (lines 131–134)

```python
def route_after_memory(state: GraphState) -> str:
    if state.get("status") == "escalated":
        return "already_escalated"
    return "intent_classify"
```
Short-circuits the entire graph for conversations already escalated to humans. This prevents the agent from re-classifying intents and taking actions on behalf of a customer who is waiting for a human — a bad user experience.

### intent_classify (lines 167–198)

```python
class _IntentOutput(BaseModel):
    intent: Literal["crm_request", "knowledge_question", "lead_qualification",
                    "escalation", "general_conversation"]
    rag_query: str = Field(default="")
    crm_data: dict = Field(default_factory=dict)
    lead_signals: dict = Field(default_factory=dict)
    escalation_reason: str = Field(default="")
```
`_IntentOutput` is the schema passed to `ChatGoogleGenerativeAI.with_structured_output()`. Using a `Literal` type for `intent` causes the LLM to return exactly one of the five allowed strings — the SDK enforces this at the JSON schema level before the response reaches Python. Alternative: manual JSON generation and `_parse_json()` is fragile and produces worse models when the schema is complex.

```python
    structured = llm.with_structured_output(_IntentOutput)
    result: _IntentOutput = await structured.ainvoke([HumanMessage(content=prompt)])
    intent = result.intent if result.intent in VALID_INTENTS else "general_conversation"
```
The membership check against `VALID_INTENTS` is a defensive guard against a future LLM version returning an unexpected value despite the schema. Edge case: if the LLM call raises (network error, quota), the `except` block defaults to `general_conversation`, preventing a graph crash.

```python
    parsed = {
        "intent": intent,
        "rag_query": result.rag_query,
        "crm_data": result.crm_data,
        "lead_signals": result.lead_signals,
        "escalation_reason": result.escalation_reason,
    }
    return {**state, "intent": intent, "intent_data": parsed}
```
`intent_data` is carried through the rest of the graph so downstream nodes (`hubspot_node`, `rag_node`, `lead_scoring_node`) can access the structured extraction without re-calling the LLM.

### hubspot_node (lines 215–269)

```python
    if lead.get("hubspot_contact_id"):
        operation = "update_contact"
        crm_data["contact_id"] = lead["hubspot_contact_id"]
    else:
        operation = "create_contact"
```
If we already have a HubSpot contact ID stored in memory, issue an update rather than a create. This prevents duplicate contacts across sessions for the same user. Edge case: if `create_contact` returns a contact ID (either from a new record or a dedupe hit), it is persisted back to the `leads` table so future turns find it.

```python
    if not result.get("success"):
        logger.warning("hubspot_node.skipped", reason=result.get("error", "unknown"))
        return {
            **state,
            "tool_results": state["tool_results"] + [{"tool": "crm_operation", "result": result}],
            "tools_called": state["tools_called"] + ["crm_operation"],
        }
```
On failure (e.g. HubSpot 403 from missing scopes), the failure result is added to `tool_results` so `generate_response` sees "the tool was already tried and failed" — preventing the LLM from retrying the same tool call in its own agentic loop. This was the fix for the retry storm observed in production.

### lead_scoring_node (lines 291–324)

```python
    result = score_lead(args)
    lead_updates = {
        "lead_score": result["score"],
        "lead_temperature": result["temperature"],
        ...
    }
    await postgres_memory.update_lead(state["user_id"], lead_updates)
```
`score_lead` is a pure function (no I/O, no LLM), so calling it directly in the node is safe. The result is immediately persisted before `route_after_scoring` runs — if the node crashes after `score_lead()` but before the return, the score is still saved.

### route_after_scoring (lines 327–331)

```python
def route_after_scoring(state: GraphState) -> str:
    lead = state.get("lead_profile") or {}
    if lead.get("lead_temperature") == "qualified":
        return "handoff_node"
    return "generate_response"
```
`lead_profile` is read from state (which was updated by `lead_scoring_node`) rather than re-queried from the DB. Temperature `"qualified"` corresponds to a score ≥ 80, meaning the lead has high budget, authority, engagement, and interest — ready for immediate human contact.

### generate_response (lines 368–472)

The most complex node. It runs up to `MAX_AGENT_ITERATIONS` (default 6) rounds of LLM + tool execution:

```python
    for _ in range(max(1, settings.MAX_AGENT_ITERATIONS)):
        result = await gemini_service.generate_with_tools(
            messages=[{"role": "user", "content": context_text}],
            tools=TOOLS,
            system_prompt=system_prompt,
        )
        calls = result.get("function_calls", [])
        if not calls:
            text = result["text"]
            break
        # ... dispatch tool calls ...
```
The loop breaks as soon as the LLM returns a text response with no tool calls. If the LLM exhausts all iterations still requesting tools, a plain `generate_text` fallback produces a response without tools. The final guard (`if not text`) returns a hardcoded apologetic message rather than an empty response — always better than silently failing.

Tool dispatch inside the loop is manual: each `call["name"]` is matched against known tool names and the corresponding function is called directly. This keeps LangGraph in full control of execution order — alternatives like `create_react_agent` hand tool dispatch to LangChain internals, which makes error handling and retry logic harder to reason about.

### save_memory (lines 479–488)

```python
    await postgres_memory.append_message(user_id, "user", state["user_message"], source=state["source"])
    await postgres_memory.append_message(user_id, "assistant", state["response"])
    if state.get("escalated"):
        await postgres_memory.update_status(user_id, "escalated")
```
Both turns are saved sequentially. If `update_status("escalated")` fails, the conversation is not marked escalated in the DB — the next turn will re-enter the graph normally rather than short-circuiting to `already_escalated`. This is acceptable: worst case, the escalation tool runs again and creates a second escalation record.

### messaging_node (lines 495–513)

```python
    if state["source"] == "vapi":
        return state
```
Vapi is synchronous: the response is returned directly in the HTTP body of the webhook response. `messaging_node` would attempt to call an outbound API that doesn't exist for Vapi. The short-circuit here avoids a NOP API call.

---

## app/graph/prompts.py — System Prompt and Tool Schemas

### Overview

`prompts.py` holds the system prompt template, a channel-rule factory, and the four `StructuredTool` stubs used as schema descriptors for `bind_tools()`. No tool in this file is ever actually called by LangChain — execution is handled manually in `generate_response`.

### Tool schema pattern

```python
def _stub(*args, **kwargs):
    raise RuntimeError("Tool stubs must not be called directly.")

TOOLS = [
    StructuredTool(name="search_knowledge_base", func=_stub, coroutine=_stub, args_schema=...),
    StructuredTool(name="crm_operation", func=_stub, coroutine=_stub, args_schema=...),
    StructuredTool(name="score_lead", func=_stub, coroutine=_stub, args_schema=...),
    StructuredTool(name="escalate_to_human", func=_stub, coroutine=_stub, args_schema=...),
]
```
`bind_tools(TOOLS)` tells the LLM what tools exist and what their arguments look like. The actual function pointers (`func`, `coroutine`) would normally be the callables LangChain invokes — but here they are stubs that raise if called, making it impossible to accidentally let LangChain execute a tool. Alternatives rejected: `Tool` objects with real function pointers would let LangChain execute tools on its own schedule, bypassing the graph's audit log and retry logic.

### System prompt

```python
_SYSTEM_PROMPT_TEMPLATE = """You are ORCAST — an AI sales and CRM assistant for {company_name}.
...
## Responsibilities
1. Answer questions about our products, pricing, and policies using the knowledge base.
2. Collect and save customer contact details to the CRM.
3. Qualify leads by assessing budget, authority, engagement, and interest.
4. Escalate frustrated, high-value, or explicitly requesting-human customers.
5. Respond in the same language as the customer. Auto-detect language.

{channel_rule}

## Lead Profile (current)
{lead_profile_json}

## Conversation Context
{context_block}
"""
```
The lead profile and conversation context are injected per-turn. `hubspot_contact_id` and `hubspot_deal_id` are redacted before injection — they are internal identifiers the LLM has no use for and which could be misused if extracted.

```python
def _channel_rule(source: str, input_type: str) -> str:
    if source == "vapi":
        return "CHANNEL: Voice call. Respond in AT MOST TWO SHORT SENTENCES."
    if source == "messenger" and input_type == "voice":
        return "CHANNEL: Voice message. Reply will be converted to speech."
    if source == "facebook_comments":
        return "CHANNEL: Public Facebook comment. NEVER include personal contact details."
    return ""
```
Channel-specific constraints prevent the LLM from giving lengthy responses to voice callers (who can't skim) or including private data in public-facing comment replies.

---

## app/tools/hubspot_tool.py — CRM Dispatcher

### Overview

`crm_operation` is the single public function. It is a thin dispatcher over `hubspot_service`, converting string operation names to method calls. The `@traceable` decorator records every call to LangSmith, including the `operation` and `data` arguments — useful for debugging which contacts were created or updated.

```python
@traceable(name="crm_operation")
async def crm_operation(operation: str, data: dict[str, Any]) -> dict[str, Any]:
    if operation == "create_contact":
        return await hubspot_service.find_or_create_contact(data)
    elif operation == "update_contact":
        return await hubspot_service.update_contact(data)
    # ... etc
    else:
        return {"success": False, "error": f"Unknown operation: {operation}"}
```
All paths return a consistent `{"success": bool, ...}` dict. Callers check `result.get("success")` rather than catching exceptions — this makes retry logic in nodes explicit and predictable.

---

## app/tools/lead_scoring_tool.py — Deterministic Scorer

### Overview

`score_lead` computes a 0–100 lead score from four weighted factors. It is a pure function — no I/O, no LLM, no network — and returns immediately with a deterministic result. This was an intentional design decision: lead scoring needs to be reproducible and auditable; a model-based scorer would produce different scores for the same inputs across versions.

### Score formula

```
score = budget × 0.35 + authority × 0.30 + engagement × 0.20 + interest × 0.15
```

| Factor | Source | Raw range | Why this weight |
|---|---|---|---|
| `budget` | LLM-extracted enum | lookup table 5–100 | Biggest predictor of deal value |
| `authority` | LLM-extracted enum | lookup table 5–100 | Decision-maker contacts close faster |
| `engagement_level` | LLM-extracted int 0–10 | ×10 = 0–100 | Correlated with intent to purchase |
| `interest_level` | LLM-extracted int 0–10 | ×10 = 0–100 | Softer signal; lowest weight |

```python
assert abs(W_BUDGET + W_AUTHORITY + W_ENGAGEMENT + W_INTEREST - 1.0) < 1e-9
```
Module-level assertion catches accidental weight drift during refactors. It runs at import time, not inside the function — failed imports are louder than silent wrong scores.

### Temperature thresholds

```python
def _temperature(score: int) -> str:
    if score >= 80: return "qualified"
    if score >= 60: return "hot"
    if score >= 30: return "warm"
    return "cold"
```
`"qualified"` is the only temperature that triggers automatic escalation via `route_after_scoring`. The 80-point threshold requires at least two high-scoring factors simultaneously — preventing premature escalation on a single strong signal.

### Input validation

```python
class LeadScoringInput(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    budget: str = Field(default="unknown")
    engagement_level: int = Field(default=0, ge=0, le=10)
```
`EmailStr` validates email format. The `phone` validator strips formatting characters and requires 7–15 digits — matching the ITU-T E.164 range without requiring country-code format.

---

## app/tools/handoff_tool.py — Human Escalation

### Overview

`escalate_to_human` performs three actions atomically from the caller's perspective: creates a HubSpot note on the contact, optionally advances the associated deal stage, and writes an escalation record to PostgreSQL. Each action is independent — if HubSpot note creation fails, the PostgreSQL escalation record is still written.

```python
if lead.get("hubspot_contact_id"):
    note_id = await hubspot_service.create_note(
        lead["hubspot_contact_id"], "CONTACT",
        _build_note_body(user_id, reason, priority, notes, lead)
    )
```
The note body includes priority, user ID, reason, lead score, and contact details — everything a human agent needs to pick up the conversation without reading the full transcript.

```python
if lead.get("lead_temperature") == "qualified" and lead.get("hubspot_deal_id"):
    await hubspot_service.update_deal(
        {"deal_id": lead["hubspot_deal_id"], "dealstage": QUALIFIED_DEAL_STAGE}
    )
```
`QUALIFIED_DEAL_STAGE = "qualifiedtobuy"` is the HubSpot internal stage ID for the default pipeline. If the company uses a custom pipeline, this constant must be updated to match the internal stage ID from HubSpot's pipeline settings.

```python
escalation_id = await postgres_memory.create_escalation(
    user_id=user_id, reason=reason, priority=priority, hubspot_note_id=note_id
)
```
`create_escalation` also sets `conversations.status = 'escalated'` in the same DB transaction, which is what `route_after_memory` checks on subsequent turns.

---

## app/tools/rag_tool.py — Knowledge Base Search

### Overview

`search_knowledge_base` is a three-stage pipeline: hybrid retrieval → Gemini reranking → LCEL answer generation. The stages are composed using LangChain's abstractions (`BaseRetriever`, `BaseDocumentCompressor`, LCEL `|` operator), making each independently replaceable.

### Stage 1: Hybrid retrieval

```python
docs = await hybrid_retriever.ainvoke(query)
```
`hybrid_retriever` runs dense (pgvector HNSW cosine similarity) and sparse (PostgreSQL TSVECTOR) search in parallel via `asyncio.gather`, then fuses the two ranked lists with Reciprocal Rank Fusion (RRF). See the retriever section below.

### Stage 2: Reranking

```python
reranked = list(await gemini_reranker.acompress_documents(docs, query))
```
`acompress_documents` is the LangChain `BaseDocumentCompressor` interface. The Gemini backend prompts the model to return a JSON array of re-ordered indices; the cross-encoder backend uses `sentence-transformers`. Using the standard interface means the reranker can be swapped via `RERANKER_BACKEND` config without touching this file.

### Stage 3: LCEL answer generation

```python
_chain = _prompt | _llm | StrOutputParser()
answer = await _chain.ainvoke({"context": context, "question": query})
```
The LCEL chain is a module-level singleton — `_llm` is not re-instantiated per request. `StrOutputParser()` strips the `AIMessage` wrapper and returns a plain string. The prompt instructs the model to return the sentinel `"INSUFFICIENT_CONTEXT"` rather than hallucinating when the retrieved chunks don't answer the question.

```python
if not answer or "INSUFFICIENT_CONTEXT" in answer:
    return {"found": False, "answer": NO_INFO_RESPONSE, ...}
```
Returning `found: False` with a fixed `NO_INFO_RESPONSE` string prevents the LLM in `generate_response` from seeing a hallucinated answer. The `NO_INFO_RESPONSE` also promises human follow-up, maintaining trust even when the knowledge base doesn't have the answer.

---

## app/tools/messaging_tool.py — Channel Delivery

### Overview

`send_reply` routes a completed response back to whichever channel the message originated from. For Messenger voice turns, it attempts TTS synthesis and audio delivery before falling back to text. For Vapi, it is a no-op (the response is returned in the HTTP body).

```python
def _retry_on_failure():
    return retry(
        retry=retry_if_result(lambda result: not result.get("success", False)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry_error_callback=lambda retry_state: retry_state.outcome.result(),
    )
```
Retries on API-level failures (Messenger Send API returning `{"success": False}`) rather than exceptions. `retry_error_callback` returns the last result rather than raising, so callers always get a dict back. `wait_exponential` with max=4s avoids hammering Meta's API during transient outages.

```python
async def _send_messenger_reply(message: UnifiedMessage, text: str) -> dict:
    if message.input_type == "voice":
        tts = await gemini_service.synthesize_speech(text)
        if tts:
            audio_bytes, audio_mime = tts
            result = await messenger_adapter.send_voice_reply(message.user_id, audio_bytes, audio_mime)
            if result.get("success"):
                return result
            logger.warning("messaging_tool.voice_reply_failed_fallback_text", ...)
    result = await messenger_adapter.send_message(message.user_id, text)
```
The voice path is attempted first but is not required to succeed. Falling back to text ensures the customer always gets a response, even if TTS or Messenger audio upload fails. The fallback is logged as a warning (not an error) to distinguish intentional graceful degradation from true failures.

---

## app/services/gemini_service.py — Intelligence Layer

### Overview

`GeminiService` is the unified Gemini interface. Text generation and tool-calling use `ChatGoogleGenerativeAI` (LangChain) for automatic LangSmith tracing. Multimodal operations (audio transcription, image description, PDF extraction, TTS) use the raw `google-generativeai` SDK because LangChain's multimodal interface doesn't handle raw binary payloads natively.

### UnifiedMessage

```python
class UnifiedMessage(BaseModel):
    user_id: str
    source: str          # "messenger" | "facebook_comments" | "vapi"
    input_type: str      # "text" | "voice" | "image" | "document"
    content: str         # always plain text
    timestamp: datetime
    metadata: dict[str, Any]
```
By the time a `UnifiedMessage` reaches the graph, all media has been converted to text. This abstraction means the graph nodes never handle binary data or channel-specific payload formats.

### generate_text (lines 113–125)

```python
    for model_name in (settings.GEMINI_MODEL, settings.GEMINI_MODEL_FALLBACK):
        try:
            llm = self.get_chat_model(model_name, temperature)
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            return (response.content or "").strip()
        except Exception as exc:
            logger.warning("gemini_service.generate_text.error", model=model_name, error=str(exc))
    return ""
```
Falls back to `GEMINI_MODEL_FALLBACK` on any exception. Returns `""` only if both models fail — callers handle empty strings as a degraded state rather than crashing.

### transcribe_audio (lines 180–194)

```python
    _VIDEO_TO_AUDIO = {"video/mp4": "audio/mp4", "video/mpeg": "audio/mpeg", "video/webm": "audio/webm"}
    mime_type = _VIDEO_TO_AUDIO.get(mime_type, mime_type)
```
Messenger's CDN delivers voice notes with `Content-Type: video/mp4` because they're recorded with a video codec container even though they contain only audio. Gemini's multimodal API rejects `video/*` MIME types when the request is clearly audio-only — normalising to `audio/*` resolves the 400 error.

### synthesize_speech (lines 221–269)

```python
    payload = {
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}},
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, params={"key": settings.GEMINI_API_KEY})
```
Uses raw httpx rather than the LangChain SDK because `ChatGoogleGenerativeAI` does not support `responseModalities: ["AUDIO"]` in `GenerationConfig` — the SDK's `GenerationConfig` class raises `Unknown field: response_modalities` on that key. The REST API accepts it as camelCase without issue.

```python
    if "L16" in mime or "pcm" in mime.lower():
        rate = int(mime.split("rate=")[1].split(";")[0].strip())
        raw = _pcm_to_wav(raw, sample_rate=rate)
        mime = "audio/wav"
```
Gemini TTS returns raw PCM (`audio/L16;rate=24000`) — headerless, uncompressed 16-bit samples. Messenger's Send API requires a recognised audio file format. `_pcm_to_wav()` wraps the bytes in a standard RIFF/WAV container using Python's stdlib `wave` module, adding the 44-byte header that describes sample rate, channels, and bit depth.

```python
def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)     # 1 = mono
        wf.setsampwidth(sample_width) # 2 = 16-bit
        wf.setframerate(sample_rate)  # 24000 Hz
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
```
All parameters match Gemini TTS output spec. `sample_width=2` = 2 bytes = 16 bits per sample (L16 encoding). Using `io.BytesIO` avoids writing to disk — the WAV bytes are constructed in memory and returned directly.

---

## app/services/hubspot_service.py — HubSpot HTTP Client

### Overview

`HubspotService` wraps the HubSpot CRM v3 REST API using `httpx.AsyncClient`. It handles contact and deal CRUD, note creation, and contact search. All methods return a `{"success": bool, ...}` dict — exceptions are caught internally and converted to `{"success": False, "error": "..."}` so callers have consistent structure regardless of network conditions.

### find_or_create_contact (deduplication)

```python
    if lookup:
        try:
            search_result = await self.search_contact(lookup)
            if search_result.get("found") and search_result.get("contact_id"):
                return {..., "contact_id": search_result["contact_id"], "created": False}
        except Exception as exc:
            logger.warning("hubspot_service.search_skipped", reason=str(exc)[:120])
    result = await self.create_contact(data)
```
If the search endpoint returns a 403 (missing `crm.objects.contacts.read` scope), the exception is caught and the code falls through to `create_contact`. This degrades gracefully: duplicate contacts may be created, but the primary write path still works. Alternatives rejected: raising on 403 would break the entire CRM path for the sake of deduplication.

### Retry strategy

```python
@retry(
    retry=retry_if_exception(lambda e: isinstance(e, httpx.HTTPStatusError)
                              and e.response.status_code in {429, 500, 502, 503, 504}),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
```
Retries only on transient server errors and rate-limit (429). Deliberately excludes 400 (bad request — retrying won't help), 401 (auth failure — retrying won't help), and 403 (scope missing — retrying won't help). Retrying 403 would be the source of the retry storm observed in production.

---

## app/memory/postgres_memory.py — Rolling-Summarisation Memory

### Overview

`PostgresMemory` backs all conversation state in three PostgreSQL tables: `conversations` (per-user rolling buffer + summary), `leads` (progressively-updated qualification data), and `escalations` (handoff records). Every method acquires its own connection from the shared asyncpg pool — they are safe to call concurrently from multiple FastAPI background tasks.

### load (lines 53–102)

```python
    await conn.execute(
        "INSERT INTO conversations (user_id, source) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
        user_id, source,
    )
    row = await conn.fetchrow("SELECT * FROM conversations WHERE user_id = $1", user_id)
```
`ON CONFLICT DO NOTHING` creates the record for first-time users in the same query as the select. Alternative: check-then-insert has a TOCTOU race; the upsert is atomic.

```python
    gap = _utcnow() - row["updated_at"]
    if messages and gap > timedelta(hours=SESSION_GAP_HOURS):
        await self.summarize(user_id)
```
A 6-hour gap (configurable via `SESSION_GAP_HOURS`) between messages triggers session-boundary summarisation before the new session starts. This prevents the transcript from the last session crowding out the context window of the new session.

### append_message (lines 106–149)

```python
    update_sql = """
        UPDATE conversations
        SET messages      = messages || $1::jsonb,
            message_count = message_count + 1,
            updated_at    = NOW()
    """
```
`messages || $1::jsonb` appends to the JSONB array in a single SQL statement — no read-modify-write cycle, no race condition under concurrent appends. The `RETURNING message_count` clause avoids a second round-trip to check whether the threshold has been crossed.

### summarize (lines 252–310)

```python
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    prompt = (
        "You maintain a rolling summary of a customer-support conversation. "
        "Merge the EXISTING SUMMARY with the NEW MESSAGES into a single, concise, "
        "updated summary. Preserve important facts: who the user is, what they want, "
        "decisions made, and any commitments. Keep it under 200 words.\n\n"
        f"EXISTING SUMMARY:\n{row['summary'] or '(none)'}\n\n"
        f"NEW MESSAGES:\n{transcript}\n\n"
        "UPDATED SUMMARY:"
    )
    new_summary = await gemini_service.generate_text(prompt, temperature=0.2)
```
`temperature=0.2` (not 0.0) is intentional: summaries benefit from slight paraphrasing but should remain factual. The prompt structure (existing → new → merged) mirrors how humans update meeting notes.

```python
    await conn.execute("""
        UPDATE conversations
        SET summary              = $1,
            messages              = '[]'::jsonb,
            message_count         = 0,
            summarization_cycles  = summarization_cycles + 1,
            summary_updated_at    = NOW()
        WHERE user_id = $2
    """, new_summary, user_id)
```
Atomically: replace `summary`, clear `messages`, reset `message_count`, increment `summarization_cycles`. The cycle count is useful for diagnosing runaway summarisation (too-short threshold) and for billing estimation.

### update_lead (lines 168–199)

```python
    insert_cols = ["user_id"] + columns
    placeholders = ", ".join(f"${i + 1}" for i in range(len(insert_cols)))
    update_assignments = ", ".join(f"{col} = EXCLUDED.{col}" for col in columns)
    sql = f"""
        INSERT INTO leads ({", ".join(insert_cols)}) VALUES ({placeholders})
        ON CONFLICT (user_id) DO UPDATE SET {update_assignments}, updated_at = NOW()
    """
```
Dynamic SQL upsert: only the fields present in `updates` are written, so calling `update_lead(user_id, {"email": "x@y.com"})` does not overwrite `budget` or `lead_score`. `EXCLUDED.col` refers to the value that would have been inserted — the standard PostgreSQL pattern for partial upserts. Edge case: `pain_points` (a list) is serialised to JSON before insertion because PostgreSQL stores it as JSONB.

---

## app/rag/embeddings.py — Gemini Embeddings Wrapper

### Overview

`GeminiEmbeddings` is a LangChain `Embeddings` subclass that calls the Gemini `embedContent` REST endpoint directly via `httpx` rather than using the `google-generativeai` SDK. This was necessary because `langchain-google-genai` 2.0.7 silently ignores `outputDimensionality` in the SDK call, producing 3072-d vectors that don't fit the 768-d pgvector HNSW index.

### Key implementation details

```python
_MAX_CONCURRENCY = 8
_sem = asyncio.Semaphore(_MAX_CONCURRENCY)
```
A semaphore caps parallel embedding requests to 8. Without this, large batches during ingestion would open hundreds of concurrent HTTP connections, hitting Gemini's per-minute rate limit.

```python
async def _embed_one(text: str, task_type: str) -> list[float]:
    payload = {
        "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
        "outputDimensionality": settings.EMBEDDING_DIM,
    }
    async with _sem:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, params={"key": settings.GEMINI_API_KEY})
```
`taskType` distinguishes indexing (`RETRIEVAL_DOCUMENT`) from querying (`RETRIEVAL_QUERY`). Gemini's embedding model is trained on these two task types and produces better retrieval when they match — using `RETRIEVAL_QUERY` for documents would reduce recall.

```python
async def embed_batch(texts: list[str]) -> list[list[float]]:
    tasks = [_embed_one(t, "RETRIEVAL_DOCUMENT") for t in texts]
    return await asyncio.gather(*tasks)
```
`asyncio.gather` runs all tasks concurrently, bounded by the semaphore. Alternative: sequential loop would be correct but 8× slower for a 100-document batch.

---

## app/rag/retriever.py — Hybrid Retriever

### Overview

`HybridRetriever` extends LangChain's `BaseRetriever` to combine dense vector search (cosine similarity via pgvector HNSW) and sparse keyword search (PostgreSQL `TSVECTOR`/`GIN`). The two ranked lists are fused with Reciprocal Rank Fusion (RRF) before being returned.

### Dense search

```python
embedding = await gemini_embeddings.aembed_query(query)
rows = await conn.fetch("""
    SELECT id, content, metadata, source_file, chunk_index,
           1 - (embedding <=> $1::vector) AS similarity
    FROM document_chunks
    WHERE 1 - (embedding <=> $1::vector) >= $2
    ORDER BY similarity DESC
    LIMIT $3
""", str(embedding), settings.RAG_SIMILARITY_THRESHOLD, DENSE_TOP_K)
```
`<=>` is pgvector's cosine distance operator. `1 - distance` converts to similarity score. The `HNSW` index makes this an approximate nearest-neighbour search at O(log n) rather than exact O(n). The similarity threshold (default 0.30) filters out weakly related chunks before RRF.

### Sparse search

```python
rows = await conn.fetch("""
    SELECT id, content, metadata, source_file, chunk_index,
           ts_rank_cd(to_tsvector('english', content), query) AS rank
    FROM document_chunks, to_tsquery('english', $1) query
    WHERE to_tsvector('english', content) @@ query
    ORDER BY rank DESC
    LIMIT $2
""", pg_query, SPARSE_TOP_K)
```
`to_tsvector('english', content)` requires the PostgreSQL `english` text-search dictionary. Known limitation: Arabic text returns 0 results because PostgreSQL doesn't have an Arabic stemmer installed by default. Dense search still works for Arabic via semantic similarity.

### RRF fusion

```python
def rrf_fuse(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores
```
RRF assigns each document a score of `1/(k + rank)` for each list it appears in, then sums across lists. `k=60` is the standard RRF constant that down-weights high-rank documents relative to low-rank ones — it was empirically derived in the original RRF paper. Documents appearing in both lists get scores from two terms; unique documents get one. The final sorted order prioritises documents that ranked well in at least one modality over documents that ranked mediocrely in both.

---

## app/rag/reranker.py — Gemini Reranker

### Overview

`GeminiReranker` extends `BaseDocumentCompressor` (the LangChain interface for reranking). It supports two backends: `gemini` (default) prompts Gemini to re-order documents by relevance, returning a JSON array of indices; `cross-encoder` uses a local `sentence-transformers` model. The interface is identical from the caller's perspective.

### Gemini backend

```python
prompt = (
    f"You are a document relevance ranker. Given the query and documents, "
    f"return a JSON array of document indices ordered from most to least relevant.\n\n"
    f"Query: {query}\n\n"
    + "\n\n".join(f"[{i}] {doc.page_content[:500]}" for i, doc in enumerate(docs))
    + "\n\nReturn ONLY a JSON array like [2, 0, 1]. No other text."
)
```
The prompt is constrained to return `[2, 0, 1]` format — no prose, no explanation. Gemini's JSON mode (`response_format`) is not used here because the documents themselves may contain JSON, which confuses the parser.

### Cross-encoder backend

```python
from sentence_transformers import CrossEncoder
_ce_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
```
Lazy-loaded on first use (`_ce_model` is a module-level `None` until needed). `ms-marco-MiniLM-L-6-v2` is a 6-layer distilled cross-encoder trained on the MS MARCO passage ranking dataset — smaller and faster than the full-size model, adequate for re-ordering 20 documents.

---

## app/rag/ingest.py — Document Ingestion Pipeline

### Overview

`DocumentIngester` reads documents from a directory, chunks them, embeds each chunk, and upserts into the `document_chunks` pgvector table. Supported formats: PDF, DOCX, TXT, Markdown, JSON (FAQ pairs), and images. All loaders are LangChain-native with Gemini Vision/extraction as fallback.

### Loader dispatch

```python
async def load_document(path: Path) -> tuple[list[Document], str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":    return await _load_pdf(path), "pdf"
    elif suffix == ".json": return await _load_faq_json(path), "faq"
    elif suffix in _IMAGE_MIME: return await _load_image(path), "image"
    ...
```
Each loader returns a list of `Document` objects with `page_content` and `metadata`. Using LangChain's `Document` type preserves the loader chain: `_splitter.split_documents(raw_docs)` works identically regardless of source format.

### PDF loader with fallback

```python
async def _load_pdf(path: Path) -> list[Document]:
    try:
        loader = PyPDFLoader(str(path))
        docs = await asyncio.to_thread(loader.load)
        return docs
    except Exception:
        text = await gemini_service.extract_pdf_text(path.read_bytes())
        return [Document(page_content=text, metadata={"source": str(path)})]
```
`asyncio.to_thread` wraps the synchronous `PyPDFLoader.load()` call to avoid blocking the event loop. Gemini Vision fallback handles scanned PDFs that PyPDFLoader can't parse (image-only PDFs with no extractable text).

### FAQ JSON format

```python
parts = [
    f"Q: {item['question'].strip()}\nA: {item['answer'].strip()}"
    for item in data if item.get("question") and item.get("answer")
]
return [Document(page_content="\n\n".join(parts), metadata={"source": str(path)})]
```
All Q&A pairs are joined into a single document before chunking. This preserves Q&A pairing across chunk boundaries — a question and its answer are unlikely to be split if the chunk size (2000 chars) is larger than a typical Q&A pair.

### Chunk and embed

```python
chunks: list[Document] = _splitter.split_documents(raw_docs)
chunks = [c for c in chunks if len(c.page_content.strip()) >= MIN_CHUNK_LENGTH]
embeddings = await embed_batch([c.page_content for c in chunks])
```
Chunks shorter than 50 characters (typically table headers or stray whitespace) are filtered out before embedding — they add noise to retrieval without providing useful context.

```python
"token_count": len(chunk.page_content) // 4,
```
Character count ÷ 4 is an approximation of token count (English averages ~4 chars/token). Used for analytics and budget estimation, not for any routing decision.

### chunk_text utility

```python
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text or len(text) < MIN_CHUNK_LENGTH:
        return []
    splitter = RecursiveCharacterTextSplitter(...)
    return splitter.split_text(text)
```
Public function for splitting arbitrary text strings (not `Document` objects). Used by tests and by any caller that has raw text rather than a loaded document.

---

## app/api/messenger.py — Messenger Adapter

### Overview

`MessengerAdapter` handles the full inbound/outbound Messenger lifecycle: webhook verification, event normalisation (text, voice, image, file), outbound text replies, voice attachment uploads, and typing indicators. The `MessengerAdapter` and `FacebookCommentsAdapter` share a single webhook endpoint (`/messenger/webhook`) — Meta routes both subscription types through the same app.

### Webhook verification

```python
def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
    valid = {settings.MESSENGER_VERIFY_TOKEN, settings.FB_COMMENTS_VERIFY_TOKEN} - {""}
    if mode == "subscribe" and token in valid:
        return challenge
    return None
```
Both Messenger and Facebook Comments apps use the same webhook URL but may have different verify tokens. The set comprehension (`- {""}`) removes any empty strings, preventing an empty config value from accidentally matching anything.

### normalise (lines 58–116)

```python
    elif message.get("attachments"):
        attachment = message["attachments"][0]
        if att_type == "audio" and att_url:
            audio_bytes, mime_type = await self._download(att_url)
            content = await gemini_service.transcribe_audio(audio_bytes, mime_type)
            input_type = "voice"
```
Only the first attachment is processed. Messenger allows up to 10 attachments per message, but ORCAST's current scope is single-turn; multi-attachment handling would require batching transcriptions.

```python
async def _download(self, url: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {settings.MESSENGER_ACCESS_TOKEN}"})
        mime_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
        return resp.content, mime_type
```
The `Authorization` header is required even for attachment CDN URLs — Meta's CDN validates the page access token before serving media. `split(";")[0]` strips parameters like `; charset=utf-8` from the MIME type.

### send_voice_reply (lines 151–175)

```python
    data = {
        "recipient": json.dumps({"id": recipient_id}),
        "message": json.dumps({"attachment": {"type": "audio", "payload": {"is_reusable": False}}}),
    }
    files = {"filedata": ("voice_reply.mp3", audio_bytes, mime_type)}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(SEND_API_URL, data=data, files=files,
                                 headers={"Authorization": f"Bearer {settings.MESSENGER_ACCESS_TOKEN}"})
```
Messenger's `attachment_upload` API requires multipart/form-data with JSON-serialised `recipient` and `message` fields (not nested JSON body). `is_reusable: False` prevents Meta from caching the audio and serving it to other users. The `Authorization` header must not include `Content-Type: application/json` — the Content-Type is set automatically by httpx for multipart.

### Unified webhook (lines 220–262)

```python
@router.post("/messenger/webhook")
async def messenger_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    for entry in payload.get("entry", []):
        for messaging in entry.get("messaging", []):
            # Messenger DMs
            background_tasks.add_task(_process_and_respond, norm)

        for change in entry.get("changes", []):
            if change.get("field") == "feed" and value.get("item") == "comment":
                # Page comments
                background_tasks.add_task(_fc_process, norm)
    return {"status": "ok"}
```
The webhook returns `{"status": "ok"}` immediately and processes messages as FastAPI `BackgroundTask`s. Meta requires a 200 response within 20 seconds; background tasks ensure this even if graph execution takes longer. Edge case: if the FastAPI process dies after returning 200 but before the background task completes, the message is lost (no queue durability). A production system would use a message queue (Celery, ARQ, SQS) here.

---

## app/api/facebook_comments.py — Page Comments Adapter

### Overview

`FacebookCommentsAdapter` handles comments on Facebook Page posts. Event normalisation extracts the comment text, commenter ID, and comment ID. The comment ID is stored in `metadata` and is required for `reply_to_comment` to target the correct thread. The adapter filters out the Page's own comments to prevent reply loops.

### normalise

```python
def normalise(self, value: dict) -> Optional[UnifiedMessage]:
    comment_id = str(value.get("comment_id", ""))
    commenter_id = str(value.get("from", {}).get("id", ""))
    post_id = str(value.get("post_id", ""))
    text = str(value.get("message", "")).strip()
```
`value` is the `changes[*].value` dict from Meta's feed event. Comment text is in `message` (not `text` as in DMs). The comment ID is carried in metadata so `_send_facebook_comment_reply` can call `/{comment_id}/comments` on the Graph API.

### Reply-loop guard

```python
if page_id and sender_id == page_id:
    continue  # ignore the page's own comments
```
When ORCAST replies to a comment, Meta fires a feed webhook event for the reply. If that reply came from the same Page, ignoring it prevents infinite loops. The check is done in `messenger_webhook` using the entry's `id` field (the Page ID).

---

## app/api/vapi.py — Vapi Voice Adapter

### Overview

`VapiAdapter` handles the synchronous Vapi webhook protocol. Unlike Messenger (async, background tasks), Vapi requires the agent's response in the HTTP response body — Vapi reads it immediately and speaks it to the caller. The adapter normalises `conversation-update` events (the main message hook), acknowledges `end-of-call-report`, and returns assistant config on `assistant-request`.

### Signature verification

```python
def verify_signature(self, secret_header: str) -> bool:
    secret = settings.VAPI_WEBHOOK_SECRET
    valid = hmac.compare_digest(secret_header.strip(), secret.strip())
    return valid
```
Vapi sends the webhook secret as a plain string in `X-Vapi-Secret` — not an HMAC signature. `hmac.compare_digest` is used anyway for constant-time comparison, which prevents timing side-channel attacks where a valid prefix of the secret could be detected by response latency.

### extract_event

```python
    if event_type == "conversation-update":
        messages = payload.get("message", {}).get("artifact", {}).get("messages", [])
        user_messages = [m for m in messages if m.get("role") == "user"]
        result["user_text"] = user_messages[-1].get("message", "") if user_messages else ""
```
`artifact.messages` contains the full call transcript so far. Taking `[-1]` gets the most recent user utterance. Vapi sends the full history on every update — the graph's own memory layer handles deduplication.

### Synchronous response

```python
    agent_response = await run_graph(norm)
    return vapi_adapter.format_response(agent_response.message)
    # → {"result": "<text>"}
```
The HTTP response is the agent's message wrapped in `{"result": "..."}`. Vapi reads this field and speaks it to the caller using its own TTS engine. No backend audio synthesis occurs on the Vapi path — the messaging_node short-circuits for `source == "vapi"`.

---

## tests/ — Test Suite

### conftest.py

```python
import os
from pathlib import Path
os.chdir(Path(__file__).parent.parent)
```
Sets the process CWD to `CRM/CRM/` before any test module is imported. This ensures relative paths in config and loaders resolve correctly regardless of where `pytest` is invoked from. `config.py` uses `Path(__file__).parent / ".env"` so it doesn't need CWD, but other file references (knowledge base path, SQLite paths) may use CWD-relative strings.

### test_api.py

| Test class | What is tested | Key assertion |
|---|---|---|
| `TestHealthEndpoints` | `/` and `/health` routes | 200 + `{"status": "running"}` |
| `TestMessengerWebhook` | GET `/messenger/webhook` verify handshake | Returns challenge on valid token; 403 on invalid |
| `TestFacebookWebhook` | POST `/messenger/webhook` comments path | Background task dispatched; `{"status": "ok"}` |
| `TestVapiWebhook` | POST `/vapi/webhook` conversation-update | `verify_signature` checked via `x-vapi-secret` header; `run_graph` mocked |
| `TestAdminSimulate` | POST `/admin/simulate` | `run_graph` called with correct `UnifiedMessage`; response dict returned |

Key fix applied: all tests that previously used `META_VERIFY_TOKEN` (an old unified config field) were updated to `MESSENGER_VERIFY_TOKEN` and `FB_COMMENTS_VERIFY_TOKEN`. The Vapi signature tests were rewritten from HMAC-style (`x-vapi-signature: sha256=...`) to plain-string style (`x-vapi-secret: <secret>`).

### test_units.py

| Test class | What is tested |
|---|---|
| `TestLeadScoring` | `score_lead()` correctness: weights, thresholds, edge cases (unknown inputs, clamped integers) |
| `TestChunkText` | `chunk_text()` from `ingest.py`: empty string, short text, long text, overlap |
| `TestVapiSignature` | `verify_signature()`: valid secret, invalid secret, whitespace trimming, empty config skips check |
| `TestIntentClassify` | Mocked `ChatGoogleGenerativeAI.with_structured_output` returns known `_IntentOutput`; node returns correct `intent` |
| `TestHubspotNode` | Mocked `crm_operation` success and failure paths; checks `tool_results` accumulation on failure |

---

## app/db.py — Shared asyncpg Connection Pool

### Overview

`db.py` is the single owner of the PostgreSQL connection pool. It is imported by both `app/memory/postgres_memory.py` and `app/rag/vector_store.py`. Having one module own the pool prevents two separate pools from being created (which wastes connections and makes shutdown ordering unpredictable).

### Line-by-line walkthrough

```python
from pgvector.asyncpg import register_vector
```
`pgvector.asyncpg` installs a custom type codec for asyncpg so it knows how to serialise `list[float]` into PostgreSQL's `VECTOR` wire type and deserialise it back. Without this registration, passing a Python list as a `VECTOR` parameter raises a `can't adapt type 'list'` error.

```python
_pool: Optional[asyncpg.Pool] = None
_INIT_SQL_PATH = Path(__file__).resolve().parent.parent / "scripts" / "init_db.sql"
```
`_pool` is a module-level sentinel (None until `get_pool()` is first called). `_INIT_SQL_PATH` uses `__file__` to locate `scripts/init_db.sql` relative to `app/db.py`, not relative to CWD — the same pattern used in `config.py` for `.env`.

```python
async def _init_connection(conn: asyncpg.Connection) -> None:
    try:
        await register_vector(conn)
    except Exception:
        pass
```
asyncpg calls `init` for every new connection as it is added to the pool. The `try/except` silently skips the registration if the `vector` extension hasn't been created yet — this happens on the very first call to `init_db()`, before the SQL has run. After `init_db()` the pool is recreated so all subsequent connections pick up the codec.

```python
async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
            init=_init_connection,
        )
    return _pool
```
`min_size=2` keeps two connections warm at all times — avoids connection latency on the first real request after an idle period. `max_size=10` caps total connections; a single ORCAST instance with 10 concurrent webhook requests never needs more than 10 simultaneous DB operations. `command_timeout=30` raises `asyncpg.exceptions.QueryCanceledError` if any single query takes longer than 30 seconds, preventing a slow query from holding a connection indefinitely.

```python
async def init_db() -> None:
    sql = _INIT_SQL_PATH.read_text(encoding="utf-8")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(sql)
    await close_pool()
    await get_pool()
```
Runs the entire `init_db.sql` in one `execute()` call. PostgreSQL executes multi-statement SQL atomically when submitted as a single string without explicit `BEGIN`. After execution the pool is closed and recreated — this forces all connections to be freshly made, which triggers `_init_connection` now that the `vector` extension exists.

---

## scripts/init_db.sql — Database Schema

### Overview

`init_db.sql` is idempotent: every statement uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`, so re-running it on an existing database is safe. It creates four objects: the `vector` extension, and three tables (`conversations`, `leads`, `escalations`) for memory, plus `document_chunks` for the RAG store.

### conversations table

```sql
CREATE TABLE IF NOT EXISTS conversations (
    user_id               TEXT        PRIMARY KEY,
    source                TEXT        NOT NULL DEFAULT 'unknown',
    status                TEXT        NOT NULL DEFAULT 'active',
    summary               TEXT,
    messages              JSONB       NOT NULL DEFAULT '[]',
    message_count         INTEGER     NOT NULL DEFAULT 0,
    summarization_cycles  INTEGER     NOT NULL DEFAULT 0,
    summary_updated_at    TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| Column | Type | Purpose |
|---|---|---|
| `user_id` | TEXT PK | Facebook PSID / Vapi call_id / phone number. External identifier — not a UUID |
| `source` | TEXT | Last channel used: `"messenger"` / `"facebook_comments"` / `"vapi"` |
| `status` | TEXT | `"active"` or `"escalated"`. Once `"escalated"`, `route_after_memory` short-circuits the graph |
| `summary` | TEXT (nullable) | Rolling Gemini summary; NULL until first summarisation cycle |
| `messages` | JSONB `[]` | Raw turn buffer. Schema: `[{"role","content","source","timestamp"}, ...]` |
| `message_count` | INTEGER | Incremented per turn. Triggers summarisation when > `SUMMARIZATION_MESSAGE_THRESHOLD` |
| `summarization_cycles` | INTEGER | How many times the buffer has been summarised — useful for monitoring |
| `summary_updated_at` | TIMESTAMPTZ (nullable) | When the last summarisation ran — used for gap detection |
| `updated_at` | TIMESTAMPTZ | Updated by every `append_message` call — used for session-gap detection |

### leads table

```sql
CREATE TABLE IF NOT EXISTS leads (
    user_id            TEXT PRIMARY KEY REFERENCES conversations(user_id) ON DELETE CASCADE,
    name               TEXT,
    email              TEXT,
    phone              TEXT,
    budget             TEXT,
    authority          TEXT,
    engagement_level   INTEGER,
    interest_level     INTEGER,
    pain_points        JSONB NOT NULL DEFAULT '[]',
    lead_score         INTEGER,
    lead_temperature   TEXT,
    hubspot_contact_id TEXT,
    hubspot_deal_id    TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
`ON DELETE CASCADE` from `conversations` means cleaning up a test user via `DELETE FROM conversations WHERE user_id = $1` also removes their lead record — a single-statement cleanup for tests and admin. All qualification columns are nullable because leads are built progressively: a user might provide their email in turn 1, their budget in turn 5, and their authority level in turn 10.

### escalations table

```sql
CREATE TABLE IF NOT EXISTS escalations (
    id              BIGSERIAL   PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES conversations(user_id) ON DELETE CASCADE,
    reason          TEXT NOT NULL,
    priority        TEXT NOT NULL DEFAULT 'medium',
    status          TEXT NOT NULL DEFAULT 'open',
    hubspot_note_id TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_escalations_user_id ON escalations(user_id);
```
`BIGSERIAL` (not UUID) because escalation IDs are never shared externally — they're internal audit trail identifiers. `hubspot_note_id` links back to the HubSpot note created during escalation. The index on `user_id` allows fast lookup of a user's full escalation history without a seq scan.

### document_chunks table

```sql
CREATE TABLE IF NOT EXISTS document_chunks (
    id          BIGSERIAL    PRIMARY KEY,
    doc_id      TEXT         NOT NULL,
    source_file TEXT         NOT NULL,
    chunk_index INTEGER      NOT NULL,
    content     TEXT         NOT NULL,
    token_count INTEGER      NOT NULL DEFAULT 0,
    embedding   VECTOR(768),
    ts_content  TSVECTOR     GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    metadata    JSONB        NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (doc_id, chunk_index)
);
```

The two most important design choices:

**`VECTOR(768)`** — pgvector's fixed-width vector column. Dimension 768 matches the `outputDimensionality=768` we force on Gemini embedding REST calls. The HNSW index requires all vectors to share the same dimension — mismatched dimension would cause an index build failure.

**`ts_content TSVECTOR GENERATED ALWAYS AS (...) STORED`** — a generated column: PostgreSQL automatically recomputes it whenever `content` changes. No application code needs to maintain it. `STORED` writes the tsvector to disk rather than computing it on every read — required for the GIN index to work. Alternative: maintaining `ts_content` in application code is error-prone (easy to forget in updates) and more verbose.

```sql
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```
HNSW parameters: `m=16` is the number of bidirectional links per node in the navigable small world graph — higher values increase recall but slow index builds. `ef_construction=64` is the size of the candidate list during index construction — higher values increase index quality at the cost of build time. These are pgvector's recommended defaults for a balanced recall/speed tradeoff on datasets < 1M vectors.

```sql
CREATE INDEX IF NOT EXISTS idx_document_chunks_ts_content
    ON document_chunks USING gin (ts_content);
```
GIN (Generalized Inverted Index) is designed for multi-valued elements like tsvectors. It maps each lexeme to a list of document IDs, enabling `@@` operator lookups in O(log n) rather than a full table scan.

---

## app/rag/vector_store.py — pgvector Operations

### Overview

`vector_store.py` is the only file that issues SQL against `document_chunks`. Keeping all chunk SQL here means the schema can be changed in one place without hunting through multiple files.

### upsert_chunks (lines 23–62)

```python
async with conn.transaction():
    for chunk in chunks:
        await conn.execute("""
            INSERT INTO document_chunks
                (doc_id, source_file, chunk_index, content, token_count, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (doc_id, chunk_index) DO UPDATE
            SET source_file = EXCLUDED.source_file,
                content     = EXCLUDED.content,
                token_count = EXCLUDED.token_count,
                embedding   = EXCLUDED.embedding,
                metadata    = EXCLUDED.metadata
        """, ...)
```
All chunk inserts for a file run inside a single transaction. If any one fails (e.g. embedding dimension mismatch), the whole batch rolls back — no partial ingest states. `ON CONFLICT (doc_id, chunk_index)` makes re-ingestion idempotent: updating a document just replaces its chunks in place without creating duplicates. `doc_id` is an MD5 hash of the file path (from `ingest._doc_id()`), so the same file always maps to the same `doc_id`.

### dense_search (lines 65–80)

```python
rows = await conn.fetch("""
    SELECT id, doc_id, source_file, chunk_index, content, metadata,
           1 - (embedding <=> $1) AS score
    FROM document_chunks
    ORDER BY embedding <=> $1
    LIMIT $2
""", query_embedding, top_k)
```
`<=>` is pgvector's cosine distance operator. The HNSW index makes this query sub-linear. Important: the query does **not** apply a similarity threshold here — that happens in `retriever.py` at the RRF fusion stage. Applying a threshold in the SQL would skip the HNSW index and fall back to a sequential scan.

### sparse_search (lines 83–99)

```python
rows = await conn.fetch("""
    SELECT id, ..., ts_rank_cd(ts_content, plainto_tsquery('english', $1)) AS score
    FROM document_chunks
    WHERE ts_content @@ plainto_tsquery('english', $1)
    ORDER BY score DESC
    LIMIT $2
""", query, top_k)
```
`plainto_tsquery` converts natural-language text to a tsquery without requiring the user to know tsquery syntax — `"machine learning model"` becomes `'machine' & 'learning' & 'model'`. `ts_rank_cd` (cover density ranking) considers both term frequency and position proximity, giving better ranking than plain `ts_rank` for multi-word queries.

### _row_to_dict (lines 133–138)

```python
def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    if isinstance(d.get("metadata"), str):
        d["metadata"] = json.loads(d["metadata"])
    if d.get("score") is not None:
        d["score"] = float(d["score"])
    return d
```
asyncpg returns JSONB columns as strings, not Python dicts, in some configurations. The `isinstance` check guards against this without erroring if asyncpg already parsed it. `float(score)` normalises the decimal score from PostgreSQL's `numeric` type to Python's `float`.

---

## app/services/hubspot_service.py — HubSpot HTTP Client

### Overview

`HubSpotService` is the only file that talks to HubSpot's REST API. All methods return `{"success": bool, ...}` dicts — exceptions are caught at the call site rather than propagating. The shared `_request` method applies tenacity retries to every outbound call.

### Retry strategy (lines 32–45)

```python
def _is_retryable_http(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {429, 500, 502, 503, 504}

_RETRYABLE = retry_if_exception_type(httpx.TransportError) | retry_if_exception(_is_retryable_http)
```
Two independent retry conditions are OR-ed together:
1. `httpx.TransportError` — network-level failures (connection refused, timeout, DNS failure). These are always retryable.
2. `HTTPStatusError` with status in `{429, 500, 502, 503, 504}` — server-side transient errors and rate limit. Explicitly excludes 400 (bad payload — fix the request), 401 (bad token — retrying won't help), and 403 (missing scope — retrying won't help). This exclusion was critical for preventing the retry storm observed in production when HubSpot returned 403.

```python
def _retryable_request():
    return retry(
        retry=_RETRYABLE,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
```
`reraise=True` means after 3 failed attempts, the original exception is re-raised to the caller — not wrapped in a tenacity exception. This lets callers catch `httpx.HTTPStatusError` directly without knowing tenacity is involved.

### _request (lines 58–63)

```python
@_retryable_request()
async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.request(method, url, headers=self._headers, **kwargs)
        resp.raise_for_status()
        return resp
```
A new `AsyncClient` is created per call rather than reusing a session. This avoids connection pool state leaking between retries and is safe because `AsyncClient` itself manages a connection pool internally. `raise_for_status()` converts 4xx/5xx responses into `httpx.HTTPStatusError`, which tenacity then evaluates against `_is_retryable_http`.

### create_contact (lines 67–84)

```python
properties = self._build_contact_properties(data)
resp = await self._request("POST", CONTACTS_URL, json={"properties": properties})
result = resp.json()
contact_id = result.get("id")

if data.get("notes") and contact_id:
    await self.create_note(contact_id, "CONTACT", data["notes"])
```
HubSpot's CRM v3 contact create API wraps all properties in a `{"properties": {...}}` envelope. `_build_contact_properties` filters the data dict to only the keys HubSpot accepts — passing unknown keys causes a 400. The optional note creation runs after the contact is confirmed created; if it fails, the contact still exists (notes are informational, not blocking).

### _build_contact_properties (lines 267–270)

```python
@staticmethod
def _build_contact_properties(data: dict) -> dict:
    mapping = ("email", "firstname", "lastname", "phone", "company", "hs_lead_status", "lifecyclestage")
    return {key: str(data[key]) for key in mapping if data.get(key)}
```
All values are coerced to `str`. HubSpot's API rejects non-string property values with a 400. `if data.get(key)` drops `None` and empty-string values — sending `"phone": ""` to HubSpot would overwrite a valid phone number.

### find_or_create_contact (lines 153–181)

```python
if lookup:
    try:
        search_result = await self.search_contact(lookup)
        if search_result.get("found") and search_result.get("contact_id"):
            contact_id = search_result["contact_id"]
            update_data = {**data, "contact_id": contact_id}
            await self.update_contact(update_data)
            return {..., "created": False}
    except Exception as exc:
        logger.warning("hubspot_service.search_skipped", reason=str(exc)[:120])

result = await self.create_contact(data)
result["operation"] = "find_or_create_contact"
result["created"] = True
return result
```
When a contact is found by email/phone, it is updated with any new data (e.g. a name that wasn't in the original record), not just returned. The `created: False` flag lets callers distinguish between "we created a new contact" and "we found and updated an existing one" — useful for analytics and avoiding duplicate HubSpot deal creation.

### create_note (lines 240–263)

```python
association_type_id = 202 if object_type == "CONTACT" else 214
ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
payload = {
    "properties": {"hs_timestamp": ts, "hs_note_body": body},
    "associations": [{
        "to": {"id": object_id},
        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": association_type_id}],
    }],
}
```
HubSpot Notes API (v3 engagements) requires `hs_timestamp` in Unix milliseconds. Association type IDs are HubSpot-defined constants: `202` links a note to a contact, `214` links a note to a deal. These are stable internal IDs from HubSpot's schema. `create_note` returns `Optional[str]` (the note ID, or None on failure) and swallows its exception — a failed note is not critical enough to fail the entire escalation.

### create_deal (lines 185–220)

```python
payload: dict[str, Any] = {"properties": properties}
if contact_id:
    payload["associations"] = [{
        "to": {"id": contact_id},
        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
    }]
```
Association type ID `3` links a deal to a contact (standard HubSpot association). Setting this at creation time is more reliable than a follow-up association call — one fewer API call, and the deal is immediately visible on the contact timeline in HubSpot.

---

## app/graph/prompts.py — System Prompt and Tool Schemas (Full Detail)

### Tool input schemas

```python
class _CRMDataInput(BaseModel):
    email: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    hs_lead_status: Optional[str] = Field(
        default=None,
        description="HubSpot lead status: NEW | OPEN | IN_PROGRESS | UNQUALIFIED | ..."
    )
    lifecyclestage: Optional[str] = Field(
        default=None,
        description="HubSpot lifecycle stage: subscriber | lead | salesqualifiedlead | ..."
    )
    notes: Optional[str] = Field(default=None, description="Free-text note to attach to the contact.")
    contact_id: Optional[str] = None
    dealname: Optional[str] = None
    deal_id: Optional[str] = None
    amount: Optional[float] = None
    dealstage: Optional[str] = None
    pipeline: Optional[str] = None
```
`_CRMDataInput` is a superset of all contact and deal fields. The LLM receives a single `data` argument rather than operation-specific arguments — this simplifies the tool schema and lets the LLM pass fields appropriate to the operation without knowing every operation's exact signature. Fields irrelevant to a given operation (e.g. `dealname` on a `create_contact` call) are silently ignored by `hubspot_service._build_contact_properties`.

```python
class _CRMOperationInput(BaseModel):
    operation: str = Field(
        description="CRM operation: create_contact | update_contact | search_contact | get_contact | create_deal | update_deal"
    )
    data: _CRMDataInput
```
The nested model structure means the LLM call produces `{"operation": "create_contact", "data": {"email": "x@y.com", "firstname": "Alice"}}` — which `_flatten_crm_data()` in `nodes.py` unpacks, handling both dict and Pydantic model forms.

### build_system_prompt (lines 117–137)

```python
def build_system_prompt(state: GraphState) -> str:
    lines: list[str] = []
    summary = state.get("summary")
    lines.append(f"**Conversation Summary:** {summary}" if summary else "No prior summary.")
    lead = state.get("lead_profile") or {}
    if lead:
        safe_lead = {k: v for k, v in lead.items()
                     if k not in ("hubspot_contact_id", "hubspot_deal_id")}
        lines.append(f"**Lead Profile:** {json.dumps(safe_lead, default=str)}")
    else:
        lines.append("**Lead Profile:** No information collected yet.")
    lines.append(f"**Active Channel:** {state['source']}")
    return _SYSTEM_PROMPT_TEMPLATE.format(
        now=_now_utc(),
        channel_rule=_channel_rule(state["source"], state.get("input_type", "text")),
        context_block="\n".join(lines),
    )
```
Key decisions: `_now_utc()` injects the current datetime so the LLM can give accurate answers about time-sensitive questions ("are you open today?"). The format is `"Monday, 16 June 2026 — 14:30 UTC"` — human-readable, not ISO 8601, because the LLM is more likely to correctly reason about it. HubSpot IDs are stripped from `safe_lead` before injection — they're internal FK references that the LLM has no need for and could leak in a response.

### Channel rules (lines 86–110)

```python
if source == "vapi":
    return ("This is a live phone call. Respond in AT MOST TWO SHORT SENTENCES "
            "of plain spoken language. No markdown, no lists, no bullet points "
            "— your reply will be read aloud verbatim.")
if source == "messenger" and input_type == "voice":
    return ("The user sent a voice message and will receive a voice reply. "
            "Use natural, spoken language. No markdown, no lists.")
if source == "facebook_comments":
    return ("This reply will be posted PUBLICLY as a comment on a Facebook post. "
            "Keep it to one or two sentences, invite the user to send a DM for "
            "details, and never share personal data publicly.")
```
Three distinct voice/text distinctions: (1) Vapi is live voice — the LLM response is read by Vapi's own TTS, so brevity is critical. (2) Messenger voice input — the response will be synthesised by Gemini TTS and sent as an audio attachment. (3) Facebook comments — the reply is publicly visible; including a phone number or email in the reply would be a privacy violation and would violate Meta's platform policies.

---

## app/api/facebook_comments.py — Page Comments Adapter (Full Detail)

### extract_comment_events (lines 38–61)

```python
def extract_comment_events(self, payload: dict) -> list[dict]:
    entries = payload.get("entry", [])
    page_id = str(entries[0].get("id", "")) if entries else ""

    events = []
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if (
                change.get("field") == "feed"
                and value.get("item") == "comment"
                and value.get("verb") == "add"
            ):
                sender_id = str(value.get("from", {}).get("id", ""))
                if page_id and sender_id == page_id:
                    logger.debug("fb_comments.ignored_own_comment")
                    continue
                events.append(value)
    return events
```
The triple filter `field=="feed" AND item=="comment" AND verb=="add"` is required because Meta's Page feed subscription delivers many event types through the same webhook: post creates, comment adds, comment edits, post reactions, etc. Without all three conditions, a post reaction would be treated as a comment. `verb=="add"` specifically excludes comment edits and deletes. The page-ID guard prevents the page from replying to its own replies, which would create an infinite loop of AI responses to AI responses.

### reply_to_comment (lines 91–109)

```python
async def reply_to_comment(self, comment_id: str, text: str) -> dict:
    url = f"{GRAPH_BASE}/{comment_id}/comments"
    payload = {"message": text[:8000]}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=FB_HEADERS)
```
The reply endpoint is `/{comment_id}/comments` — posting to the `comments` edge of the comment object creates a thread reply, not a top-level post. `text[:8000]` respects Facebook's 8,000-character limit for comment text; silently truncating is better than raising (a partial reply is better than no reply).

### Dual webhook endpoints

```python
@router.get("/facebook/webhook")   # verification handshake
@router.get("/messenger/webhook")  # also handled by messenger.py
```
`FacebookCommentsAdapter` has its own `/facebook/webhook` endpoint for the initial Meta verification handshake (required when first connecting the app to a Page). In production, Meta can route feed events to either `/messenger/webhook` (unified) or `/facebook/webhook` (dedicated) — both paths ultimately call `facebook_comments_adapter.normalise()`.

---

## app/rag/retriever.py — Hybrid Retriever (Full Detail)

### rrf_fuse (lines 41–50)

```python
def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda cid: scores[cid], reverse=True)
```
Score accumulation example with `k=60`: a document at rank 0 (first) in one list gets score `1/61 ≈ 0.0164`. A document at rank 0 in both lists gets `2/61 ≈ 0.0328`. A document at rank 10 in both lists gets `2/71 ≈ 0.0282`. The `k` constant prevents the formula from weighting rank-1 documents massively higher than rank-2 documents — without it (`k=0`), rank-1 would score 1.0 and rank-2 would score 0.5, a 2× gap. With `k=60`, rank-1 scores 0.0164 and rank-2 scores 0.0161, a near-equal gap.

### _chunk_to_document (lines 53–63)

```python
def _chunk_to_document(chunk: dict[str, Any]) -> Document:
    return Document(
        page_content=chunk["content"],
        metadata={
            "id": chunk["id"],
            "doc_id": chunk.get("doc_id", ""),
            "source_file": chunk.get("source_file", ""),
            "chunk_index": chunk.get("chunk_index", 0),
            **chunk.get("metadata", {}),
        },
    )
```
Converts a raw DB row dict into a LangChain `Document`. The `metadata` dict is merged from the `metadata` JSONB column (file type, page number, etc.) plus the key row fields. This merging means `doc.metadata["source_file"]` and `doc.metadata["chunk_index"]` are always present in reranked documents, which `rag_tool.py` uses when building the source citation string.

### HybridRetriever.Config

```python
class Config:
    arbitrary_types_allowed = True
```
Required because `HybridRetriever` extends Pydantic's `BaseModel` (via `BaseRetriever`), and Pydantic v1 rejects non-Pydantic type annotations by default. `arbitrary_types_allowed = True` lets the class hold arbitrary Python objects in its fields without Pydantic trying to validate their types.

### _get_relevant_documents (lines 129–135)

```python
def _get_relevant_documents(self, query: str, ...) -> List[Document]:
    return asyncio.run(self._aget_relevant_documents(query))
```
The synchronous variant exists because `BaseRetriever` requires it. It wraps the async implementation with `asyncio.run()`. This is only ever called from synchronous contexts (tests running outside an event loop, or the `retrieve()` helper). In production, `ainvoke` is always used and the async path runs natively.

---

## app/rag/reranker.py — Gemini Reranker (Full Detail)

### acompress_documents (lines 49–60)

```python
async def acompress_documents(self, documents, query, callbacks=None):
    docs = list(documents)
    if not docs or len(docs) <= self.top_k:
        return docs
    if settings.RERANKER_BACKEND == "cross-encoder":
        return await _rerank_cross_encoder(query, docs, self.top_k)
    return await _rerank_gemini(query, docs, self.top_k)
```
The early return `if len(docs) <= self.top_k` skips reranking when there are fewer documents than requested — reranking 3 documents to get 5 is a no-op. `top_k` comes from `settings.RAG_TOP_K` (default 5); the retriever returns up to 20 docs, so reranking always applies in normal operation.

### _rerank_gemini (lines 76–98)

```python
numbered = "\n\n".join(f"[{i}] {doc.page_content[:500]}" for i, doc in enumerate(docs))
prompt = (
    "Rank the following numbered passages by relevance to the QUERY. "
    f"Return ONLY a JSON array of passage numbers, best-first, max {top_k} items.\n\n"
    f"QUERY: {query}\n\nPASSAGES:\n{numbered}\n\nJSON array:"
)
response = await gemini_service.generate_text(prompt, temperature=0.0)
cleaned = response.strip().strip("`")
if cleaned.lower().startswith("json"):
    cleaned = cleaned[4:].strip()
indices = json.loads(cleaned)
ranked = [docs[i] for i in indices if isinstance(i, int) and 0 <= i < len(docs)]
```
`temperature=0.0` makes the reranker deterministic. `[:500]` truncates each passage to 500 characters — sending full 2000-character chunks would consume too many tokens in the reranking prompt (20 docs × 2000 chars = 40k tokens). The `cleaned.lower().startswith("json")` guard handles Gemini occasionally returning a markdown code block: ` ```json\n[2,0,1]\n``` ` — stripping the fence and the language hint before parsing. The bounds check `0 <= i < len(docs)` rejects hallucinated indices (e.g. if Gemini returns `[0,1,25]` but only 20 docs exist).

### _rerank_cross_encoder (lines 105–118)

```python
if _cross_encoder is None:
    from sentence_transformers import CrossEncoder
    _cross_encoder = CrossEncoder(_CROSS_ENCODER_MODEL)

pairs = [(query, doc.page_content) for doc in docs]
scores = _cross_encoder.predict(pairs)
ranked = [d for _, d in sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)]
```
`CrossEncoder.predict(pairs)` scores all query-document pairs in a single batched forward pass. The model is loaded from Hugging Face on first use (lazy load avoids startup time when `RERANKER_BACKEND=gemini`). `ms-marco-MiniLM-L-6-v2` is a 6-layer distilled BERT model — fast inference (CPU is sufficient for 20 docs), well-calibrated relevance scores for English passages. If `sentence_transformers` is not installed, the exception is caught and the original order is returned.

---

## app/rag/embeddings.py — Gemini Embeddings (Full Detail)

### Why httpx instead of the LangChain wrapper

`langchain-google-genai` 2.0.7's `GoogleGenerativeAIEmbeddings` class does not pass `output_dimensionality` to the API. Without it, Gemini `text-embedding-004` returns 3072-dimensional vectors. pgvector's HNSW index requires a fixed dimension matching `VECTOR(768)` in the schema. Passing a 3072-d vector to a `VECTOR(768)` column raises a dimension mismatch error. The fix is calling the REST API directly with `outputDimensionality: 768` in the payload.

### _call (lines 103–113)

```python
async def _call(text: str, task_type: str) -> list[float]:
    payload = {
        "model": _model_path,
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
        "outputDimensionality": _EMBED_DIM,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_EMBED_URL, json=payload, params=_KEY_PARAM)
        resp.raise_for_status()
    return resp.json()["embedding"]["values"]
```
`_KEY_PARAM = {"key": settings.GEMINI_API_KEY}` is passed as a query parameter (`?key=...`) rather than an `Authorization` header — this is how Gemini's REST API v1 expects authentication. A new `AsyncClient` is created per call because the semaphore in `embed_batch` manages concurrency externally.

### Task type separation

```
embed_text()  → RETRIEVAL_DOCUMENT  (for indexing at ingest time)
embed_query() → RETRIEVAL_QUERY     (for search queries at runtime)
```
Gemini `text-embedding-004` is trained with both task types. Using `RETRIEVAL_DOCUMENT` for indexing and `RETRIEVAL_QUERY` for queries ensures the embedding space is calibrated for retrieval — the model produces vectors where query-document cosine similarity is meaningful. Using the same task type for both degrades recall because the model can't apply its asymmetric training.

---

## tests/ — Full Test Coverage Detail

### conftest.py design

```python
import os
from pathlib import Path
os.chdir(Path(__file__).parent.parent)
```
This runs before any test module is imported. Without it, running `pytest tests/` from `CRM/` (one level up from `CRM/CRM/`) would set CWD to `CRM/`, and any code that uses relative paths (e.g. `./knowledge_base`) would fail. Note: `config.py` uses `Path(__file__).parent / ".env"` and is CWD-independent, but `conftest.py` still sets CWD for any user-code that may use relative paths inadvertently.

### test_api.py — TestClient fixture

```python
@pytest.fixture(scope="module")
def client():
    from contextlib import asynccontextmanager
    from main import app

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        app.router.lifespan_context = original_lifespan
```
Replacing the lifespan prevents `init_db()` and `compiled_graph = build_graph()` from running during tests — these would require a live PostgreSQL connection and a valid Gemini API key. `scope="module"` creates the client once per test file (not once per test), avoiding multiple app instantiations. `raise_server_exceptions=False` lets tests assert on 500 responses instead of having the test client re-raise the exception.

### test_api.py — Vapi webhook test pattern

```python
def _post(self, client, payload: dict, secret: str = ""):
    raw = json.dumps(payload).encode()
    headers = {}
    if secret:
        headers["x-vapi-secret"] = secret  # plain string, NOT HMAC
    return client.post("/vapi/webhook", content=raw,
                       headers={"Content-Type": "application/json", **headers})
```
`content=raw` (raw bytes) rather than `json=payload` is required because `vapi_webhook` reads `await request.body()` before `json.loads()` — if the test sent `json=payload`, the Content-Type would still be set correctly but the test would be matching the production code's flow more faithfully by also using raw bytes.

### test_units.py — TestRrfFuse

```python
def test_top_ranked_in_both_wins(self):
    result = self._fuse([1, 2, 3], [2, 4, 5])
    assert result[0] == 2
```
ID 2 appears at rank 1 (0-indexed) in the first list and rank 0 in the second. ID 1 appears at rank 0 in the first list only.
- Score(ID 2) = 1/(60+1+1) + 1/(60+0+1) = 1/62 + 1/61 ≈ 0.0161 + 0.0164 = 0.0325
- Score(ID 1) = 1/(60+0+1) = 1/61 ≈ 0.0164
So ID 2 wins despite not being first in either list individually — the two-list boost outweighs the rank-0 advantage.

### test_units.py — TestBuildSystemPrompt security tests

```python
def test_hubspot_ids_redacted_from_prompt(self):
    state = self._state("messenger", lead_profile={
        "name": "Alice",
        "email": "alice@example.com",
        "hubspot_contact_id": "HS-SECRET-123",
        "hubspot_deal_id": "HS-DEAL-456",
    })
    prompt = build_system_prompt(state)
    assert "HS-SECRET-123" not in prompt
    assert "HS-DEAL-456" not in prompt
    assert "Alice" in prompt
```
This test directly encodes a security contract: internal HubSpot IDs must never appear in the LLM context window. If they did, the LLM could include them in a response (unlikely but possible), leaking internal record identifiers to end users.

---

## Configuration Reference

Complete list of all settings in `config.py` with their defaults and where they are used:

| Setting | Default | Used by | Notes |
|---|---|---|---|
| `GEMINI_API_KEY` | `""` | All Gemini calls | Required — empty key falls back to Application Default Credentials |
| `GEMINI_MODEL` | `""` | `gemini_service`, `intent_classify`, `rag_tool` | e.g. `gemini-2.5-flash` |
| `GEMINI_MODEL_FALLBACK` | `""` | `generate_text`, `generate_with_tools` | Tried if primary model fails |
| `GEMINI_EMBEDDING_MODEL` | `""` | `embeddings.py` | e.g. `text-embedding-004` |
| `GEMINI_TTS_MODEL` | `""` | `synthesize_speech` | e.g. `gemini-2.5-flash-preview-tts` |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/automark` | `db.py` | asyncpg DSN |
| `HUBSPOT_ACCESS_TOKEN` | `""` | `hubspot_service.py` | Private App token (`pat-eu1-...`) |
| `HUBSPOT_BASE_URL` | `https://api.hubapi.com` | `hubspot_service.py` | Do not change unless using a proxy |
| `MESSENGER_VERIFY_TOKEN` | `""` | `messenger.py` webhook verification | Must match Meta app webhook config |
| `MESSENGER_ACCESS_TOKEN` | `""` | `messenger.py` send/download | Page access token, not user token |
| `MESSENGER_APP_SECRET` | `""` | (reserved) | Currently unused — available for X-Hub-Signature-256 verification |
| `MESSENGER_PAGE_ID` | `""` | (reserved) | Available for reply-loop guard |
| `FB_COMMENTS_VERIFY_TOKEN` | `""` | `facebook_comments.py` | Can be same as `MESSENGER_VERIFY_TOKEN` |
| `FB_COMMENTS_ACCESS_TOKEN` | `""` | `facebook_comments.py` outbound | May be same as `MESSENGER_ACCESS_TOKEN` |
| `FB_COMMENTS_APP_SECRET` | `""` | (reserved) | |
| `FB_COMMENTS_PAGE_ID` | `""` | (reserved) | |
| `VAPI_WEBHOOK_SECRET` | `""` | `vapi.py` signature check | Plain string; empty = skip verification |
| `LANGCHAIN_TRACING_V2` | `False` | `config.py` env propagation | Set to `True` to enable LangSmith |
| `LANGCHAIN_API_KEY` | `""` | LangSmith SDK | Required when tracing is enabled |
| `LANGCHAIN_PROJECT` | `""` | LangSmith SDK | Organises traces in LangSmith UI |
| `RERANKER_BACKEND` | `"gemini"` | `reranker.py` | `"gemini"` or `"cross-encoder"` |
| `RAG_TOP_K` | `5` | `reranker.py` singleton | Final docs returned after reranking |
| `RAG_SIMILARITY_THRESHOLD` | `0.30` | (available) | Dense search pre-filter threshold |
| `KNOWLEDGE_BASE_PATH` | `"./knowledge_base"` | `ingest.py` CLI, `/admin/ingest` | Directory of documents to ingest |
| `EMBEDDING_DIM` | `768` | `embeddings.py`, `vector_store.py` | Must match `VECTOR(N)` in schema |
| `MAX_CONVERSATION_HISTORY` | `20` | `postgres_memory.load` | Max recent messages in context |
| `SUMMARIZATION_MESSAGE_THRESHOLD` | `20` | `postgres_memory.append_message` | Buffer size before summarisation |
| `APP_HOST` | `"0.0.0.0"` | `uvicorn.run` | |
| `APP_PORT` | `8000` | `uvicorn.run` | |
| `LOG_LEVEL` | `"INFO"` | `configure_logging` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `DEBUG` | `False` | `/docs`, CORS, admin routes | Set `True` in dev only |
| `MAX_AGENT_ITERATIONS` | `6` | `generate_response` loop | Max tool-call rounds per turn |

---

## Concrete Data Flow: "I'm Ahmed, my email is ahmed@company.com"

Walking a single message through the full system:

1. **Messenger webhook** — Meta POSTs to `/messenger/webhook`. `entry[0].messaging[0]` contains `sender.id = "123456"`, `message.text = "I'm Ahmed, my email is ahmed@company.com"`.

2. **normalise** — `MessengerAdapter.normalise()` creates:
   ```python
   UnifiedMessage(user_id="123456", source="messenger", input_type="text",
                  content="I'm Ahmed, my email is ahmed@company.com")
   ```

3. **Background task** — `background_tasks.add_task(_process_and_respond, norm)`. HTTP 200 `{"status": "ok"}` returned to Meta immediately.

4. **run_graph** — `initial_state = {"user_id": "123456", "source": "messenger", "input_type": "text", "user_message": "I'm Ahmed, my email is ahmed@company.com"}`

5. **memory_load** — `postgres_memory.load("123456")` issues `INSERT ... ON CONFLICT DO NOTHING` then `SELECT`. First-time user: `status="active"`, `summary=None`, `recent_messages=[]`, `lead={}`.

6. **route_after_memory** — `status != "escalated"` → `intent_classify`.

7. **intent_classify** — Gemini `with_structured_output(_IntentOutput)` receives the prompt with empty summary and empty lead profile. Returns:
   ```python
   _IntentOutput(intent="crm_request", rag_query="",
                 crm_data={"firstname": "Ahmed", "email": "ahmed@company.com"},
                 lead_signals={}, escalation_reason="")
   ```

8. **route_by_intent** — `"crm_request"` → `hubspot_node`.

9. **hubspot_node** — `lead_profile = {}`, no `hubspot_contact_id`. `crm_data = {"firstname": "Ahmed", "email": "ahmed@company.com"}`. Calls `crm_operation("create_contact", crm_data)` → `hubspot_service.find_or_create_contact()`. Search by email: not found → `create_contact()`. HubSpot returns `{"id": "HS-789"}`. Calls `postgres_memory.update_lead("123456", {"hubspot_contact_id": "HS-789", "email": "ahmed@company.com", "name": "Ahmed"})`.

10. **generate_response** — `build_system_prompt(state)` includes the updated lead profile. `gemini_service.generate_with_tools(...)` returns no tool calls, just text: `"Nice to meet you, Ahmed! I've got your details saved. How can I help you today?"`.

11. **save_memory** — `append_message("123456", "user", "I'm Ahmed...")` then `append_message("123456", "assistant", "Nice to meet you, Ahmed!...")`. `message_count` is now 2.

12. **messaging_node** — `source == "messenger"`, `input_type == "text"`. `send_reply()` → `messenger_adapter.send_message("123456", "Nice to meet you, Ahmed!...")`. Messenger Send API call.

13. **AgentResponse** returned: `{user_id: "123456", message: "Nice to meet you...", tools_called: ["crm_operation"], lead_updated: True, escalated: False}`.

---

## Error Handling and Resilience

### Hierarchy of failure modes

| Failure | Effect | Recovery |
|---|---|---|
| PostgreSQL connection fails at startup | `sys.exit(1)` | Fix DB connection; restart server |
| PostgreSQL query timeout (30s) | `asyncpg.QueryCanceledError` → graph exception | LangGraph returns partial state; channel adapter logs error |
| Gemini API rate limit (429) | `generate_text` falls back to `GEMINI_MODEL_FALLBACK` | If both fail, returns `""` |
| HubSpot 403 scope missing | `hubspot_node` adds failure to `tool_results`; LLM sees it failed | Contact not created; LLM tells user it noted the info |
| HubSpot 429/5xx | Tenacity retries 3× with exponential backoff | After 3 failures, `crm_operation` returns `{"success": False}` |
| TTS synthesis failure | `synthesize_speech` returns `None` | `messaging_tool` falls back to text reply |
| Voice transcription failure | `transcribe_audio` returns `""` | `normalise` uses `"[Voice message — transcription unavailable]"` as content |
| Messenger Send API failure | `send_message` returns `{"success": False}` | `_retry_on_failure` retries 3×; after exhaustion, message is lost |
| Reranker failure | `_rerank_gemini` catches exception, returns `docs[:top_k]` | First `top_k` retrieved docs used unranked |
| Background task crash | Logged with `exc_info=True` | No retry; message is lost (no queue durability) |

### Why no queue for background tasks

FastAPI `BackgroundTask`s run in the same process as the webhook handler. If the process dies after returning 200 but before the task completes, the message is silently lost. The current design accepts this tradeoff for simplicity. Production hardening would replace background tasks with an async task queue (Celery with Redis, ARQ, or AWS SQS) that guarantees at-least-once delivery and provides dead-letter queues for failed messages.

---

## Singleton Pattern — Why Module-Level Instances

Every major service is instantiated once at module import time:

```python
# postgres_memory.py
postgres_memory = PostgresMemory()

# gemini_service.py
gemini_service = GeminiService()

# hubspot_service.py
hubspot_service = HubSpotService()

# vapi.py
vapi_adapter = VapiAdapter()

# messenger.py
messenger_adapter = MessengerAdapter()

# rag/retriever.py
hybrid_retriever = HybridRetriever(top_k=FUSED_TOP_K)

# rag/reranker.py
gemini_reranker = GeminiReranker(top_k=settings.RAG_TOP_K)

# graph/orchestrator.py
compiled_graph = build_graph()
```

This pattern has three benefits:
1. **No per-request allocation** — Python's GIL and asyncpg's pooling mean sharing instances across concurrent requests is safe. Creating a new `GeminiService()` per request would add object allocation overhead with no benefit.
2. **Eager error detection** — if `build_graph()` raises (bad node wiring), it happens at import time (startup) rather than on the first production request.
3. **Testability via monkeypatch** — `monkeypatch.setattr("app.api.vapi.settings.VAPI_WEBHOOK_SECRET", "test")` works because the module attribute reference is stable. If settings were read at request time via a closure, monkeypatching would be harder.

The one risk: module-level imports create circular import potential. `app/graph/nodes.py` imports from `app/tools/*`; `app/tools/handoff_tool.py` imports from `app/memory/postgres_memory.py`; `app/memory/postgres_memory.py` imports from `app/db.py`. Python handles this because all paths terminate at modules with no back-references to `nodes.py`. The one deferred import is in `postgres_memory.summarize`:
```python
from app.services.gemini_service import gemini_service  # inside the method
```
This is intentional — `postgres_memory` is imported by `nodes.py`, which is imported by `orchestrator.py`, which imports `gemini_service`. Importing `gemini_service` at module level in `postgres_memory.py` would create a circular import via the `nodes.py → postgres_memory → gemini_service → config` chain.

---

## Why These Techniques

### HNSW vs IVFFlat for vector search

pgvector supports two ANN index types. HNSW (Hierarchical Navigable Small World) was chosen over IVFFlat for three reasons: (1) **No training step** — IVFFlat requires a pre-build `kmeans` clustering pass over existing data; re-running it after adding documents requires rebuilding the index, which is an exclusive lock operation. HNSW builds incrementally as rows are inserted — new chunks are immediately searchable. (2) **Better recall at small-to-medium scale** — at tens of thousands of chunks, HNSW achieves ~97% recall vs. IVFFlat's ~93% at the same query latency, because the navigable small world graph can explore more candidate paths. (3) **Simpler parameterisation** — `m=16, ef_construction=64` are near-universal defaults; IVFFlat requires tuning `lists` to `sqrt(n_rows)` and `probes` to balance recall vs. speed, which changes as the knowledge base grows. The one situation where IVFFlat wins is memory: HNSW uses ~4 bytes × `m` × 2 per vector for graph links (≈128 bytes overhead per 768-d vector at m=16), while IVFFlat has near-zero overhead. At hundreds of millions of vectors, this difference matters; at the single-company scale of ORCAST it does not.

### Reciprocal Rank Fusion for hybrid search

Dense retrieval (embedding cosine similarity) excels at paraphrase matching — "how much does the service cost?" matches "pricing plans start at $X/month" even without shared vocabulary. Sparse retrieval (TSVECTOR full-text) excels at exact-term matching — product codes, proper nouns, version numbers. Neither alone is sufficient. Naive score fusion (dense_score × w1 + sparse_score × w2) requires calibrating weights across two different score distributions: cosine similarity is bounded [−1, 1] and typically clusters near 0.3–0.7 for retrieved docs; `ts_rank_cd` is unbounded and varies with document length. RRF sidesteps calibration entirely by using rank position rather than raw scores. The `k=60` constant (from Cormack, Clarke & Buettcher, SIGIR 2009) was empirically shown to be robust across many retrieval tasks without per-query tuning. Documents appearing in both lists receive score contributions from two terms; documents in only one list from one. The penalty for appearing late in a list (rank 19 vs. rank 0) is `1/79 vs. 1/61` — about 23% — which is intentionally gentle, preventing a marginally worse rank from being penalised harshly.

### Rolling-summarisation memory vs. full-context memory

Naively storing the full conversation in the system prompt costs O(n) tokens per turn for an n-turn conversation. A 50-turn conversation at 150 tokens/turn is 7,500 tokens of history before the user's message — on a model with a 32k context window, this leaves little room for knowledge base context and response generation. Rolling summarisation compresses the buffer into a ≤200-word summary (~260 tokens) after every `SUMMARIZATION_MESSAGE_THRESHOLD` (20) turns, keeping the memory footprint constant. The lossy compression is acceptable because the `leads` table captures all structured facts (name, email, budget, score) independently — the summary covers narrative arc and tone, not precise quotes. Two alternatives were considered: (1) **Vector memory** (store each turn as an embedding, retrieve top-K on each request) — more faithful but requires a retrieval call every turn, adding 200–400ms latency; (2) **Full-window context** (pass all messages every turn) — zero information loss but expensive at scale and inflexible when the conversation grows beyond the model's context limit.

### LangGraph deterministic DAG vs. ReAct agent loop

The ReAct pattern (Reason + Act, Yao et al. 2023) lets the LLM choose which tool to call at each step in an unconstrained loop. ORCAST uses a deterministic graph instead for three reasons: (1) **Auditability** — every HubSpot write and every escalation event is recorded against a specific graph node, not "the LLM chose to do this." The `tool_results` list in state is a turn-level audit log. (2) **Testability** — `route_after_memory`, `route_by_intent`, `route_after_scoring` are plain Python functions that can be unit-tested without mocking an LLM. (3) **Bounded side effects** — the bounded tool-call loop in `generate_response` (max `MAX_AGENT_ITERATIONS=6`) ensures the agent cannot enter an infinite tool-calling loop. The key hybrid element is that `generate_response` itself runs a mini ReAct loop for response assembly (call tool, observe result, call another tool, compose response) — but all state-mutating actions (escalations, DB writes, HubSpot creates) happen in the deterministic upstream nodes, not in the LLM-driven loop.

### Structured output for intent classification (with_structured_output)

The naive approach to intent classification is: prompt the LLM to return a JSON object, parse the response string with `json.loads`, and validate it. This fails in practice because LLMs frequently add prose before or after JSON, use single quotes instead of double quotes, or truncate long JSON. `with_structured_output(_IntentOutput)` instructs the Gemini SDK to use function-calling mode with `_IntentOutput`'s JSON schema as the function signature — the model is constrained to return a valid JSON object matching the schema, and LangChain parses it into a Pydantic model automatically. The result is a `Literal` type guarantee on `intent`: the model cannot return `"crm-request"` instead of `"crm_request"`, and the Python type system confirms it.

### Human-handoff gating — two triggers, one lock

Escalation is triggered by two independent conditions: (1) explicit request (`escalation` intent from `intent_classify`) and (2) automatic qualification (`lead_temperature == "qualified"` from `route_after_scoring`, i.e. score ≥ 80). The two triggers are independent — a qualified lead who never says "I want a human" is still escalated automatically. Once escalated, `conversations.status` is set to `"escalated"` and every subsequent turn short-circuits to `already_escalated`, which returns a canned message without touching any tools. This lock has two purposes: (a) preventing the agent from continuing to qualify a lead that has already been handed to a human (awkward for the customer), and (b) ensuring the human agent has a clean slate without the AI interceding while they're working with the customer. The lock can only be reset by an admin via `DELETE FROM conversations WHERE user_id = $1` or by setting `status = "active"` directly.

### asyncpg over SQLAlchemy / psycopg3

asyncpg is a pure-async PostgreSQL driver with no synchronous fallback. It was chosen over SQLAlchemy async (which wraps a sync core) and psycopg3 (which requires more boilerplate for async) for three reasons: (1) **Protocol efficiency** — asyncpg uses PostgreSQL's binary protocol by default, which is 2–3× faster than the text protocol for large result sets (important for embedding vectors). (2) **True async** — asyncpg uses asyncio primitives natively; no thread pool tricks. (3) **pgvector integration** — `pgvector.asyncpg.register_vector` has a first-class integration path. The one downside: raw SQL strings rather than ORM models — `document_chunks` queries live in `vector_store.py` and must be updated when the schema changes, without ORM-level validation.

### httpx over aiohttp / requests

`httpx` was chosen as the async HTTP client for Gemini REST calls, Messenger Send API, and HubSpot API because: (1) it has a near-identical API to `requests` (both sync and async in one library), (2) it is the FastAPI project's recommended HTTP client and has the same dependency chain, and (3) `httpx.HTTPStatusError` integrates cleanly with tenacity's `retry_if_exception` predicate. `aiohttp`'s API is more verbose (session management requires explicit `async with` context at a different level), and `requests` is synchronous (blocking the event loop in an async app).

### StructuredTool stubs vs. real tool functions

The tool execution pattern in `generate_response` is: LangChain `bind_tools(TOOLS)` tells the LLM what tools exist (schema only), the LLM returns a `function_calls` list, and `generate_response` dispatches to the real functions manually. The `_stub` / `_async_stub` functions passed as `func` / `coroutine` to `StructuredTool` are never called by LangChain — they would only be called if using `AgentExecutor` or LCEL's tool-calling chain, neither of which is used here. The benefit: the graph retains full control over when and how tools execute, including the ability to batch tool calls, short-circuit on failure, and write to the DB before the LLM sees the result. The alternative (real functions in StructuredTool) would hand execution to LangChain and make it impossible to reliably add the result to `tool_results` before the next LLM call.
