---
id: CHAT-001
title: "Free-Form Chat"
status: stable
area: chat
mvp: false

ui_tooltip: "Chat with your writing companion about craft, plot, worldbuilding, and your story."
ui_help_short: |
  Ask open-ended questions about your project. Brainstorm plot ideas, discuss
  writing techniques, explore character motivations, or get advice on worldbuilding —
  the AI knows your story context and characters.
ui_help_long: |
  ## Free-Form Chat

  A conversational space for discussing your writing project without
  leaving Narrare.

  **What you can ask:**
  - **Plot brainstorming**: "What if Chapter 5 ended differently?"
  - **Character exploration**: "How would Elara react to betrayal?"
  - **Worldbuilding**: "What are the implications of this magic rule?"
  - **Writing craft**: "How can I make this scene more tense?"
  - **Continuity**: "Are there any plot holes between chapters 3 and 7?"

  **How it works:**
  1. Open the Chat panel from any screen
  2. Type your question or start a discussion
  3. The AI responds with direct, practical answers
  4. It references your specific characters, locations, and story details
  5. Continue the conversation naturally

  **Important:** This is a writing companion, not a general-purpose chatbot.
  The AI stays scoped to writing, storytelling, and worldbuilding topics.
ui_available_in: [global, cli]

service: chat/chat_service.py
contract: packages/core/narrare_core/chat/contracts.py#ChatServiceProtocol
router: chat/router.py
prompt: core/prompts/_bundled/writing/en/chat/system.md
requires: [INFRA-001, INFRA-002, INFRA-003, KB-001, ADR-034]
adr: [ADR-024, ADR-049]
---

# CHAT-001 — Free-Form Chat

## What it does

Free-form conversational AI with full story context. Enables natural language
discussion of plot possibilities, character motivations, worldbuilding
implications, and writing craft guidance. Scoped to writing-related topics —
not a general chatbot.

## Why it exists

Writers have questions that don't fit into structured tools. "What if this
happened?" "How would my character react?" "Why isn't this scene working?"
Currently, users must leave Narrare and switch to an external chatbot for
these conversations — a UX break that pulls them out of their creative flow.
The interactive_session mode focuses on writing production, not discussion.
Free-Form Chat keeps the writer inside the platform for all creative
exploration.

**Supersedes:** ASSIST-003 (Story Chat Assistant) — this spec replaces the
earlier planned feature with a scoped, architecturally grounded design.

## How it works (User perspective)

1. Open the Chat panel (available from any screen via sidebar)
2. Type a question, idea, or topic — e.g., "How do I resolve this plot hole
   where Elara knows about the betrayal before chapter 5?"
3. Narrare responds with a direct, practical answer referencing their
   specific characters, locations, and story context
4. Continue the conversation naturally — ask follow-ups, explore alternatives,
   dig deeper into a suggestion
5. Responses stay focused on writing, storytelling, and worldbuilding
6. The AI gently redirects if the conversation drifts off-topic

## How it works (Technical)

**Entry point:** `chat/router.py` → `POST /api/v1/chat/message` (SSE streaming)
**Service:** `ChatService.handle_message()` in `chat/service.py`
**Contract:** `ChatServiceProtocol` in `chat/contracts.py`
**Agent:** `ChatAgent[ChatDeps, str]` in `core/chat/chat_agent.py` — conversational agent with `HistoryPolicy.CONVERSATIONAL`
**Dependencies:** `ChatDeps` in `core/chat/chat_deps.py` — prompt composition infrastructure per turn
**History:** `ProcessHistory` in `core/agents/process_history.py` — cross-turn message continuity (ADR-034)
**LLM Intent:** `LLMIntent.CHAT`
**Intent Category:** `IntentCategory.CHAT`
**Prompt:** `core/prompts/_bundled/writing/{lang}/chat/system.md`
**Context assembled by:** `PromptComposer` with `PromptContext`

### PromptComposer Integration

The PromptComposer maps intents to prompt file locations:

