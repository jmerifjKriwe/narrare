---
id: LEARN-001
title: "Feedback & Learning Loop"
status: implemented
area: learning
mvp: false

ui_tooltip: "AI learns from your feedback to improve future suggestions."
ui_help_short: |
  The AI learns from your preferences over time. Accept, reject, or modify
  suggestions and the system adapts — improving future recommendations
  to match your writing style and creative preferences.
ui_help_long: |
  ## Feedback & Learning Loop

  AI that gets better at helping you by learning from your feedback.

  **Feedback Types**
  - **Accept**: Suggestion was useful and used
  - **Reject**: Suggestion was not useful
  - **Modify**: Suggestion was useful but needed changes
  - **Rate**: Quality score (1-5 stars) for granularity

  **What Gets Learned**
  - **Style Preferences**: Sentence structure, descriptive density, dialogue
  - **Content Preferences**: Thematic interests, genre leanings, character types
  - **Structure Preferences**: Scene length, chapter organization, pacing
  - **Avoidance Patterns**: What you consistently reject

  **Learning Application**
  - **Positive Context**: Highlights preferred styles in generation
  - **Negative Constraints**: Explicitly avoids rejected patterns
  - **Continuous Improvement**: Adapts over time based on feedback
  - **Per-Project Learning**: Different preferences per novel

  **How it works:**
  1. Receive AI suggestion (continuation, rewrite, etc.)
  2. Provide feedback:
     - Click ✓ to accept
     - Click ✗ to reject
     - Edit before accepting (counts as modify)
     - Optional: Rate 1-5 stars
  3. System records:
     - What was suggested
     - Your feedback type
     - What you changed (if modified)
     - Context (chapter, feature type)
  4. Future suggestions incorporate learning
  5. View your preference profile in Settings

  **Best practices:**
  - Be consistent with feedback for pattern recognition
  - Explain rejections when possible for better learning
  - Review preference profile periodically
  - Reset preferences when changing creative direction
  - Provide feedback even for imperfect suggestions

  Available globally (feedback on any AI suggestion) or via CLI:
  `narrare learning feedback submit --suggestion <id> --action reject --reason "too wordy"`
ui_available_in: [global, cli]

service: memory/service.py
contract: memory/contracts.py#FeedbackServiceProtocol
router: memory/router.py
prompt: ~
requires: [INFRA-005, ADR-033]
---

# LEARN-001 — Feedback & Learning Loop

## What it does

Adaptive AI system that learns from user feedback. Tracks accept/reject/modify actions on AI suggestions, identifies patterns in preferences, and incorporates learning into future generations to better match individual writing style and creative preferences.

## Why it exists

Generic AI suggestions don't match every writer's style. Writers have unique preferences for sentence length, dialogue style, descriptive density, pacing. By learning from feedback, the AI adapts to each writer's voice and provides more relevant, personalized suggestions over time.

## How it works (User perspective)

1. Receive any AI suggestion:
   - Text continuation
   - Rewrite options
   - Plot ideas
   - Character dialogue
2. Provide feedback:
   - Click ✓ (accept) — suggestion was useful
   - Click ✗ (reject) — suggestion not useful
   - Edit before accepting — suggestion useful but needed changes
   - Optional: Rate 1-5 stars for detail
3. System records:
   - What was suggested
   - Your feedback type
   - What you changed (if modified)
   - Context (chapter, feature)
4. Future suggestions improve based on your patterns
5. View preference profile in Settings → Learning

## How it works (Technical)

**Entry point:** Implicit on all AI interactions via `apps/api/narrare/memory/service.py`
**Service:** `FeedbackService.record()` and `LearningService.apply()` in `apps/api/narrare/memory/service.py`
**Contract:** `FeedbackServiceProtocol` in `apps/api/narrare/memory/contracts.py`

**Architecture per ADR-033:** Feedback events are stored in two systems: PostgreSQL `feedback_events` table for structured audit, and mem0 AsyncMemory (OSS, local-first, pgvector) for semantic preference extraction. mem0 supersedes the earlier 4-tier embedding cascade (ADR-017 → ADR-033).

**Feedback record:**
```python
class FeedbackRecord:
    id: UUID
    suggestion_id: UUID
    suggestion_type: SuggestionType  # continuation, rewrite, plot, etc.
    action: FeedbackAction  # accept, reject, modify
    rating: int | None  # 1-5 if provided
    context: str  # Chapter, genre, feature
    modification: str | None  # What user changed (if modified)
    timestamp: datetime
```

**Learning extraction:**
- Style patterns: Sentence length, vocabulary, structure
- Content patterns: Themes, genres, character types
- Avoidance patterns: Consistently rejected elements
- Weight calculation: Frequency × recency × confidence

**Application:**
- Positive patterns: Added to few-shot examples
- Negative patterns: Added as constraints
- Per-project profiles: Different preferences per novel
- Continuous adaptation: Re-weights over time

### Rating expansion (CR-AUFG-07-24)

Writers can rate AI outputs from Co-Author, KB field-suggest, KB enhance,
KB improve, and Chat. Each rating reuses `POST /memory/feedback` and is
tagged with a closed `source_type` vocabulary:

- `co_author_change`
- `kb_field_suggest`
- `kb_enhance_field`
- `kb_improve_suggestion`
- `chat_message`

Ratings never alter the original AI output and never block accept/reject/apply.
mem0 forwarding remains privacy-safe: only `action`, `intent`, `rating`,
optional `rating_reason`, and `source_type` reach the memory layer. Raw prose
is never persisted to mem0 (RULE-22 / INFRA-005).

The backend derives a deterministic UUID from `(source_id`, `source_type)`
server-side (`apps/api/narrare/memory/suggestion_identity.py`); the raw
`source_id` never reaches core or mem0 (RULE-22). The frontend sends
`source_id` + `source_type` and forwards `suggestion_id` only when the surface
id is itself a valid UUID.

## Constraints & Edge Cases

- Requires significant feedback (50+ interactions) for noticeable improvement
- May overfit to recent feedback patterns
- Conflicting feedback sends mixed signals
- Preferences may change as writer evolves
- Cannot learn unspoken preferences (only feedback)
- Learning is per-user, not shared across projects
- Reset required for major creative direction changes
- May reduce creative variety (over-optimization)

## Related Features

- [INFRA-005](../infra/INFRA-005-memory-layer.md) — Persistent preference storage
- [WRITE-001](../writing/WRITE-001-editor.md) — Suggestion feedback source
- [LEARN-002](LEARN-002-style-adaptation.md) — Style profiling
- [ANAL-007](../analysis/ANAL-007-voice-author.md) — Voice analysis

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-21` — **Implemented.** Full feedback loop wired: 4-tier embedding cascade (OpenAI → provider-native → sentence-transformers → disabled) ensures all users get memory regardless of LLM provider. FeedbackEvent extended with rating + enriched context. mem0 AsyncMemory replaces NullMemoryClient for configured users. PreferenceAnalysisAgent performs periodic deep analysis persisted to preference_profiles table. Frontend adds modify-tracking in GenerationDraft, RatingPrompt inline UI, preference profile page (LearningTab), and LearningStatus progress indicator. Event-driven processing via FeedbackRecorded/PreferenceAnalysisTriggered events → TaskIQ tasks. 55 tasks, 3 migrations.
- `2026-06-22` — ADR-033 applied: mem0 OSS documented as preference extraction backend (supersedes ADR-017 embedding cascade)
