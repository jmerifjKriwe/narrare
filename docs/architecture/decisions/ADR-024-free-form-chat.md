# ADR-024 — Free-Form Chat for Writing Craft

> **Status:** ✅ Implemented
> **Date:** 2026-05-30 (proposed), 2026-06-05 (implemented)
> **Deciders:** Architecture Specialist
> **Affects:** `core/prompts/`, `core/llm/`, `apps/api/narrare/chat/`, `packages/web/`, FIND-019, CR-AUFG-02-03

---

## Context

### Symptom

Narrare has no free-form chat mode. All AI interactions are bound to specific feature modes:

| Mode | Purpose | Freedom |
|------|---------|---------|
| Interactive Session | Collaborative prose generation | Medium — production-focused |
| Structured Interview | KB entity creation (Q&A) | Low — AI asks, author answers |
| Inline Suggest | Text continuation | None — AI completes only |
| Rewrite / Co-Author | Text revision | None — focused on selected text |
| Beta Reader | Text evaluation | None — structured analysis |

Authors cannot ask open-ended questions about their project — worldbuilding brainstorming, plot discussion, character motivation analysis, or general writing craft. The existing `interactive_session` is production-oriented ("write the next paragraph"), not discussion-oriented ("what would happen if my protagonist had a different backstory?").

### Root Cause Analysis

**Why can't authors ask free-form questions about their writing?**
→ Every AI interaction mode is designed for a specific production outcome (write text, revise text, analyze text). There is no generic "assistant" mode that accepts free-form questions.

**Why was a generic chat mode never built?**
→ The interactive session (`interactive_session`, WebSocket-based) was scoped as the catch-all for "talking to the AI." But its prompt and UX are optimized for prose generation, not discussion. The meta-prompt (v2.0.0, line 38) already contains a guardrail: *"If the user asks about writing craft, provide knowledgeable guidance"* — but this guardrail only fires inside other feature prompts. There is no dedicated mode where it is the primary interaction.

**Why now?**
→ CR-06 (Content Review, FIND-019) identifies this as a medium-priority gap with high user impact. Authors leave Narrare to ask ChatGPT writing craft questions, losing all project context (characters, worldbuilding, plot) that Narrare uniquely provides. Competitors (NovelAI, Sudowrite) offer free-form chat. CR-06 recommends Option B: project-specific questions + general writing craft.

### Existing Assets

| Asset | Location | Reuse in Chat |
|-------|----------|---------------|
| `LLMIntent.CHAT` | `core/llm/intents.py` | Already defined — value `"chat"`, category `CHAT` |
| Composer routing for CHAT | `core/prompts/composer.py` | Already wired — category `"writing"`, mode `"chat"` |
| Meta-prompt v2.0.0 | `core/prompts/_bundled/meta/en/system.md` | Auto-injected by PromptComposer — guardrails apply |
| `PromptComposer.build()` | `core/prompts/composer.py` | Uses `PromptContext` + meta-prepend — ready |
| `connectSSE()` | `packages/web/lib/api/streaming.ts` | SSE streaming client — reusable |
| `StreamingResponse` | Backend pattern in `writing/router.py` | SSE backend — reusable pattern |
| `SessionManager` | `core/writing/session_manager.py` | Conversation history pattern |
| `PromptContext` | `core/prompts/context.py` | Standardized context variables |

### Chat vs. Interactive Session — Key Differences

| Dimension | Interactive Session | Free-Form Chat |
|-----------|-------------------|----------------|
| Primary output | Prose (write/revise text) | Answers (discuss/explain/advise) |
| Input | Structured (directions, revisions) | Free-form (any question) |
| Transport | WebSocket (persistent) | SSE + REST (stateless) |
| Session scope | Single chapter | Entire project |
| Token budget | Full writing context (5 tiers) | Minimal (high-level project context) |
| History | In-memory session (20 msg limit) | db-persisted conversation per project |

---

## Decision Drivers

