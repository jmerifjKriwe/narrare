---
id: KB-002
title: "Assisted KB Creation"
status: implemented
area: kb
mvp: false

ui_tooltip: "AI-guided interview for creating rich Knowledge Base entries."
ui_help_short: |
  Instead of filling forms, have a conversation with the AI to create
  Knowledge Base entries. The AI asks thoughtful questions about your
  characters, locations, and world, then structures your answers into
  organized entries.
ui_help_long: |
  ## Interactive KB Sessions

  KB Sessions are conversations with the AI that create structured Knowledge
  Base entries. Instead of filling forms, you answer questions — the AI handles
  structure, organization, and completeness.

  **How it works:**

  1. Choose what you want to create (Character, Location, Faction, etc.)
  2. AI begins guided interview with context-aware questions
  3. You answer in natural language — single words or paragraphs
  4. AI follows up with deeper questions based on your answers
  5. When complete, AI structures everything into a proper KB entry
  6. You review, edit, and save

  **Example: Creating a Character**

  **AI:** "What's your character's name?"
  **You:** "Elena Vance"
  **AI:** "Tell me about Elena. What role does she play in your story?"
  **You:** "She's the protagonist. A mage who's just discovered her powers."
  **AI:** "Interesting! How old is Elena, and what does she look like?"
  **You:** "24, tall with silver hair — unusual in her world."
  **AI:** "Silver hair at 24 — that's distinctive. Is this natural, or connected
   to her magic? And how does she feel about discovering her powers?"

  ...conversation continues...

  **AI:** "I've created Elena's profile. Here's what I have:" [displays entry]
  **You:** [Review and edit] "Perfect, save it."

  **Benefits over manual entry:**
  - No blank forms to stare at
  - AI suggests details you might forget
  - Natural conversation flow
  - Better structured entries (AI organizes everything)
  - Serendipitous discoveries (questions spark ideas)

  **Session types:**
  - **New entity**: Create from scratch
  - **Deepen**: Expand existing entity with interview
  - **Connect**: Explore relationships between entities

  Available in Knowledge Base → "New with AI Interview".
ui_available_in: [kb]

service: kb/session_service.py
contract: kb/assist_contracts.py#KBAssistProtocol
router: kb/router_sessions.py
prompt: core/prompts/_bundled/kb
requires: [KB-001, INFRA-001]
---

# KB-002 — Interactive KB Session

## What it does

Conversational AI interface for creating and deepening Knowledge Base entries.
Guided interview asks context-aware questions, structures responses into proper
KB format, and suggests details users might forget.

## Why it exists

Blank forms are intimidating. Writers know their characters but freeze when
facing empty fields. Conversational creation feels natural — like describing
a friend to someone. The AI's questions also spark ideas users might not
consider on their own.

## How it works (User perspective)

1. Open Knowledge Base → click "New with AI Interview"
2. Choose entity type (Character, Location, etc.)
3. Chat with AI — it asks, you answer
4. AI builds entry in real-time (visible in sidebar)
5. When conversation ends, review complete entry
6. Edit if needed, then save

You can also "deepen" existing entries — AI interviews you about what's missing
or could be expanded.

## How it works (Technical)

**Entry point:** `apps/api/narrare/kb/router_sessions.py` → `POST /api/v1/novels/{novel_id}/kb/sessions`
**Service:** `KBSessionService` in `apps/api/narrare/kb/session_service.py`
**Contract:** `KBAssistProtocol` in `apps/api/narrare/kb/assist_contracts.py`
**LLM Intent:** `LLMIntent.KB_CREATE`, `LLMIntent.KB_IMPROVE`
**Streaming:** No — turn-based REST; each AI action returns synchronously

**Ownership & 404 semantics (IDOR S7):**
- Every session endpoint is novel-scoped (`/novels/{novel_id}/kb/sessions/...`)
  and user-scoped: the service only accepts a session when it belongs to
  both the path's novel and the authenticated user.
- Unknown and foreign (novel, session) combinations are indistinguishable —
  both raise `NotFoundError` → HTTP 404, so callers cannot probe for other
  users' sessions.
- Session creation gates novel ownership FIRST: a foreign/unknown novel
  yields 404 and no session row is created.

**Session flow:**
1. User starts session with entity_type and optional existing_entry
2. Service generates interview questions based on:
   - Entity type (character gets different questions than location)
   - Existing content (if deepening, focus on gaps)
   - Related entities (ask about connections)
