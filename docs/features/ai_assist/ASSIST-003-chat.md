---
id: ASSIST-003
title: "Story Chat Assistant"
status: deprecated
area: ai_assist
mvp: false

ui_tooltip: "Conversational AI assistant for writing guidance and brainstorming."
ui_help_short: |
  Chat with your story. Ask questions, brainstorm ideas, explore plot
  possibilities, and get writing guidance through natural conversation.
  The AI knows your story context and characters.
ui_help_long: |
  ## Story Chat Assistant

  Conversational AI that knows your story inside and out.

  **What you can ask:**
  - **Plot questions**: "What if Chapter 5 ended differently?"
  - **Character exploration**: "How would Elara react to betrayal?"
  - **Brainstorming**: "Give me 3 plot twists involving the mentor"
  - **Worldbuilding**: "What are the implications of this magic rule?"
  - **Writing advice**: "How can I make this scene more tense?"

  **Context-aware responses:**
  - Knows your entire story context
  - Remembers previous conversation turns
  - References specific chapters and characters
  - Suggests concrete actions

  **Conversation modes:**
  - **Brainstorm**: Generate ideas without limits
  - **Analysis**: Examine existing content critically
  - **Planning**: Develop concrete next steps
  - **Exploration**: Follow "what if" questions

  **How it works:**
  1. Open Chat panel from any screen
  2. Start typing your question or prompt
  3. AI responds with:
     - Direct answer to your question
     - Context from your story (quotes, references)
     - Actionable suggestions
     - Follow-up questions to deepen exploration
  4. Continue conversation naturally
  5. Use quick actions:
     - "Create chapter from this idea"
     - "Add this to character profile"
     - "Generate scene outline"

  **Best practices:**
  - Be specific with your questions
  - Provide context for complex scenarios
  - Use for exploration, not final decisions
  - Combine with other tools for implementation
  - Let the AI ask you clarifying questions

  Available globally via Chat panel or via CLI:
  `narrare chat --novel <id> --message "What if..."`
ui_available_in: [global, cli]

service: chat/service.py
contract: chat/contracts.py#ChatServiceProtocol
router: chat/router.py
prompt: core/prompts/_bundled/writing/en/chat/system.md
requires: [INFRA-001, INFRA-002, INFRA-003]
---

> **⚠️ SUPERSEDED by [CHAT-001](../chat/CHAT-001-free-form-chat.md).**
> This spec is retained for history only. ASSIST-003 was never implemented as
> designed; it was replaced by CHAT-001 (Free-Form Chat) with a scoped,
> architecturally grounded design. The `prompt:` path above reflects the
> current canonical chat template (relocated under `writing/` by ADR-024 and
> confirmed by ADR-049); the original aspirational path
> `_bundled/chat/en/conversation` never existed and the `_bundled/chat/`
> directory has been deleted. Do not implement against this spec.

# ASSIST-003 — Story Chat Assistant

## What it does

Conversational AI assistant with full story context. Enables natural language exploration of plot possibilities, character motivations, worldbuilding implications, and writing guidance. Maintains conversation history and suggests concrete actions.

## Why it exists

Writers have questions that don't fit into structured tools. "What if this happened?" "How would my character react?" "Why isn't this scene working?" Story Chat provides a natural interface for exploration, brainstorming, and problem-solving without leaving the writing flow.

## How it works (User perspective)

1. Open Chat panel (available from any screen)
2. Start typing or use prompt templates:
   - "Explore consequences of..."
   - "Brainstorm alternatives for..."
   - "Analyze problems with..."
   - "Develop ideas for..."
3. AI responds with:
   - Direct answer to your question
   - Relevant story context (chapter references, character details)
   - Actionable suggestions
   - Follow-up questions
4. Continue conversation naturally
5. Use quick actions to implement:
   - Create chapter from idea
   - Update character profile
   - Generate scene outline
   - Save to notes

## How it works (Technical)

**Entry point:** `chat/router.py` → WebSocket endpoint at `/api/v1/chat`
**Service:** `ChatService.handle_message()` in `chat/service.py`
**Contract:** `ChatServiceProtocol` in `chat/contracts.py`
**LLM Intent:** `LLMIntent.CHAT`

**Conversation management:**
```python
class ChatMessage:
    role: "user" | "assistant" | "system"
    content: str
    context_references: list[ContextRef]  # Chapters, characters cited
    timestamp: datetime
    suggestions: list[ActionSuggestion]  # Concrete actions
```

**Context assembly:**
- Gathers relevant KB entries based on conversation
- Includes recent chapter content
- Maintains conversation history (last 10 turns)
- Provides story state summary (where we are in the plot)

**Action suggestions:**
- Create chapter: "Generate chapter based on this idea"
- Update KB: "Add this detail to character profile"
- Generate outline: "Create scene outline for this scenario"
- Save note: "Remember this for later"

## Constraints & Edge Cases

- Limited conversation history (last 10 turns for context)
- May hallucinate story details if KB is incomplete
- Cannot access future unwritten content
- Action suggestions require confirmation
- LLM availability required
- Context limit may truncate long conversations
- Suggestions are creative, not authoritative

## Related Features

- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Context management
- [KB-001](../kb/KB-001-entity-management.md) — Character/context data
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Chapter creation
- [PLAN-001](../planning/PLAN-001-scene-planning.md) — Scene planning

## Status & History

- `project-init` — Added to registry as planned feature