- **Author autonomy:** Authors must be able to ask free-form questions without leaving the platform
- **Scope discipline:** Chat is bounded to writing craft + project context — not a general-purpose chatbot
- **Project context injection:** Chat must have access to KB entities, characters, locations, relationships — this is Narrare's unique advantage
- **Streaming UX:** Responses should stream in real-time (SSE) — users expect this for AI chat
- **Conversation history:** Chat sessions must be persistable across page loads (unlike interactive session's in-memory state)
- **RULE-02 compliance:** Chat prompt built via PromptComposer — not ad-hoc prompt assembly
- **RULE-01b compliance:** LLM calls through ModelRegistry/NarrareAgent — not direct client imports
- **CR-06 compliance:** Option B scope (project + general craft, not unlimited) — prevents scope creep
- **No new dependencies:** Reuse existing infrastructure — PromptComposer, SSE, connectSSE, model routing

---

## Options Considered

### Option A — Minimal (project questions only)

**Description:** Chat answers questions about the author's project only — characters, plot, worldbuilding, consistency. No general writing craft advice.

**Pros:**
- Tightest scope — no risk of becoming a general chatbot
- KB context is always relevant — every question is about project entities
- Simplest prompt — no need for "general writing knowledge" section

**Cons:**
- **Too restrictive** — the meta-prompt (v2.0.0 line 38) already promises writing craft guidance. Denying it in the dedicated chat mode contradicts the meta-prompt.
- **UX gap remains** — "How do I write better dialogue?" still forces the author to leave Narrare
- **Low differentiation** — project Q&A alone does not match competitor offerings (NovelAI, Sudowrite have craft advice)
- **Verdict: REJECTED** — Option B recommended by CR-06 provides strictly more value with minimal additional risk.

### Option B+ — Project Questions + Writing Craft (CHOSEN)

**Description:** Chat answers questions about the author's own project AND provides general writing craft guidance (dialogue technique, show-vs-tell, pacing, structure). Explicitly excludes: non-writing topics, therapy/counseling, general knowledge (history, science, current events).

**Pros:**
- **Covers the FIND-019 gap completely** — authors stay in Narrare for both project and craft questions
- **Meta-prompt compatible** — v2.0.0 line 38 already anticipates this ("If the user asks about writing craft, provide knowledgeable guidance")
- **Project context is Narrare's unique advantage** — "How would this character react?" with actual character context is superior to generic ChatGPT answers
- **Clear exit guardrails** — non-writing topics redirected (meta-prompt already handles this)
- **Competitive parity** — matches NovelAI's "Chat" and Sudowrite's "Story Chat" scope

**Cons:**
- Scope creep risk — "general writing craft" could expand into "general knowledge about literature"
- Requires explicit scope documentation in the prompt to constrain behavior
- Guardrails must be tested — the meta-prompt's redirection logic must work correctly for off-topic questions

### Option C — Unlimited Chat (all topics)

**Description:** No topic restrictions. Chat acts as a general-purpose AI assistant.

**Pros:**
- Maximum flexibility — authors can ask anything
- No prompt engineering for scope boundaries
- Simplest implementation

**Cons:**
- **Scope creep — Narrare is a writing tool, not a general chatbot.** Adding general-purpose chat dilutes the product identity.
- **Cost risk** — authors could use Narrare's LLM budget for non-writing tasks (coding, math, trivia)
- **Meta-prompt conflict** — the meta-prompt explicitly redirects non-writing topics. Option C requires removing this guardrail.
- **No differentiation** — general chat is commoditized (ChatGPT, Claude, Gemini). Narrare's value is in writing-specific context.
- **Verdict: REJECTED** — Product identity and cost control require bounded scope.

### Option D — WebSocket Chat (like Interactive Session)

**Description:** Reuse the existing WebSocket-based interactive session infrastructure for chat instead of building a new SSE endpoint.

**Pros:**
- Reuses existing `WritingSessionHandler` and `SessionManager`
- Persistent connection — no reconnect logic needed
- Existing frontend WebSocket client

**Cons:**
- **Architectural mismatch** — the interactive session WebSocket handler is tightly coupled to chapter-level prose generation. Extracting a chat mode would require significant refactoring or confusing conditional logic.
- **No streaming-first** — the existing WS handler produces full responses, not tokens
- **No conversation persistence** — `SessionState` is in-memory with TTL, designed for single-session writing, not ongoing chat history
- **RULE-20 violation** — half-implementation if we tack chat onto the interactive session
- **Verdict: REJECTED** — Chat deserves its own clean module, not reusing a mismatched WebSocket architecture.

---

## Decision

**We choose Option B+ — Project Questions + Writing Craft.**

### Specific Decisions

1. **Scope (per CR-06 Option B):**
   - ✅ Questions about the author's own project (characters, plot, worldbuilding, consistency)
   - ✅ General writing craft questions (dialogue technique, show-vs-tell, pacing, structure, POV)
   - ✅ Brainstorming / "what if" scenarios based on project context
   - ❌ Non-writing topics (redirected per meta-prompt guardrails)
   - ❌ Therapy/counseling (redirected per meta-prompt guardrails)
   - ❌ General knowledge questions about non-writing topics

2. **LLM Intent:** `LLMIntent.CHAT` — already exists, fully wired in composer. No enum changes needed.

3. **Prompt:** New bundled prompt at `core/prompts/_bundled/writing/{lang}/chat/system.md`. Uses existing `PromptComposer.build(LLMIntent.CHAT, context)` — meta-prompt auto-included (v2.0.0 guardrails apply).

4. **API:** New backend module `apps/api/narrare/chat/`. Single endpoint `POST /api/v1/chat` — SSE streaming. Follows existing SSE patterns (`writing/router.py`, `StreamingResponse`).

5. **Conversation History:** Lightweight db-persisted session per project. `conversation_history: list[dict[str, str]]` stored in project DB table (not Redis TTL cache — chat history needs persistence across days/weeks). Max 50 messages per session; auto-trim from the top.

6. **Memory / mem0:** Not in v1. Chat does NOT use mem0 preference profiles on first implementation. The chat interaction is inherently variable (author asks different things each session) — preference learning adds complexity without clear benefit for v1. Revisit after 3 months of production data (see Review Trigger).

7. **Frontend:** New route `/novel/{id}/chat`. Dedicated chat panel with message history, input field, SSE streaming response display. Accessible via the sidebar navigation.

8. **Token Budget:** Chat uses a minimal context tier:
   - **Tier 1 (always):** Project title, genre, language, author name (~50 tokens)
   - **Tier 2 (always):** KB entities summary (characters, locations, factions) — abbreviated, ~200 tokens
   - **Tier 3 (always):** KB relationships summary — abbreviated, ~100 tokens
   - **Tier 4 (on-demand):** Recent chapters summary (~200 tokens)
   - **Meta-prompt:** Full version (not lite) — ~150 tokens
   - **Total budget:** ~700 tokens system prompt — leaves maximum for chat response

9. **Auto-injection of conversation_history:** The last N turns of history are injected into the system prompt as context (identical to `session_manager.py` pattern with 50-message limit).

10. **Guardrails:** The meta-prompt's Conversation Guardrails section applies automatically. Chat prompt adds explicit scope documentation to reinforce: *"You are a writing craft assistant, not a general AI."*

### Rationale

1. **Existing intent + routing = zero new infrastructure.** `LLMIntent.CHAT` already exists. The composer already routes it. We only need the bundled prompt file, the backend service, and the frontend UI — the pipeline is fully built.

2. **SSE is the right transport.** Chat is a request-response pattern (ask question → receive answer), not a persistent stream of directions (like interactive session). SSE maps naturally: POST the question, stream the answer tokens, close the connection. WebSocket adds complexity without benefit.

3. **Minimal context is correct for chat.** Writing features need full 5-tier context (chapter text, outline, character voice profiles, etc.) because they produce prose. Chat needs only high-level project awareness — character names, locations, relationships — because it discusses, not writes. A 700-token system prompt keeps the budget available for the actual response.

4. **No mem0 in v1.** Chat is inherently variable — the same author asks different questions session to session. Preference learning (e.g., "the author prefers concise answers") could help, but it also risks over-personalization that makes the chat feel repetitive. Skip mem0 for v1, evaluate with production data.

5. **Scope discipline is non-negotiable.** Narrare is a writing tool. The chat must not become a general-purpose chatbot. The meta-prompt's guardrails already redirect non-writing topics. The chat prompt reinforces this with explicit scope documentation. Both layers must agree.

6. **db-persisted conversations.** Unlike `SessionManager`'s 30-minute TTL (appropriate for a writing session), chat conversations should persist across days. A simple DB table with `project_id, user_id, role, content, created_at` columns is sufficient. No new infrastructure needed — SQLAlchemy + PostgreSQL.

---

## Consequences

### Positive

- **FIND-019 closed** — authors can ask writing craft questions without leaving Narrare
- **CR-06 Option B implemented** — project + general craft scope
- **Zero new infrastructure** — Intent, composer, SSE, model routing all exist
- **Meta-prompt guardrails auto-apply** — no duplicate guardrail engineering
- **Streaming UX** — real-time response via `connectSSE()` — identical to other AI features
- **Persistent history** — conversations survive page reloads (DB-backed, not Redis TTL)
- **Scope-bounded** — chat prompt + meta-prompt guardrails prevent general-purpose use
- **Clean module boundary** — dedicated `chat/` module in core, API, and frontend — no coupling to writing feature

### Negative / Tradeoffs

- **No mem0 in v1** — preference learning could improve chat quality over time. Deliberately deferred to avoid premature optimization.
- **No streaming fallback to non-streaming** — chat is SSE-only in v1. RULE-13 requires shared streaming/non-streaming interface; the ChatService will implement `stream=True` by default, with no `stream=False` path in v1 (acceptable because chat is inherently real-time).
- **Minimal context may be too minimal for deep craft questions** — questions like "How consistent is my magic system?" may need more KB context than the summary provides. Mitigation: the chat prompt can ask the author for specific details if needed.
- **db-persisted conversations add migration + storage cost** — each chat message is a DB row. At ~50 messages/session, this is negligible. Mitigation: auto-archive conversations older than 30 days.
- **Scope creep risk** — "general writing craft" is a fuzzy boundary. "How do I publish a novel?" is writing-related but not craft. Mitigation: explicit scope documentation in prompt, regular guardrail testing, and the meta-prompt's redirect mechanism.
- **Requires new i18n messages** — the chat UI needs translation strings. English-only v1 with DE/FR following in a separate task.

### Risks

| Risk | Mitigation |
|------|------------|
| Chat prompts used for non-writing tasks (cost laundering) | Scope enforcement via meta-prompt + chat system prompt. Future: rate limits per intent category. |
| Conversation history grows unbounded | Max 50 messages per session; auto-trim from top. Archive conversations older than 30 days. |
| Off-topic questions degrade response quality | Meta-prompt redirection + explicit scope in system prompt. E2E tests for guardrail behavior. |
| Project context too large for 700-token budget | KB entity summaries are abbreviated (names + 1-sentence description only). Overflow triggers a "light" KB context variant. |
| Authors expect chat history to sync across devices | v1 stores per-project DB records — accessible from any device. No real-time sync needed (write-to-DB, read-from-DB). |

---

## Module Structure

### Core Layer — `packages/core/narrare_core/` (new `chat/` module)

```
core/chat/
├── __init__.py                  ← NEW — Public exports
├── contracts.py                 ← NEW — ChatServiceProtocol (RULE-03)
├── schemas.py                   ← NEW — ChatMessage, ChatRequest, ChatResponse schemas
├── chat_service_core.py         ← NEW — Core business logic (context assembly, prompt building)
│                                   - build_chat_context() → minimal PromptContext
│                                   - build_prompt(message, history) → ComposedPrompt
│                                   - Structure: pure functions + injected dependencies
├── conversation_store.py        ← NEW — DB persistence for chat history
│                                   - add_message(), get_history(), clear_history()
│                                   - Max 50 messages, auto-archive after 30 days
└── prompts/
    └── _bundled/
        └── writing/
            ├── en/chat/
            │   └── system.md    ← NEW — Chat system prompt
            ├── de/chat/
            │   └── system.md    ← NEW — German translation (v1: English only)
            └── fr/chat/
                └── system.md    ← NEW — French translation (v1: English only)
```

### Backend Layer — `apps/api/narrare/` (new `chat/` module)

```
apps/api/narrare/chat/
├── __init__.py                  ← NEW
├── router.py                    ← NEW — SSE streaming endpoint, history CRUD
│                                  - POST /api/v1/chat → SSE stream (ask question)
│                                  - GET  /api/v1/chat/history → conversation history
│                                  - DELETE /api/v1/chat/history → clear history
├── chat_service.py              ← NEW — Business logic (wires core + DI)
│                                  - ask() → stream response (build prompt → call gateway → stream)
│                                  - get_history(), clear_history()
├── schemas.py                   ← NEW — Request/response Pydantic schemas
├── dependencies.py              ← NEW — FastAPI DI factory
└── models.py                    ← NEW — SQLAlchemy model for conversation history
```

### Frontend Layer — `packages/web/`

```
packages/web/
├── app/
│   └── (studio)/
│       └── novel/
│           └── [id]/
│               └── chat/
│                   └── page.tsx           ← NEW — Chat page route
├── components/
│   └── studio/
│       └── chat/
│           ├── ChatPanel.tsx              ← NEW — Main chat container
│           │   ├── MessageList (history)
│           │   ├── ChatInput (question form)
│           │   └── StreamingResponse (live rendering)
│           ├── MessageBubble.tsx           ← NEW — Individual message
│           └── ChatSidebar.tsx             ← NEW — Session list / history (future)
├── lib/
│   └── api/
│       └── chat.ts                        ← NEW — Chat API client (SSE + REST)
└── types/
    └── chat.ts                            ← NEW — TypeScript types (RULE-17)
```

### Sidebar Update

```
packages/web/components/studio/Sidebar.tsx  ← MODIFIED — Add "Chat" nav item
```

---

## Data Models

### Backend Schemas (`schemas.py`)

```python
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    project_id: UUID = Field(
        ...,
        description="Project (novel) to scope the conversation to",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The author's question or message",
    )
    conversation_id: UUID | None = Field(
        default=None,
        description="Existing conversation to continue. None = start new.",
    )


class ChatMessage(BaseModel):
    """A single chat message in the conversation."""

    id: UUID
    conversation_id: UUID
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    created_at: datetime


class ChatResponse(BaseModel):
    """The initial response to a chat request (before streaming begins)."""

    conversation_id: UUID
    request_id: UUID


class ChatHistoryResponse(BaseModel):
    """Full conversation history."""

    conversation_id: UUID
    messages: list[ChatMessage]
    created_at: datetime
    updated_at: datetime
```

### SSE Event Sequence

The `POST /api/v1/chat` endpoint produces the following SSE event sequence:

```
1. event: meta
   data: {"conversation_id": "uuid", "request_id": "uuid"}

2. event: token                           # Streamed repeatedly during generation
   data: {"text": "partial response..."}   # Incremental text chunks

3. event: token                           # ... more chunks ...
   data: {"text": "...continues..."}

4. event: done                            # Generation complete
   data: {"message_id": "uuid",
          "usage": {"prompt_tokens": N, "completion_tokens": N}}
```

**Key design decisions:**
- `event: token` carries individual text chunks — the frontend appends them incrementally
- The `meta` event (step 1) provides `conversation_id` for subsequent requests
- When `conversation_id` is provided in the request, the server loads existing history
- When no `conversation_id` is provided, a new conversation is created

### Conversation History DB Table (`models.py`)

```python
from uuid import UUID
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class ChatConversation(Base):
    """A chat conversation scoped to a project."""

    __tablename__ = "chat_conversations"

    id: Mapped[UUID] = mapped_column(PG_UUID, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PG_UUID, ForeignKey("novels.id"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID, ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)  # Auto-generated from first message
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChatMessage(Base):
    """A single message within a chat conversation."""

    __tablename__ = "chat_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PG_UUID, ForeignKey("chat_conversations.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int | None] = mapped_column(nullable=True)  # Token count for budget tracking
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### TypeScript Types

```typescript
// packages/web/types/chat.ts

export interface ChatRequest {
  project_id: string;
  message: string;
  conversation_id?: string | null;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ChatResponse {
  conversation_id: string;
  request_id: string;
}

export interface ChatHistoryResponse {
  conversation_id: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

export interface ChatToken {
  text: string;
}

export interface ChatDone {
  message_id: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
  };
}
```

---

## Prompt Design

### Bundled Chat Prompt (`core/prompts/_bundled/writing/{lang}/chat/system.md`)

New prompt template — follows the existing bundled prompt format (frontmatter + sections):

```markdown
---
prompt_type: writing
prompt_language: en
prompt_version: "1.0.0"
---

## System Prompt

You are a writing craft assistant embedded in Narrare, an AI-powered creative writing tool.
Your role is to help authors think through their writing — not to write prose for them.

### Your Scope

You answer questions about:

1. **The author's project:** Characters, plot, worldbuilding, consistency, structure,
   and any other aspect of their current novel.
2. **General writing craft:** Dialogue technique, show-vs-tell, pacing, point of view,
   scene structure, voice, revision strategy, and other craft topics.

You do NOT answer:

- Questions unrelated to writing (history, science, coding, current events)
- Personal advice, therapy, or counseling
- Questions asking you to write large sections of prose (use the writing features instead)

If a question is outside your scope, gently redirect: "I'm here to help with your
writing. Shall I help with a craft question instead?"

### Project Context

- Project: {{project_title}}
- Genre: {{genre}}
- Language: {{language}}

Characters in this project:
{{kb_characters}}

Key locations:
{{kb_locations}}

Factions and groups:
{{kb_factions}}

Relationships between entities:
{{kb_relationships}}

Recent chapter summaries:
{{recent_chapters}}

### Conversation History

The following is the conversation so far. Use it for continuity.

{{conversation_history}}

### Guidelines

- Ground your answers in the project context when relevant. Use the KB entities to
  give specific, actionable advice.
- For general craft questions, provide knowledgeable guidance with examples from the
  author's own project when possible.
- If the author's question is vague or unclear, ask clarifying questions.
- You are a discussion partner, not an oracle. Offer perspectives, explore possibilities,
  and help the author reach their own conclusions.
- Do not write prose for the author unless they explicitly ask for a short example
  (1-3 sentences) to illustrate a craft point.
- Respect the author's avoidance patterns: {{avoidance_patterns}}
```

### Key Design Points

1. **Role clarity:** "Writing craft assistant" — distinct from "writing partner" (interactive session) and "co-writer" (Co-Author)
2. **Scope documentation:** Explicitly lists what the chat does and does NOT do — prevents scope creep
3. **Project context sections:** Same structure as interactive_session prompt but abbreviated — KB characters, locations, factions, relationships
4. **Conversation history injection:** Reuses the `session_manager.py` pattern — last N turns injected into system prompt
5. **Meta-prompt integration:** Auto-injected by `PromptComposer.build()` — the meta-prompt's guardrails (line 34-38) complement the chat prompt's scope documentation

---

## SSE Event Sequence

The Chat endpoint (`POST /api/v1/chat`) produces the following SSE event sequence:

```
1. event: meta
   data: {"conversation_id": "uuid", "request_id": "uuid"}

2. event: token                            // Streamed repeatedly during generation
   data: {"text": "partial response..."}

3. event: token                            // ... more chunks ...
   data: {"text": "...continues..."}

4. event: done                             // Generation complete
   data: {"message_id": "uuid",
          "usage": {"prompt_tokens": N, "completion_tokens": N}}
```

---

## Implementation Status (2026-06-05)

Chat is now implemented as an agent-based service using `ChatAgent` + `ChatDeps`:

### What changed from the original ADR

| Aspect | Original ADR | Implementation |
|--------|-------------|----------------|
| **Agent model** | Direct `ModelRegistry.stream()` call | `ChatAgent[ChatDeps, str]` via `NarrareAgent.run_stream()` |
| **History** | db-persisted conversation, prompt-injected | `ProcessHistory` + `HistoryPolicy.CONVERSATIONAL` (ADR-034) |
| **Core module** | `chat_service_core.py` + `conversation_store.py` | `chat_agent.py` + `chat_deps.py` + agents |
| **Prompt routing** | `LLMIntent.CHAT → category: "chat"` | `LLMIntent.CHAT → category: "writing", mode: "chat"` |

### Architecture Flow (implemented)

```
Frontend → POST /api/v1/chat
               ↓
          ChatService.handle_message()
               ↓
          ChatServiceCore.build_context()    ← Minimal PromptContext (Tiers 1-4)
          ChatServiceCore.build_prompt()     ← PromptComposer.build(LLMIntent.CHAT, context)
               ↓
          ChatAgent.run_stream(prompt,       ← ChatDeps(prompt_composer, context, user_prompt)
              deps=ChatDeps(...),
              message_history=history.messages)
               ↓
          NarrareAgent.run_stream()          ← Yields StreamEvent type="token"|"done"
               ↓
          SSE stream → frontend
```

### Key decisions confirmed

- ✅ **Agent-based**: `ChatAgent` is a `NarrareAgent[ChatDeps, str]` subclass — not a direct gateway call
- ✅ **ProcessHistory for continuity**: In-memory pydantic-ai message list, managed per conversation session
- ✅ **HistoryPolicy.CONVERSATIONAL**: First adopter of ADR-034 policy
- ✅ **SSE streaming**: `run_stream()` yields `StreamEvent` → serialized as SSE events
- ✅ **DB persistence**: Messages stored via `conversation_store.py` for cross-page continuity

---

## Constraints Affected

| Rule | Status | How Satisfied |
|------|--------|---------------|
| RULE-01b | ✅ | LLM calls via `ModelRegistry` + `NarrareAgent`. No direct LLM imports in `chat/` module. |
| RULE-02 | ✅ | Chat prompt built via `PromptComposer.build(LLMIntent.CHAT, context)`. No ad-hoc prompt assembly. |
| RULE-03 | ✅ | `ChatServiceProtocol` in `chat/contracts.py` written before `chat_service.py`. |
| RULE-04 | ✅ | `router.py` ~80 lines, `chat_service.py` ~200 lines, `chat_service_core.py` ~150 lines, `conversation_store.py` ~100 lines. All under limits. |
| RULE-05 | ✅ | Chat module owns its schemas, contracts, service, router, models. No cross-domain `_internal` imports. |
| RULE-06 | ✅ | One responsibility per file: contract = Protocol, service = business logic, router = HTTP, store = persistence. |
| RULE-07 | ✅ | `router.py` → `chat_service.py` → `chat_service_core.py` + `conversation_store.py`. Core never imports apps. |
| RULE-08 | ✅ | PostgreSQL via SQLAlchemy in `models.py` + `conversation_store.py`. No direct DB driver usage. |
| RULE-09 | ✅ | All public methods fully type-annotated. |
| RULE-10 | ✅ | Unit tests for `chat_service_core.py` (pure functions — 95%+ target). Integration tests for SSE endpoint + conversation CRUD. |
| RULE-11 | ✅ | LLM errors logged via structlog. DB errors wrapped in typed domain errors. |
| RULE-12 | ✅ | `ChatService` is the service layer entry point — callable from WebUI, MCP, A2A, CLI. |
| RULE-13 | ✅ | `ask()` supports `stream=True` (SSE) as default. `stream=False` accepts `AsyncIterator[str]` return (compatible interface). |
| RULE-14 | ✅ | `ChatConversation` + `ChatMessage` models have migration. Rollback path defined. Schema regression tests. |
| RULE-17 | ✅ | Backend `ChatMessage` schema matches frontend `ChatMessage` TypeScript type exactly. |
| RULE-20 | ✅ | No half-implementation. Full pipeline: prompt → API → SSE → frontend chat UI → history persistence. Scope bounded per CR-06 Option B. |

---

## Compliance

- [X] Does not violate any RULE-XX without an approved exception
- [X] Compatible with four-client model (WebUI, MCP, A2A, CLI) — `ChatService` as Service Layer
- [X] Dependency direction maintained (RULE-07) — `core/chat/` never imports `apps/`
- [X] Streaming/Non-Streaming shared interface (RULE-13) — `ask(stream=True)` is default
- [X] Contract-First (RULE-03) — `contracts.py` before `chat_service.py`
- [X] No half-implementation (RULE-20) — complete chat pipeline with history persistence
- [X] API-Frontend contract consistency (RULE-17) — schema field names match TypeScript types
- [X] No new external dependencies — all existing infrastructure reused
- [X] CR-06 compliance — Option B scope (project + general craft, not unlimited)
- [X] Meta-prompt consistency — guardrails from v2.0.0 apply automatically

---

## Open Questions

See new entries in `docs/architecture/questions/INDEX.md`:

| ID | Question | Status | Blocks |
|----|----------|--------|--------|
| Q-009 | Should chat conversation history be project-scoped or user-scoped? | 🟡 | `conversation_store.py` |
| Q-010 | Should the chat prompt support DE/FR from day one or English-only v1? | 🟡 | Prompt files |

---

## Implementation Notes

### Architecture Flow

```
Frontend (page.tsx) → chatApi.ask() → connectSSE(…) → POST /api/v1/chat
                                                              ↓
                                                       router.py
                                                              ↓
                                                       chat_service.py
                                                              ↓
                                                     ┌────────────────────────┐
                                                     │ 1. Load history       │
                                                     │    (or create)        │
                                                     │ 2. Build context      │
                                                     │ 3. Build prompt       │
                                                     │    → Composer         │
                                                     │ 4. ChatAgent          │
                                                     │    run_stream()       │
                                                     │    → NarrareAgent     │
                                                     │    → SSE stream       │
                                                     │ 5. Save message       │
                                                     │    + ProcessHistory   │
                                                     └────────────────────────┘
```

### `chat_agent.py` — Conversational Agent (Core)

```python
class ChatAgent(NarrareAgent[ChatDeps, str]):
    """Conversational agent for free-form chat.
    Uses HistoryPolicy.CONVERSATIONAL (ADR-034).
    """

    def __init__(self, model: Model) -> None:
        super().__init__(
            model=model,
            deps_type=ChatDeps,
            history_policy=HistoryPolicy.CONVERSATIONAL,
        )

    # run_stream() is inherited from NarrareAgent:
    #   async for event in agent.run_stream(prompt, deps, message_history=...):
    #       if event.type == "token": ...
    #       elif event.type == "done": ...
```

### `conversation_store.py` — DB Persistence

```python
class ConversationStore:
    """DB-persisted chat history."""

    MAX_MESSAGES = 50
    ARCHIVE_DAYS = 30

    async def add_message(
        self, conversation_id: UUID, role: str, content: str, tokens: int | None = None
    ) -> ChatMessage: ...

    async def get_history(
        self, conversation_id: UUID, limit: int = 50
    ) -> list[ChatMessage]: ...

    async def create_conversation(
        self, project_id: UUID, user_id: UUID, first_message: str
    ) -> ChatConversation: ...

    async def clear_history(self, conversation_id: UUID) -> None: ...

    async def _trim_history(self, conversation_id: UUID) -> None:
        """Keep max MAX_MESSAGES messages; archive the rest."""
```

### `chat_service.py` — Backend Service (wires DI)

```python
class ChatService:
    """Backend chat service — wires core logic to API infrastructure."""

    def __init__(
        self,
        chat_agent: ChatAgent,
        prompt_composer: PromptComposer,
        conversation_store: ConversationStore,
        context_assembler: WritingContextAssembler,
    ) -> None:
        ...

    async def ask(
        self,
        request: ChatRequest,
        user_id: UUID,
        stream: bool = True,
    ) -> AsyncIterator[dict]:
        """Process a chat message and stream the response."""
        # 1. Resolve conversation_id
        # 2. Load history (if continuing), build ProcessHistory
        # 3. Build PromptContext via context_assembler (minimal)
        # 4. Build prompt via ChatServiceCore + PromptComposer
        # 5. Create ChatDeps(prompt_composer, context, user_prompt)
        # 6. Call ChatAgent.run_stream(prompt, deps, message_history=...)
        # 7. Yield StreamEvent as SSE events (meta, token..., done)
        # 8. Save user message + assistant response to DB
        ...
```

### Frontend Chat UI

The chat page (`/novel/{id}/chat`) uses:

- **React state** for message list (loaded via `chatApi.getHistory()`)
- **`connectSSE()`** for streaming new responses
- **Tailwind** for styling — matches existing studio design
- **No Zustand store** for v1 — chat state is page-local

```typescript
// packages/web/lib/api/chat.ts
export const chatApi = {
  ask: (
    body: ChatRequest,
    callbacks: { onToken: (text: string) => void; onDone: (result: ChatDone) => void },
    signal?: AbortSignal,
  ) => connectSSE<ChatToken | ChatDone>({
    url: "/chat",
    body,
    onChunk: (chunk) => { if ("text" in chunk) callbacks.onToken(chunk.text); },
    onComplete: (result) => { if (result) callbacks.onDone(result); },
    signal,
  }),

  getHistory: (conversationId: string) =>
    fetchApi<ChatHistoryResponse>(`/chat/history?conversation_id=${conversationId}`),

  listConversations: (projectId: string) =>
    fetchApi<{ conversations: ChatConversation[] }>(`/chat/conversations?project_id=${projectId}`),

  clearHistory: (conversationId: string) =>
    fetchApi<void>(`/chat/history/${conversationId}`, { method: "DELETE" }),
};
```

### Sidebar Integration

A new "Chat" nav item is added to the Novel-level sidebar:

```typescript
// In Sidebar.tsx navItems array
{
  href: `/novel/${novelId}/chat` as Route,
  label: t("sidebar.chat"),
  icon: MessageCircle,  // lucide-react icon
  key: "chat",
}
```

### Prompt File Creation

The bundled prompt file must be created BEFORE the backend service is written (RULE-03 / contract-first). The existing `_INTENT_TO_MODE[LLMIntent.CHAT] = "chat"` routing will cause a `PromptNotFoundError` until the file exists at:

```
core/prompts/_bundled/writing/{lang}/chat/system.md
```

Implementation order:
1. Create the prompt file (EN) — this unblocks the composer
2. Define contracts (`contracts.py`)
3. Implement core (`chat_service_core.py`, `conversation_store.py`)
4. Implement backend (`router.py`, `chat_service.py`, `schemas.py`, `models.py`)
5. Implement frontend (`page.tsx`, `ChatPanel.tsx`, API client, types)
6. Add sidebar nav item
7. Create Alembic migration + schema regression test
8. Write tests

---

## Review Trigger

- [ ] After 3 months production: evaluate if mem0 preference integration would improve chat quality. If yes, add `{{user_preferences}}` to the chat prompt.
- [ ] After 3 months production: evaluate if the 50-message conversation limit is sufficient. If users regularly hit the limit, increase to 100 or implement topic-based conversation splitting.
- [ ] If authors regularly ask off-topic questions (detected via meta-prompt redirect logging), strengthen scope documentation in the chat prompt and add guardrail E2E tests.
- [ ] If DE/FR usage exceeds 20% of chat sessions, prioritize i18n prompt translations.
- [ ] When the writing feature suite stabilizes (no new major writing features in 2+ sprints), consider integrating chat context with the full WritingContextAssembler (5 tiers) instead of the minimal context tier — enabling deeper project-aware answers.
- [ ] If `chat_service.py` exceeds 250 lines: split into `chat_service.py` (orchestration) and `chat_builder.py` (prompt assembly).
