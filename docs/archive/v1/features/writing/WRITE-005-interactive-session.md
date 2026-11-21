---
id: WRITE-005
title: "Interactive Writing Session"
status: implemented
area: writing
mvp: false

ui_tooltip: "Collaborative writing session with AI as your co-writer."
ui_help_short: |
  Enter an interactive writing session where you and the AI write together.
  You provide direction, the AI generates prose, and you iterate in real-time.
  Like having a co-writer available 24/7.
ui_help_long: |
  ## Interactive Writing Session

  Transform AI from a tool into a writing partner. Interactive sessions let
  you collaborate with the AI in real-time, iterating on prose together.

  **How it works:**

  1. Open a chapter and click "Start Session"
  2. AI greets you and asks what you'd like to write
  3. You give direction:
     - "Let's write the scene where Elena confronts the Council"
     - "I need dialogue between two characters who hate each other"
     - "Continue from where I am, but make it more tense"
  4. AI generates prose based on your direction
  5. You respond:
     - "Good, but make it shorter"
     - "Too much dialogue, add some action"
     - "Perfect, continue"
  6. Iterate back and forth until satisfied

  **Session features:**

  **Direction types:**
  - Scene goals: what should happen
  - Tone guidance: how it should feel
  - Character focus: who's in the scene
  - Constraints: length, style, etc.

  **AI responses:**
  - Generate prose based on your direction
  - Ask clarifying questions when needed
  - Suggest alternatives when direction is unclear
  - Explain choices when you ask why

  **Session controls:**
  - Save anytime to chapter
  - Undo last AI response
  - Regenerate if you don't like it
  - End session and close

  **Best for:**
  - Brainstorming scenes before writing
  - Working through difficult passages
  - Exploring different approaches
  - Getting unstuck when blocked

  Sessions are saved — you can close and return later. The AI remembers the
  conversation context within the session.

  Note: Sessions are not saved permanently. End of session = end of memory.
  Use chapter save to preserve prose you want to keep.
ui_available_in: [editor]

service: writing/service.py
contract: writing/contracts.py#WritingServiceProtocol, core/writing/contracts.py#SessionManagerProtocol
router: writing/router_sessions.py
prompt: core/prompts/_bundled/writing/{en,de,fr}/interactive_session/system.md
requires: [INFRA-001, INFRA-002, INFRA-013, KB-001]
---

# WRITE-005 — Interactive Writing Session

## What it does

Real-time conversational interface for collaborative writing. User provides
direction, AI generates prose, and they iterate together. Session maintains
conversation context but not permanent memory.

## Why it exists

Some writers want collaboration, not generation. They have ideas but need a
partner to bounce ideas off of, to try different approaches, to work through
difficult passages interactively. Sessions provide this collaborative experience.

## How it works (User perspective)

1. Open any chapter in Editor
2. Click "Start Session" — chat panel opens
3. AI greets: "What would you like to write today?"
4. You describe what you want: scene, tone, focus, etc.
5. AI generates prose and displays it
6. You respond: "Good but..." "Make it more..." "Try this instead..."
7. AI adjusts and regenerates
8. When satisfied, click "Add to Chapter" to save prose
9. Continue or end session

The AI remembers the conversation within the session but forgets everything
when the session ends. Save important prose to your chapter.

## How it works (Technical)

**Core module:** `packages/core/narrare_core/writing/session_manager.py`
**API module:** `apps/api/narrare/writing/`

**Entry point:** `apps/api/narrare/writing/router_sessions.py` → WebSocket `WS /api/v1/writing/sessions/{chapter_id}`
**WebSocket turn orchestrator:** `apps/api/narrare/writing/ws_turn_service.py` → `WritingTurnService` — transport-agnostic turn orchestration that flows through the invocation contract (RULE-12/RULE-13)
**WebSocket handler:** `apps/api/narrare/writing/ws_handler.py` — delegates to `WritingTurnService` for each turn
**Service:** `WritingService` in `apps/api/narrare/writing/service.py` (orchestrates session + pipeline + feedback)
**Session manager:** `SessionManager` in `packages/core/narrare_core/writing/session_manager.py` — cache-backed persistence via `SessionCacheProtocol`
**Contract:** `SessionManagerProtocol` in `packages/core/narrare_core/writing/contracts.py`
**LLM Intent:** `LLMIntent.GENERATE`
**Protocol:** WebSocket for real-time bidirectional messaging
**Invocation contract:** `WritingTurnService.stream_turn()` builds a `PromptInvocationContext` with user/project/chapter/session identifiers, then runs the `InvocationPipeline` (prepare → merge → compose → finalize), resolves run limits, and streams via `ModelRegistry.stream()` with `UsageLimits` enforcement. This design is transport-agnostic — any transport adapter (WebSocket, SSE, MCP) can consume the same service.

