---
id: INFRA-005
title: "Memory Layer (Rejection Learning)"
status: in progress
area: infra
mvp: false

ui_tooltip: "AI learns from your feedback to improve suggestions over time."
ui_help_short: |
  Narrare learns from your writing choices. When you accept, reject, or modify
  AI suggestions, the system remembers your preferences and adapts future
  suggestions to match your style and taste.
ui_help_long: |
  ## Memory Layer & Rejection Learning

  Narrare's Memory Layer enables the AI to learn from your feedback over time.
  The more you write with Narrare, the better it understands your preferences.

  **How feedback works:**

  **Accept** ✓
  You used the suggestion exactly as provided.
  → AI learns: "This style/approach works for this user"

  **Reject** ✗
  You dismissed the suggestion.
  → AI learns: "Avoid this pattern for this user"

  **Modify** ✎
  You used the suggestion but made changes.
  → AI learns: "This was close, but needed adjustment"

  **What the AI tracks:**

  **Style Preferences**
  - Sentence structure (short vs long, complex vs simple)
  - Descriptive density (sparse vs rich description)
  - Dialogue patterns (realistic vs stylized)
  - Metaphor usage frequency

  **Content Preferences**
  - Themes and genres you prefer
  - Character types you write well
  - Plot patterns you enjoy
  - Pacing tendencies

  **Structure Preferences**
  - Scene length preferences
  - Chapter organization patterns
  - Transition styles
  - Exposition vs action balance

  **How it affects suggestions:**
  Future AI operations include your preference profile as context.
  Accepted patterns appear more often; rejected patterns appear less.
  The AI gradually adapts to your unique voice.

  **Reset and control:**
  - View your preference profile in Settings
  - Reset preferences when changing creative direction
  - Disable learning entirely if preferred
  - Export preferences for backup/analysis

  Learning happens automatically. Your data stays private — preferences are
  stored locally, never shared with any service.
ui_available_in: [settings]

service: core/memory/feedback_service.py, core/memory/preference_service.py
contract: apps/api/narrare/memory/contracts.py
router: apps/api/narrare/memory/router.py
prompt: ~
requires: [INFRA-001]
---

# INFRA-005 — Memory Layer (Rejection Learning)

## What it does

Persistent preference learning system that tracks user feedback on AI suggestions
(accept/reject/modify) and builds a preference profile. Future AI operations
include this profile as context to better match user's style and taste.

## Why it exists

One-size-fits-all AI suggestions frustrate writers. What works for literary
fiction fails for thriller writers. What one author loves, another hates.
The Memory Layer enables Narrare to adapt to each writer's unique voice and
preferences over time.

## How it works (User perspective)

1. You interact with AI suggestions (accept, reject, or modify)
2. Narrare records your choice in the background
3. Preference profile updated with pattern analysis
4. Future suggestions influenced by your profile
5. Over time, suggestions match your style better

Most users don't need to think about it — it just gets better. Power users can:
- View preference profile in Settings
- See what patterns the AI has learned
- Reset when changing creative direction
- Disable if they don't want learning

## How it works (Technical)

**Core modules (`packages/core/narrare_core/memory/`):**
- `protocols.py` — Protocol definitions: `MemoryClientProtocol`, `FeedbackServiceProtocol`, `PreferenceServiceProtocol`
- `models.py` — Data models: `FeedbackEvent`, `Preference`, `FeedbackAction` enum
- `mem0_client.py` — `Mem0Client` factory and `NullMemoryClient` for graceful degradation (approved RULE-01 exception)
- `feedback_service.py` — `FeedbackService` — records feedback events to both `feedback_events` table and mem0
- `preference_service.py` — `PreferenceService` — extracts preferences from mem0, formats for prompt injection

**API module (`apps/api/narrare/memory/`):**
- `contracts.py` — Protocol definitions
- `schemas.py` — Request/response Pydantic models
- `models.py` — SQLAlchemy `feedback_events` table model
- `repository.py` — Database queries for feedback events
- `service.py` — Business logic orchestrating core services
- `router.py` — REST endpoints