3. User answers → AI processes → next question
4. AI structures responses into entry fields incrementally
5. On completion, AI assembles final entry with YAML frontmatter
6. User accepts → entry saved via KB-001

**Interview question generation:**
- Questions adapt based on previous answers
- Context-aware (asks about magic in fantasy worlds, tech in sci-fi)
- Prioritizes: Identity → Details → Relationships → Arc
- 5-15 questions per entity depending on complexity

**State management:** `KBCreationSession` in `apps/api/narrare/kb/session_models.py`
(one `KBCreationField` per template field; status `active → review →
complete/abandoned`; each field tracks question_asked, user_value,
ai_suggested_value, ai_reasoning, source, final_value — see Architecture
Decisions below).

## Constraints & Edge Cases

- Session timeout after 30 minutes of inactivity
- Maximum 50 questions per session (prevents infinite loops)
- AI requires LLM availability — graceful fallback if offline
- Very long answers may be truncated for context limits
- Deepening very complete entries may have few questions
- Simultaneous sessions limited to 3 per user

## Related Features

- [KB-001](KB-001-entity-management.md) — Saves completed entries
- [KB-003](KB-003-kb-improve.md) — Similar concept for improving existing entries
- [WRITE-005](../writing/WRITE-005-interactive-session.md) — Interactive writing sessions
- [INFRA-002](../infra/INFRA-002-prompt-system.md) — Interview prompts come from prompt system

## Architecture Decisions (2026-05-24)

### Assisted Form-Filling, not Chat

KB-002 is NOT a chat/Interview in the traditional sense. It's a
**template-guided assisted creation flow** where the user fills a template
and can request AI suggestions, AI-generated answers, or world-derived
context for any field at any time.

The interaction is a spectrum, not a mode:
- Full manual: User fills fields themselves
- AI-assisted: User clicks "suggest" on individual fields
- Interview mode: AI guides through fields sequentially
- Auto-generate: AI fills the entire template from context

### Session model: State machine, not chat

`KBCreationSession` with `KBCreationField` per template field.
Status: active → review → complete/abandoned.
Each field tracks: question_asked, user_value, ai_suggested_value,
ai_reasoning, context_entries_used, source (user/ai/world_derived/merged), final_value.

### KBAgent: Single agent, Union output

One agent with mode-aware prompts. The mode (interview/suggest/enhance/extract)
is set via system prompt, not via different agents. Shared tools:
KBQueryService (search_kb, get_entity, get_related).

### API: REST (not WebSocket)

REST endpoints for data operations (create session, answer field, accept suggestion).
No SSE/streaming endpoints are currently shipped — AI actions return
synchronously in the JSON response; per-action streaming can be added later if
the UX needs it. Not a real-time chat — turn-based Q&A.

### World context: ProactiveContextService

AI suggestions are grounded in the project's existing KB via
ProactiveContextService (merged KB-005/INFRA-009). Advanced mode lets users
choose which KB entries and chapters to include as context.

### Session storage: Ephemeral in-memory cache, 30min TTL (ADR-080)

Sessions are ephemeral creation flows, not persistent data. The
`KBCreationSessionStore` keeps them in the ADR-080 in-memory cache
(`SessionCacheProtocol`, TTL 1800s; the Redis abstraction was removed per
ADR-080). Final entries are saved via KB-001.

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-24` — Redesigned. Renamed from "Interactive KB Session" to "Assisted KB Creation". Template-guided spectrum (manual ↔ interview ↔ auto). Single KBAgent. REST+SSE. ProactiveContext for world context.
- `2026-05-25` — Status updated to implemented. Backend + Frontend complete. Backend: session_service, session_store, session_models, session_schemas, assist_service, assist_contracts, router_sessions, router_sessions_complete. Frontend: KBAssistedCreationPanel, KBAssistedCreationFooter, KBSessionFieldList, KBFieldSuggestion, KBInterviewView, KBEnhanceReview. Integration in WorldBuilding and KBEntryList ("New with AI Interview"). 99 backend tests. i18n complete.
- `2026-08-30` — IDOR S7: all session endpoints became (novel_id, user_id)-scoped with indistinguishable 404s for unknown/foreign access; creation gates novel ownership before any row is written. Technical section aligned with reality (novel-scoped routes via router_sessions.py, KBAssistProtocol, no streaming endpoints, KBCreationSession model, ADR-080 in-memory session storage).