**Turn flow (via WritingTurnService — invocation contract integration):**
1. `apps/api/narrare/writing/ws_handler.py` receives a `user_direction` message
2. Delegates to `WritingTurnService.stream_turn()` which:
   - Builds `PromptInvocationContext` with identifiers + `invocation_id`
   - Invokes `InvocationPipeline.prepare()` — enrich/validate/resolve budgets
   - Invokes `InvocationPipeline.finalize()` — final validation + evidence recording
   - Calls `ModelRegistry.stream()` with resolved `UsageLimits`
   - Yields `StreamChunk` instances back to the WebSocket handler
3. The handler sends each chunk as `ai_prose` messages
4. Evidence is recorded via `FeatureInvocationEvidenceSink` for audit/runtime-proof tracking

**Session state (core models):**
```python
class SessionState:
    id: UUID
    chapter_id: UUID
    messages: list[SessionMessage]  # conversation history
    prose_buffer: str  # accumulated prose
    started_at: datetime
    last_activity: datetime
    # Managed by SessionManager with cache-backed persistence
```

**Message types:**
- `user_direction`: Writer's guidance
- `ai_prose`: Generated text
- `ai_question`: Clarification request
- `user_feedback`: Revision direction
- `save_to_chapter`: Commit prose to chapter

**Session persistence:**
- Redis-backed via `SessionCacheProtocol` (cache layer abstraction)
- 30-minute inactivity timeout — sessions auto-expire
- `apps/api/narrare/writing/_ws_cache.py` — WebSocket connection cache for active sessions
- ADR-052 uses an injected shared `SessionCacheProtocol`/`SessionManager` for
  WebSocket sessions (not a per-connection cache) so `?session_id=` reconnects
  can recover the same live session state until the TTL expires.

**Context management:**
- Uses `WritingContextAssembler` with 5-tier ranking (shared with other generation modes)
- Conversation history included in each LLM call
- Chapter context included (recent text, frontmatter)
- KB entries for characters/locations mentioned
- Context window limits conversation to ~20 messages

**Prose generation:**
- Each `ai_prose` message contains generated text
- Writer can accept (add to buffer) or reject
- Buffer accumulates accepted prose
- "Save to chapter" commits buffer to chapter storage

**Frontend components:**
- `packages/web/components/studio/editor/SessionPanel.tsx` — Interactive session chat UI
- `packages/web/components/studio/editor/ChatMessage.tsx` — Chat message bubble component
- `packages/web/lib/api/generation.ts` — WebSocket client for session messaging
- Session commands registered in CommandPalette

## Constraints & Edge Cases

- Session timeout after 30 minutes of inactivity
- Maximum 50 messages per session
- Context window limits conversation memory
- Prose in session is temporary — lost if not saved
- No session history — ending session clears everything
- Disconnect no longer always loses unsaved prose: ADR-052 introduces
  server-side stop + WebSocket recovery. Partial prose is preserved via
  `SessionTurnStateStore` on stop, and a `?session_id=` reattach restores the
  live session when the connection drops. Local unsaved prose is also preserved
  in the UI (`SessionReconnectBanner`). If recovery is impossible (expired
  session, nonexistent session, ownership mismatch), the UI surfaces the reason
  and keeps the local copy.
- LLM availability required — no offline mode

## Related Features

- [WRITE-002](WRITE-002-new-chapter.md) — One-shot generation
- [WRITE-006](WRITE-006-co-author.md) — Alternative collaborative interface
- [ASSIST-003](../ai_assist/ASSIST-003-chat.md) — General chat with AI
- [INFRA-002](../infra/INFRA-002-prompt-system.md) — Chat prompt system

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-17` — Implementation started (in-progress). WebSocket endpoint with session handler, Redis-backed persistence via SessionCacheProtocol, 30-min inactivity timeout, frontend SessionPanel + ChatMessage components, core SessionManager with cache abstraction.
- `2026-05-18` — Fully implemented (stable). WebSocket bidirectional messaging operational, session persistence working, frontend session UI complete.
- `2026-06-14` — Invocation contract integration: `WritingTurnService` wraps the turn flow through `PromptInvocationContext` → `InvocationPipeline` (enrich/validate/budget/evidence) → `ModelRegistry.stream()` with `UsageLimits`. Transport-agnostic design per RULE-12/RULE-13. Runtime evidence recording for audit tracking.
- `2026-06-22` — ADR-052 adds server-side stop and reconnect recovery: `stop_generation` cancels active streaming turns, `generation_stopped` returns preserved partial prose, and `?session_id=` reattach restores shared cached session state until TTL expiry.