```
LLMIntent.CHAT → category: "writing" → mode: "chat"
```

Resolution path: `_bundled/writing/{language}/chat/system.md`

> **Path identity (ADR-049):** The canonical CHAT template lives under
> `writing/` because CHAT is a writing-craft assistant (ADR-024 §Decision 3).
> An earlier duplicate under `_bundled/chat/` was a route-table drift and has
> been deleted; the Prompt-Surface Identity checkers (PROMPT-IDENTITY,
> PROMPT-ROOT-MODE, ORPHAN-TEMPLATE) now enforce one routeable intent → one
> bundled template.

The composer automatically:
1. Prepends the meta-prompt (Narrare identity + role flexibility)
2. Loads the chat system prompt
3. Injects KB context (characters, locations)
4. Injects user preferences and avoidance patterns
5. Substitutes all template variables

### Core Module Structure

```
packages/core/narrare_core/chat/
├── __init__.py         ← Exports: ChatAgent, ChatDeps, ChatServiceProtocol
├── chat_agent.py       ← ChatAgent[ChatDeps, str] — conversational agent (HistoryPolicy.CONVERSATIONAL)
├── chat_deps.py        ← ChatDeps — prompt composition infrastructure per turn
├── chat_service_core.py← Pure business logic (context assembly, prompt building)
├── conversation_store.py← DB persistence for chat history (max 50 messages)
├── contracts.py        ← ChatServiceProtocol, ChatMessage, ChatRequest, ChatResponse
└── schemas.py          ← Pydantic schemas
```

History persistence is provided by `ProcessHistory` in `core/agents/process_history.py`
(ADR-034). The `ChatAgent` passes `message_history=history.messages` to
`NarrareAgent.run_stream()` for cross-turn continuity.

### Backend Module Structure

```
apps/api/narrare/chat/
├── __init__.py
├── contracts.py    ← ChatServiceProtocol
├── schemas.py      ← ChatRequest, ChatResponse, ChatMessage
├── service.py      ← ChatService (uses ChatAgent + PromptComposer)
├── dependencies.py ← FastAPI DI factory
├── models.py       ← SQLAlchemy models for conversation history
└── router.py       ← POST /chat/message (SSE streaming), history CRUD
```

### Request/Response Flow

```
User message + project context
       ↓
router.py (POST /chat/message)
       ↓
ChatService.handle_message()
       ↓
ChatServiceCore.build_context()   ← Minimal project context (Tiers 1-4)
ChatServiceCore.build_prompt()    ← PromptComposer.build(LLMIntent.CHAT, context)
       ↓
ChatAgent.run_stream(prompt, deps=ChatDeps(...),
                     message_history=history.messages)
       ↓
NarrareAgent.run_stream()         ← Yields StreamEvent(type="token"|"done")
       ↓
SSE stream → frontend
```

The `ChatAgent` is a `NarrareAgent[ChatDeps, str]` with `history_policy=HistoryPolicy.CONVERSATIONAL`.
It delegates to the base class `run_stream()` which yields `StreamEvent` objects.
Each turn's `new_messages` are appended to a `ProcessHistory` instance for
cross-turn continuity (see Conversation History below).

### Conversation History

Conversation history is maintained via `ProcessHistory` for cross-turn continuity.
The `ChatAgent` uses `HistoryPolicy.CONVERSATIONAL` (ADR-034), which means it
accumulates pydantic-ai message history across turns.

**Flow:**
```
history = ProcessHistory()

# Turn 1 — no prior history
async for event in agent.run_stream(prompt, deps, message_history=None):
    if event.type == "done" and event.new_messages:
        history.add(event.new_messages)

# Turn 2 — continuation with prior history
async for event in agent.run_stream(prompt, deps,
                                     message_history=history.messages):
    if event.type == "done" and event.new_messages:
        history.add(event.new_messages)
```

History is scoped per conversation session. The backend persists messages in
the database (via `conversation_store.py`) for cross-page-load continuity.
`ProcessHistory` handles the in-memory pydantic-ai message list for each turn.

