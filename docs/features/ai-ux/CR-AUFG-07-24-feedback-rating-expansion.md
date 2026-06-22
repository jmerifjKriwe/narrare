---
id: CR-AUFG-07-24
title: "AI Feedback Rating Expansion"
status: planned
area: ai-ux
mvp: false
ui_tooltip: "Rate more AI outputs so Narrare can learn from useful and unhelpful suggestions."
ui_help_short: |
  Feedback rating expands the existing learning loop to Co-Author, KB flows, and
  Chat while preserving privacy-safe memory semantics.
ui_help_long: |
  Writers can rate AI suggestions in more places. Ratings are routed through the
  existing feedback/memory service, not stored as disconnected UI-only events.
ui_available_in: [editor, kb, chat]
service: apps/api/narrare/memory/service.py
contract: apps/api/narrare/memory/contracts.py#FeedbackServiceProtocol
router: apps/api/narrare/memory/router.py
prompt: ~
requires: [LEARN-001, INFRA-005, WRITE-006, KB-002, KB-003, CHAT-001]
---

# CR-AUFG-07-24 — AI Feedback Rating Expansion

## Problem / Root cause

**Symptom:** LEARN-001 supports feedback/rating, but ratings are not consistently available across Co-Author, KB AI flows, and Chat outputs.

**Warum 1?** Each AI surface implemented accept/reject/apply controls around its own output shape and did not consistently emit rating-grade feedback.

**Warum 2?** The learning system exists, but CR-07 compliance focused on visible lifecycle/action controls rather than expanding feedback capture to every useful AI output.

**Root cause:** Feedback collection is service-capable but UI adoption is incomplete and lacks a cross-feature source taxonomy.

## User-facing behavior and acceptance criteria

- Co-Author suggestions, KB field/enhance/improve suggestions, and Chat assistant answers expose an optional rating affordance after visible output.
- Rating is lightweight: 1–5 or thumbs up/down plus optional reason, using the existing canonical rating vocabulary.
- Rating submission is non-blocking and never prevents accept/reject/apply.
- Users can skip rating.
- Privacy copy explains that learning stores preference summaries/events locally according to LEARN-001/INFRA-005.
- Tests prove feedback reaches the intended service/memory boundary, not just local UI state.

## Architecture fit and layer ownership

| Layer | Ownership |
|-------|-----------|
| Core | Reuses memory feedback models; extend enums/value objects only if source taxonomy is closed. |
| Backend | Owns feedback schema compatibility, validation, and service routing to existing feedback persistence/memory path. |
| Frontend | Owns reusable rating component and per-feature adapters for suggestion metadata. |
| Platform | Adds contract tests and inventory entries for rating-enabled operations. |
| Docs | Updates LEARN-001/INFRA-005 help after evidence exists. |

## API/contract implications

- Prefer reusing `POST /memory/feedback` through `FeedbackServiceProtocol.record_feedback(request: FeedbackRequest, user_id: uuid.UUID) -> FeedbackResponse`.
- Any backend expansion must extend the existing `record_feedback` request/schema path explicitly; it must not introduce or depend on a nonexistent `FeedbackServiceProtocol.record()` method.
- Add a typed source taxonomy if needed: `co_author_change`, `kb_field_suggest`, `kb_enhance_field`, `kb_improve_suggestion`, `chat_message`.
- Feedback payload must include stable `suggestion_id` or equivalent `(source_type, source_id, operation_id)` so ratings are not orphaned.
- If backend Pydantic schemas change, update frontend types and API↔Frontend contract tests in the same change.

## Data model/migration implications

- Preferred: reuse existing `feedback_events.context` JSONB for source metadata.
- If existing enum columns reject new source types, add an Alembic migration and rollback test.
- Do not persist raw excerpts to mem0 memory text; use privacy-safe summaries per INFRA-005.

## i18n requirements

- DE/EN/FR keys for expanded rating labels, optional reason placeholders, submitted/failed states, skip, and privacy explanation.
- Use `studio.aiActions.rating`, `submitRating`, `skipRating`, and `ratingSubmitted` where possible.

## AI-UX lifecycle requirements

- Rating submission is a short REST operation with loading, success, error, retry, and skip states.
- Failed rating does not remove or alter the AI output.
- Partial output cannot be rated until the source operation is complete or explicitly stopped and preserved.
- Connection-loss on source AI output preserves rating availability for preserved output where a stable source id exists.

## Tests/enforcement gates required

- Backend tests for accepted source taxonomy and privacy-safe memory event generation.
- Frontend tests for Co-Author, KB flows, and Chat rating submission/skip/error states.
- API↔Frontend schema parity if payload changes.
- Memory/feedback tests proving events reach PostgreSQL and, where configured, the memory boundary.
- AI Operation Inventory updates for rating support on `writing.co_author`, KB operations, and `chat.free_assistant`.

## Alternatives considered

1. **UI-only ratings for analytics later.** Rejected: violates RULE-20 and would duplicate learning data.
2. **Separate rating service.** Rejected: LEARN-001 already defines feedback persistence and memory semantics.
3. **Reusable rating adapter over existing feedback service (chosen).** Best fit: one learning path, privacy-safe, and testable.

## Explicit out-of-scope

- Automatic preference profile retraining beyond existing LEARN-001 behavior.
- Public/shared ratings across users.
- Rating every token/chunk during streaming.

## Dependencies/order constraints

- Should follow or accompany CR-AUFG-07-18 so ratings attach to standardized output states.
- Should precede CR-AUFG-07-22 if style variants include rating in the first slice.