### Dual Storage Architecture

Feedback data is stored in two systems:

1. **PostgreSQL `feedback_events` table** — Structured storage for individual
   feedback events with user_id, suggestion_id, action, context, and timestamp.
   Used for audit trails, analytics, and reprocessing.

2. **mem0 AsyncMemory** — Semantic memory extraction. mem0 processes feedback
   events to extract patterns (e.g., "user prefers short sentences", "user
   avoids purple prose"). These extracted preferences are semantic, searchable,
   and can be injected into prompts.

### mem0 AsyncMemory Integration

```python
# mem0_client.py — factory creates client with user-configurable provider
class Mem0Client:
    """Creates AsyncMemory with user's LLM provider settings."""

    async def create(self, user_id: str) -> AsyncMemory:
        settings = await self._load_user_settings(user_id)
        return AsyncMemory(
            llm=self._build_llm_client(settings),
            vector_store=pgvector_config,
            ...
        )
```

- **LLM provider**: Configurable via user's AI settings (same provider/model as the gateway)
- **Cost-efficient defaults**: Haiku (Anthropic), GPT-4.1-nano (OpenAI), Llama3.2 (Ollama)
- **pgvector backend**: Uses existing PostgreSQL + pgvector for memory storage
- **RULE-01 exception**: mem0 requires direct LLM client for internal extraction

### NullMemoryClient — Graceful Degradation

When mem0 is unavailable (not configured, connection failure, etc.), the system
uses `NullMemoryClient` which implements the same `MemoryClientProtocol` but
returns empty results. This ensures:

- No hard dependency on mem0 at request time
- The application starts and functions without memory
- Feedback events are still recorded to PostgreSQL (can be processed later)
- Users see no errors — just no personalization

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/memory/feedback` | Record feedback on an AI suggestion |
| GET | `/memory/preferences` | Get current preference profile |
| DELETE | `/memory/preferences` | Reset all preferences |

### Integration with Prompts

`PreferenceService` formats extracted preferences for prompt injection:
- `user_preferences` — Style patterns the user prefers
- `avoidance_patterns` — Patterns the user has rejected
- `style_constraints` — Explicit style rules

`PromptComposer` auto-injects these via `PromptContext` fields into
`{{user_preferences}}` blocks in system prompts.

### Migration

- `0006_feedback_events.py` — Creates `feedback_events` table with columns:
  `id`, `user_id`, `suggestion_id`, `action` (enum), `context` (JSONB),
  `modification` (text, nullable), `created_at`

## Constraints & Edge Cases

- Requires minimum 20 feedback events before patterns emerge
- Cold start: No adaptation until data accumulated — NullMemoryClient handles this gracefully
- Conflicting signals: Accept/reject of similar patterns both recorded
- Reset required for major creative direction changes
- Learning can be disabled (fallback to default behavior via NullMemoryClient)
- Privacy: All data stored locally in PostgreSQL, never transmitted
- mem0 LLM calls are infrastructure-level (RULE-01 exception) — cost-efficient models only
- If mem0 is unavailable, feedback events still recorded to PostgreSQL for later processing

## Related Features

- [LEARN-001](../learning/LEARN-001-feedback-loop.md) — User-facing feedback collection
- [LEARN-002](../learning/LEARN-002-style-adaptation.md) — Style profile application
- [WRITE-006](../writing/WRITE-006-co-author.md) — Co-author benefits from learning
- [INFRA-002](INFRA-002-prompt-system.md) — Prompts consume preference variables

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-15` — Core memory module implemented: mem0 AsyncMemory integration, dual storage (PostgreSQL + mem0), FeedbackService, PreferenceService, NullMemoryClient, API endpoints (POST /feedback, GET /preferences, DELETE /preferences), migration 0006