### Streaming

Chat uses SSE streaming (RULE-13, RULE-20). The endpoint returns
`StreamingResponse` with `text/event-stream` content type. Non-streaming
mode is available through the same interface for MCP/CLI clients.

## Constraints & Edge Cases

- **Scoped to writing topics**: The AI redirects non-writing questions. This is
  a writing companion, not a general chatbot.
- **Conversation persistence**: History is persisted in the database via
  `conversation_store.py`. Conversations survive page reloads. Max 50 messages
  per conversation; older messages are auto-archived.
- **KB dependency**: If the Knowledge Base is empty, the AI operates without
  project-specific context. Responses are still useful for general writing
  craft questions.
- **Context window limits**: Long conversations may require truncation of older
  turns. The service keeps the most recent N turns (configurable, default 10).
- **LLM availability**: Chat requires a configured AI provider. Returns a clear
  error if no provider is configured.
- **No prose generation by default**: The AI focuses on discussion and advice.
  It generates prose only when the author explicitly asks it to.
- **Single-turn stateless endpoint**: Each request includes its own context.
  The backend does not maintain server-side session state for chat history.

## Related Features

- [INFRA-001](../infra/INFRA-001-llm-gateway.md) — LLM Gateway for all LLM calls
- [INFRA-002](../infra/INFRA-002-prompt-system.md) — Prompt system (PromptComposer)
- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Context assembly (KB → prompt)
- [KB-001](../kb/KB-001-entity-management.md) — KB Entity data used in chat context
- [WRITE-005](../writing/WRITE-005-interactive-session.md) — Interactive session (different: writing production, not discussion)

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | Chat uses `ChatAgent` (`NarrareAgent` subclass) — no direct LLM imports |
| RULE-02 | ✅ | Prompt built exclusively by `PromptComposer` via `ChatDeps` — no f-string prompts |
| RULE-03 | ✅ | `ChatServiceProtocol` in `contracts.py` before implementation |
| RULE-04 | ✅ | Module split: contracts, schemas, service, router, agent, deps — each under limits |
| RULE-05 | ✅ | Module boundaries: `chat/` owns its schemas, service, contract, router, agent, deps |
| RULE-06 | ✅ | Router delegates to service. Service delegates to `ChatAgent`. Agent handles LLM calls. |
| RULE-07 | ✅ | Dependency direction: router → service → core/chat/ (ChatAgent) → core/agents/ (NarrareAgent) |
| RULE-08 | ✅ | LLM access abstracted through `NarrareAgent` → pydantic-ai `Agent`. No direct SDK calls. |
| RULE-09 | ✅ | All public methods fully typed. No `Any` in public interfaces. |
| RULE-10 | ✅ | Unit tests for service, integration tests for router. Coverage ≥ 80%. |
| RULE-11 | ✅ | Error handling: typed domain errors, structured logging, no bare except. |
| RULE-12 | ✅ | Service layer callable from WebUI, MCP, A2A, CLI. |
| RULE-13 | ✅ | Streaming + non-streaming share one interface via `stream: bool`. |
| RULE-20 | ✅ | SSE streaming from day one. No "REST for now, SSE later." |

## Status & History

- `2026-05-31` — Feature spec created (supersedes ASSIST-003). CR-02 identified the gap.
- `2026-06-05` — Implementation started: `ChatAgent` + `ChatDeps` created, `ProcessHistory` for cross-turn continuity, `HistoryPolicy.CONVERSATIONAL` as first adopter (ADR-034). API backend refactored to use `ChatAgent.run_stream()`.
- `2026-06-10` — Fully implemented and promoted to stable. ChatAgent + ChatDeps with SSE streaming, ProcessHistory for cross-turn continuity (ADR-034), ChatPanel frontend component, conversation persistence, PromptComposer integration. All RULE-XX compliance verified.
- `2026-06-22` — ADR-049 confirmed route under writing/chat; ADR-024 authorizes implementation.
- `project-init` — ASSIST-003 added as planned placeholder (now superseded).
