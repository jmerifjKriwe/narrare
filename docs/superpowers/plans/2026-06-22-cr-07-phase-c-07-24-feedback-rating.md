# CR-AUFG-07-24 — AI Feedback Rating Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Commit policy:** This plan contains **NO commit steps** per coordinator instruction.
> Each task ends with a `Checkpoint` (tests green, ready for review) instead of `git commit`.
> The coordinator decides when/whether to commit at the end of the whole plan.

**Goal:** Make rating available on Co-Author change review, KB field-suggest/enhance/improve, and Chat assistant answers by reusing `POST /memory/feedback` and adding a typed source taxonomy plus a shared, accessible `AIRating` frontend component.

**Architecture:** The existing `FeedbackServiceProtocol.record_feedback` and `FeedbackRequest.rating` already work end-to-end. CR-AUFG-07-24 only adds (1) a closed `source_type` vocabulary so ratings are never orphaned, (2) a reusable, accessible frontend rating primitive modeled exactly on the CR-AUFG-07-18 `AIDiffView` pattern (contracts → component → adapters → per-surface adoption), and (3) inventory/docs evidence. No new service, no new endpoint, no Alembic migration (source_type rides the existing `feedback_events.context` JSONB).

**Tech Stack:** Python 3.14 + Pydantic v2 + SQLAlchemy 2.0 (backend); Next.js 16 + React 19 + TypeScript strict + TanStack Query + next-intl (frontend); Vitest + Testing Library (frontend tests); pytest (backend tests).

---

## Spec → Plan traceability

| Spec requirement (CR-AUFG-07-24) | Task(s) |
|-----------------------------------|---------|
| Reuse `POST /memory/feedback` via `FeedbackServiceProtocol.record_feedback` | All adoption tasks (8–12) call `useRecordFeedback` → `memoryApi.recordFeedback` |
| Do **NOT** introduce `record()` method | No contract change in Task 2/3 — only `source_type` field |
| Typed source taxonomy: `co_author_change`, `kb_field_suggest`, `kb_enhance_field`, `kb_improve_suggestion`, `chat_message` | Task 1 (Core enum), Task 2 (schema), Task 4 (TS type), Tasks 8–12 (per-surface usage) |
| Stable `suggestion_id` so ratings are not orphaned | Each adapter supplies `sourceId`; Task 5 contract requires it |
| Reuse existing `feedback_events.context` JSONB for source metadata | Task 3 service plumbing; **no migration** |
| Privacy-safe memory text (no raw excerpts) | Task 3 enriches mem0 metadata only; existing `_translate_to_memory_text` already privacy-safe |
| Frontend: reusable rating component + per-feature adapters | Tasks 5, 6, 7 |
| Co-Author / KB field+enhance+improve / Chat adoption | Tasks 8, 9, 10, 11, 12 |
| i18n DE/EN/FR: `studio.aiActions.rating`, `submitRating`, `skipRating`, `ratingSubmitted`, privacy notice | Task 15 |
| AI Operation Inventory updates (`writing.co_author`, KB ops, `chat.free_assistant`) | Task 13 |
| API↔Frontend schema parity test | Task 14 |
| Backend tests: source taxonomy + privacy-safe memory event | Tasks 2, 3 |
| Frontend tests: submission/skip/error states | Tasks 6, 7, 8–12 |

---

## File structure (decomposition)

### Backend (apps/api + packages/core)
- **Create:** `packages/core/narrare_core/memory/source_types.py` — `FeedbackSourceType` StrEnum (single source of truth for the taxonomy). Kept in its own file for RULE-04 (one responsibility per file).
- **Modify:** `apps/api/narrare/memory/schemas.py` — add `source_type` field with `Literal` validation against the core enum members.
- **Modify:** `apps/api/narrare/memory/service.py` — copy `request.source_type` into `context["source_type"]` (NO service-logic change; just metadata enrichment alongside existing `chapter_id`/`genre`/`mode`).
- **Test:** `tests/unit/core/memory/test_source_types.py` (NEW)
- **Test:** `tests/unit/api/memory/test_memory_schemas.py` (extend)
- **Test:** `tests/unit/api/memory/test_memory_service.py` (extend)

### Frontend — shared rating primitive (mirrors `lib/ai-diff/*` + `components/shared/ai-diff/*`)
- **Create:** `packages/web/lib/ai-rating/contracts.ts` — `AIRatingViewModel`, `AIRatingState`, `AIRatingScale` (RULE-03: contract first).
- **Create:** `packages/web/lib/ai-rating/adapters/coauthor.ts` — builds `AIRatingViewModel` from a Co-Author `ChangeDetail`.
- **Create:** `packages/web/lib/ai-rating/adapters/kb-field.ts` — from a KB field-suggest payload.
- **Create:** `packages/web/lib/ai-rating/adapters/kb-enhance.ts` — from `KBEnhancementResult`.
- **Create:** `packages/web/lib/ai-rating/adapters/kb-improve.ts` — from `ImproveSuggestion`.
- **Create:** `packages/web/lib/ai-rating/adapters/chat.ts` — from a Chat assistant message.
- **Create:** `packages/web/lib/ai-rating/index.ts` — public surface.
- **Create:** `packages/web/lib/ai-rating/build-feedback.ts` — pure helper that maps `AIRatingViewModel` + rating → `FeedbackRequest` (single source of truth for the payload shape; DRY).
- **Create:** `packages/web/lib/hooks/useAIRating.ts` — wraps `useRecordFeedback` with loading/success/error/skip state and a typed `submit`/`skip` API.
- **Create:** `packages/web/components/shared/ai-rating/AIRating.tsx` — accessible rating control (1–5 scale + optional reason + skip + privacy notice + loading/success/error/retry).
- **Test:** `packages/web/lib/ai-rating/__tests__/contracts.test.ts`
- **Test:** `packages/web/lib/ai-rating/__tests__/build-feedback.test.ts`
- **Test:** `packages/web/lib/ai-rating/__tests__/adapters/coauthor.test.ts`
- **Test:** `packages/web/lib/ai-rating/__tests__/adapters/kb-field.test.ts`
- **Test:** `packages/web/lib/ai-rating/__tests__/adapters/kb-enhance.test.ts`
- **Test:** `packages/web/lib/ai-rating/__tests__/adapters/kb-improve.test.ts`
- **Test:** `packages/web/lib/ai-rating/__tests__/adapters/chat.test.ts`
- **Test:** `packages/web/components/shared/ai-rating/__tests__/AIRating.test.tsx`
- **Test:** `packages/web/lib/hooks/__tests__/useAIRating.test.tsx`

### Frontend — adoption (per surface)
- **Modify:** `packages/web/components/studio/editor/ChangeReview.tsx` (Co-Author change review) — render `AIRating` after accept/reject decision.
- **Modify:** `packages/web/components/studio/kb/_components/EnhanceReviewCard.tsx` — render `AIRating` after accept/reject.
- **Modify:** `packages/web/components/studio/kb/_components/ImproveSuggestionCard.tsx` — render `AIRating` after accept/reject.
- **Modify:** `packages/web/components/studio/kb/_components/FieldSuggestionReview.tsx` — render `AIRating` after accept/reject.
- **Modify:** `packages/web/components/studio/editor/ChatMessage.tsx` — render `AIRating` on assistant prose blocks.
- **Tests:** one interaction test per surface under each surface's existing `__tests__/` directory.

### Platform / governance
- **Modify:** `scripts/checks/ai_operation_inventory.yaml` — add `rating_support: true` + adapter path for `writing.co_author`, `kb.field_suggest`, `kb.enhance`, `kb.improve`, `chat.free_assistant`.
- **Create:** `tests/integration/memory/test_feedback_source_type_parity.py` — proves schema fields are symmetric across API Pydantic model and the TS type literal (single source-of-truth assertion via a shared literal list).

### Docs
- **Modify:** `packages/i18n/messages/{de,en,fr}/studio.json` — add `aiActions.ratingPrivacyNotice`, `aiActions.ratingError`, `aiActions.ratingRetry`, plus per-surface `rating` variants if needed (prefer reusing existing `aiActions.rating` / `submitRating` / `skipRating` / `ratingSubmitted`).
- **Modify:** `docs/architecture/governance/aufg-registry.md` — set CR-AUFG-07-24 lifecycle evidence pointer once tasks complete.
- **Modify:** relevant LEARN-001 / INFRA-005 help docs (see Task 16 for exact paths).

---

## RULE-XX Compliance

| Rule | Status | Evidence in plan |
|------|--------|------------------|
| RULE-01b | ✅ | No LLM calls introduced; pure feedback path |
| RULE-02 / 02a / 02b | ✅ | No prompts involved |
| RULE-03 | ✅ | `lib/ai-rating/contracts.ts` written BEFORE `AIRating.tsx` (Task 5 before Task 6) |
| RULE-04 | ✅ | Each adapter in its own file; `source_types.py` isolated; `AIRating.tsx` ≤ ~120 lines |
| RULE-05 | ✅ | Frontend adapters depend only on `contracts.ts`; surfaces depend on `useAIRating` + adapter — no cycles |
| RULE-06 | ✅ | `build-feedback.ts` is the single payload builder; `AIRating.tsx` owns only rendering; `useAIRating` owns only mutation state |
| RULE-07 | ✅ | Backend dependency unchanged: router → service → repo; `source_type` is data, not a new arrow |
| RULE-09 | ✅ | All TS public surfaces fully typed; Pydantic `Literal` for closed taxonomy |
| RULE-10 | ✅ | Every task has a TDD test step with exact command + expected output |
| RULE-11 | ✅ | `AIRating` exposes error+retry state; `useRecordFeedback` onError is non-blocking (per spec) but surfaced to UI |
| RULE-12 | ✅ | All adoption goes through Service Layer (`POST /memory/feedback`); no client-to-client calls |
| RULE-13 | ✅ | Rating is REST-only (no SSE); spec explicitly scopes this to "short REST operation" — documented exception |
| RULE-16 | ✅ | All visible strings via `studio.aiActions.*` keys; no hardcoded English; accessible roles (`radiogroup`/`radio`) |
| RULE-20 | ✅ | Ratings route through the same learning path as accept/reject — no parallel analytics store |
| RULE-22 | ✅ | mem0 metadata carries `source_type` only; raw prose never enters memory text (existing `_translate_to_memory_text` already enforces) |

**Streaming decision (RULE-13):** Rating is a short fire-and-forget REST POST, intentionally not SSE-backed. This matches the spec's explicit framing ("Rating submission is a short REST operation"). No SSE infrastructure is bypassed — there is no streaming endpoint for feedback to consume.

---

## Task 1: Core — `FeedbackSourceType` taxonomy enum

**Files:**
- Create: `packages/core/narrare_core/memory/source_types.py`
- Test: `tests/unit/core/memory/test_source_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/core/memory/test_source_types.py`:

```python
"""Unit tests for FeedbackSourceType — closed source taxonomy (CR-AUFG-07-24)."""

from __future__ import annotations

from narrare_core.memory.source_types import FeedbackSourceType


def test_taxonomy_contains_exactly_the_five_required_sources() -> None:
    members = {m.value for m in FeedbackSourceType}
    assert members == {
        "co_author_change",
        "kb_field_suggest",
        "kb_enhance_field",
        "kb_improve_suggestion",
        "chat_message",
    }


def test_each_member_round_trips_through_its_value() -> None:
    for member in FeedbackSourceType:
        assert FeedbackSourceType(member.value) is member


def test_unknown_source_raises_value_error() -> None:
    import pytest

    with pytest.raises(ValueError):
        FeedbackSourceType("totally_made_up_source")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/core/memory/test_source_types.py -v`
Expected: FAIL with `ImportError: cannot import name 'FeedbackSourceType'`.

- [ ] **Step 3: Write the minimal implementation**

Create `packages/core/narrare_core/memory/source_types.py`:

```python
"""Closed source taxonomy for feedback events (CR-AUFG-07-24).

A single source of truth for *where* a feedback event originated so ratings
are never orphaned. Reused by:

- Backend Pydantic schema (``apps/api/narrare/memory/schemas.py``) via a
  ``Literal`` of the member values.
- Frontend TypeScript type (``packages/web/types/feedback.ts``) via a union
  of the same string literals.

Both mirrors MUST stay in sync with this enum — see
``tests/integration/memory/test_feedback_source_type_parity.py`` (Task 14).
"""

from __future__ import annotations

from enum import StrEnum


class FeedbackSourceType(StrEnum):
    """Where a feedback event originated.

    Adding a member here REQUIRES updating:
      * ``apps/api/narrare/memory/schemas.py`` (``FeedbackRequest.source_type``)
      * ``packages/web/types/feedback.ts`` (``FeedbackSourceType`` union)
      * ``tests/integration/memory/test_feedback_source_type_parity.py``
      * an adapter in ``packages/web/lib/ai-rating/adapters/``
    """

    CO_AUTHOR_CHANGE = "co_author_change"
    KB_FIELD_SUGGEST = "kb_field_suggest"
    KB_ENHANCE_FIELD = "kb_enhance_field"
    KB_IMPROVE_SUGGESTION = "kb_improve_suggestion"
    CHAT_MESSAGE = "chat_message"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/core/memory/test_source_types.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Checkpoint (NO commit per plan policy)**

Verify: `pytest tests/unit/core/memory/ -v` all green. Core layer done.

---

## Task 2: Backend — `source_type` schema field with closed-vocabulary validation

**Files:**
- Modify: `apps/api/narrare/memory/schemas.py`
- Test: `tests/unit/api/memory/test_memory_schemas.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/api/memory/test_memory_schemas.py` (inside `class TestFeedbackRequest`):

```python
    def test_source_type_accepts_each_canonical_value(self) -> None:
        from narrare_core.memory.source_types import FeedbackSourceType

        for member in FeedbackSourceType:
            req = FeedbackRequest(
                action="accept",
                suggestion_id=uuid4(),
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
                source_type=member.value,
            )
            assert req.source_type == member.value

    def test_source_type_rejects_unknown_value(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                suggestion_id=uuid4(),
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
                source_type="made_up_source",
            )

    def test_source_type_defaults_to_none(self) -> None:
        """Existing callers without source_type keep working (back-compat)."""
        req = FeedbackRequest(
            action="accept",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="text",
            project_id=uuid4(),
        )
        assert req.source_type is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/api/memory/test_memory_schemas.py::TestFeedbackRequest::test_source_type_accepts_each_canonical_value -v`
Expected: FAIL with `ValidationError` / `AttributeError` (field does not exist yet).

- [ ] **Step 3: Implement — add `source_type` with `Literal` validation**

In `apps/api/narrare/memory/schemas.py`, change the imports and add the field. Replace the existing import block:

```python
from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from narrare_core.memory.source_types import FeedbackSourceType

# Closed-vocabulary literal derived from the canonical enum so Pydantic
# rejects unknown sources at the schema boundary (CR-AUFG-07-24).
# The Literal MUST stay in sync with FeedbackSourceType — enforced by
# tests/integration/memory/test_feedback_source_type_parity.py (Task 14).
_FeedbackSourceTypeLiteral = Literal[
    FeedbackSourceType.CO_AUTHOR_CHANGE.value,
    FeedbackSourceType.KB_FIELD_SUGGEST.value,
    FeedbackSourceType.KB_ENHANCE_FIELD.value,
    FeedbackSourceType.KB_IMPROVE_SUGGESTION.value,
    FeedbackSourceType.CHAT_MESSAGE.value,
]
```

Then add the field to `FeedbackRequest` (place it immediately after `intent` for readability):

```python
class FeedbackRequest(BaseModel):
    """Request body for recording user feedback on an AI suggestion."""

    action: str = Field(..., pattern="^(accept|reject|modify)$")
    suggestion_id: uuid.UUID
    intent: str = Field(..., min_length=1, max_length=50)
    source_type: _FeedbackSourceTypeLiteral | None = Field(
        default=None,
        description="Where the rated suggestion originated (CR-AUFG-07-24 taxonomy).",
    )
    suggestion_text: str = Field(..., min_length=1)
    modification: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5, description="Optional 1-5 rating")
    context: dict[str, object] | None = None
    project_id: uuid.UUID
    chapter_id: uuid.UUID | None = None
    genre: str | None = None
    mode: str | None = None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/api/memory/test_memory_schemas.py -v`
Expected: PASS (all schema tests including the 3 new ones).

- [ ] **Step 5: Checkpoint (NO commit per plan policy)**

Verify full schema suite: `pytest tests/unit/api/memory/test_memory_schemas.py -v`.

---

## Task 3: Backend — service plumbing for `source_type` into context + mem0 metadata

**Files:**
- Modify: `apps/api/narrare/memory/service.py`
- Test: `tests/unit/api/memory/test_memory_service.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append inside `class TestRecordFeedback` in `tests/unit/api/memory/test_memory_service.py`:

```python
    async def test_record_feedback_propagates_source_type_into_context(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        request = _make_feedback_request(source_type="co_author_change")

        await feedback_service.record_feedback(request, uuid4())

        event = fake_core_feedback.recorded[0]
        assert event.context["source_type"] == "co_author_change"

    async def test_record_feedback_omits_source_type_key_when_none(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        """Back-compat: existing callers without source_type must not see a key."""
        request = _make_feedback_request()  # source_type defaults to None

        await feedback_service.record_feedback(request, uuid4())

        event = fake_core_feedback.recorded[0]
        assert "source_type" not in event.context
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/api/memory/test_memory_service.py::TestRecordFeedback::test_record_feedback_propagates_source_type_into_context -v`
Expected: FAIL with `KeyError: 'source_type'`.

- [ ] **Step 3: Implement — add `source_type` enrichment in `MemoryFeedbackService.record_feedback`**

In `apps/api/narrare/memory/service.py`, locate the context-enrichment block (currently lines ~67–73):

```python
        # Build enriched context with additional metadata
        context = dict(request.context) if request.context else {}
        if request.chapter_id:
            context["chapter_id"] = str(request.chapter_id)
        if request.genre:
            context["genre"] = request.genre
        if request.mode:
            context["mode"] = request.mode
```

Insert the source_type line after the `mode` block:

```python
        if request.mode:
            context["mode"] = request.mode
        if request.source_type:
            context["source_type"] = request.source_type
```

No other change is required — the existing `FeedbackEvent(context=context)` already carries it through to `persist_fn` and into the `feedback_events.context` JSONB column. mem0 metadata enrichment is handled by core `FeedbackService` via `event.context` (no core change needed for the audit trail; the next step only adds source_type to the mem0 metadata for preference routing).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/api/memory/test_memory_service.py -v`
Expected: PASS (all service tests including the 2 new ones).

- [ ] **Step 5: Add mem0 metadata enrichment (core FeedbackService)**

The existing `packages/core/narrare_core/memory/feedback_service.py` `record()` method already builds mem0 metadata from the event. Add `source_type` to that metadata so preference extraction can route by source. Locate the `metadata={...}` block (currently lines ~62–68):

```python
                metadata={
                    "action": event.action.value,
                    "intent": event.intent,
                    "suggestion_id": str(event.suggestion_id),
                    "project_id": str(event.project_id),
                },
```

Replace with:

```python
                metadata={
                    "action": event.action.value,
                    "intent": event.intent,
                    "suggestion_id": str(event.suggestion_id),
                    "project_id": str(event.project_id),
                    "source_type": event.context.get("source_type"),
                },
```

Add the corresponding test to `tests/unit/core/memory/test_feedback_service.py` (or create it if missing). First check whether the file exists:

Run: `ls tests/unit/core/memory/test_feedback_service.py`

If missing, create `tests/unit/core/memory/test_feedback_service.py`:

```python
"""Unit tests for core FeedbackService — mem0 forwarding (CR-AUFG-07-24)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from narrare_core.memory.feedback_service import FeedbackService
from narrare_core.memory.models import FeedbackAction, FeedbackEvent


class FakeMem0:
    def __init__(self) -> None:
        self.added: list[dict[str, Any]] = []

    async def add(self, *, messages: str, user_id: str, agent_id: str, metadata: dict[str, Any]) -> None:
        self.added.append(
            {"messages": messages, "user_id": user_id, "agent_id": agent_id, "metadata": metadata}
        )


async def _persist(_event: FeedbackEvent) -> None:
    return None


@pytest.mark.asyncio
async def test_record_forwards_source_type_to_mem0_metadata() -> None:
    mem0 = FakeMem0()
    service = FeedbackService(mem0_client=mem0, persist_fn=_persist)

    event = FeedbackEvent(
        user_id=uuid4(),
        project_id=uuid4(),
        suggestion_id=uuid4(),
        action=FeedbackAction.ACCEPT,
        intent="write",
        suggestion_text="The forest was dark.",
        context={"source_type": "chat_message"},
    )

    await service.record(event)

    assert mem0.added
    assert mem0.added[0]["metadata"]["source_type"] == "chat_message"


@pytest.mark.asyncio
async def test_record_mem0_metadata_source_type_none_when_absent() -> None:
    mem0 = FakeMem0()
    service = FeedbackService(mem0_client=mem0, persist_fn=_persist)

    event = FeedbackEvent(
        user_id=uuid4(),
        project_id=uuid4(),
        suggestion_id=uuid4(),
        action=FeedbackAction.ACCEPT,
        intent="write",
        suggestion_text="x",
        context={},
    )

    await service.record(event)

    assert mem0.added[0]["metadata"]["source_type"] is None
```

- [ ] **Step 6: Run all memory tests to verify everything is green**

Run: `pytest tests/unit/core/memory/ tests/unit/api/memory/ -v`
Expected: PASS (all tests including the new mem0 source_type tests).

- [ ] **Step 7: Checkpoint (NO commit per plan policy)**

Backend layer complete. Source taxonomy is now: enum → schema validation → context JSONB → mem0 metadata. No migration required.

---

## Task 4: Frontend types — `source_type` on `FeedbackRequest`

**Files:**
- Modify: `packages/web/types/feedback.ts`

- [ ] **Step 1: Write the failing test**

The TS type itself has no runtime test — its parity with the backend is enforced by Task 14's integration test. For this task, the test is the next consumer (Task 5's `build-feedback.ts`).

Add the type change first. In `packages/web/types/feedback.ts`, replace the `FeedbackRequest` interface (lines 5–17) with:

```typescript
/**
 * Closed-vocabulary source taxonomy (CR-AUFG-07-24).
 *
 * MUST stay in sync with `packages/core/narrare_core/memory/source_types.py`
 * `FeedbackSourceType` — enforced by
 * `tests/integration/memory/test_feedback_source_type_parity.py`.
 */
export type FeedbackSourceType =
  | "co_author_change"
  | "kb_field_suggest"
  | "kb_enhance_field"
  | "kb_improve_suggestion"
  | "chat_message";

export interface FeedbackRequest {
  action: FeedbackAction;
  suggestion_id: string;
  intent: string;
  source_type?: FeedbackSourceType | null;
  suggestion_text: string;
  modification?: string | null;
  rating?: number | null;
  context?: Record<string, unknown> | null;
  project_id: string;
  chapter_id?: string | null;
  genre?: string | null;
  mode?: string | null;
}
```

- [ ] **Step 2: Type-check the change**

Run: `cd packages/web && pnpm exec tsc --noEmit`
Expected: PASS (no type errors). Existing callers don't set `source_type` — it's optional, so they continue to compile.

- [ ] **Step 3: Checkpoint (NO commit per plan policy)**

Frontend type parity ready. Adapters in Task 5 will set `source_type` explicitly.

---

## Task 5: Frontend — `ai-rating` contracts + payload builder (RULE-03 contract first)

**Files:**
- Create: `packages/web/lib/ai-rating/contracts.ts`
- Create: `packages/web/lib/ai-rating/build-feedback.ts`
- Create: `packages/web/lib/ai-rating/index.ts`
- Test: `packages/web/lib/ai-rating/__tests__/contracts.test.ts`
- Test: `packages/web/lib/ai-rating/__tests__/build-feedback.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `packages/web/lib/ai-rating/__tests__/contracts.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { AIRatingScale, AIRatingState, AIRatingViewModel } from "../contracts";

describe("AIRating contracts", () => {
  it("AIRatingState covers idle/loading/success/error/skipped", () => {
    const states: AIRatingState[] = ["idle", "loading", "success", "error", "skipped"];
    // compile-time check: every value is assignable
    states.forEach((s) => expect(typeof s).toBe("string"));
  });

  it("AIRatingScale is exactly 1..5", () => {
    const scale: AIRatingScale[] = [1, 2, 3, 4, 5];
    expect(scale).toHaveLength(5);
  });

  it("AIRatingViewModel requires every field the UI depends on", () => {
    const vm: AIRatingViewModel = {
      sourceType: "co_author_change",
      sourceId: "change-1",
      projectId: "proj-1",
      intent: "rewrite",
      suggestionText: "A revised sentence.",
      action: "accept",
      chapterId: "ch-1",
      genre: null,
      mode: null,
    };
    expect(vm.sourceType).toBe("co_author_change");
    expect(vm.sourceId).toBe("change-1");
  });
});
```

Create `packages/web/lib/ai-rating/__tests__/build-feedback.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { FeedbackAction } from "@/types";
import { buildFeedbackRequest } from "../build-feedback";
import type { AIRatingViewModel } from "../contracts";

const vm: AIRatingViewModel = {
  sourceType: "chat_message",
  sourceId: "msg-42",
  projectId: "proj-1",
  intent: "chat_assistant",
  suggestionText: "Here is a paragraph.",
  action: "accept",
  chapterId: "ch-9",
  genre: null,
  mode: null,
};

describe("buildFeedbackRequest", () => {
  it("builds a FeedbackRequest with source_type and rating", () => {
    const req = buildFeedbackRequest(vm, { rating: 5 });
    expect(req).toMatchObject({
      action: "accept",
      suggestion_id: "msg-42",
      source_type: "chat_message",
      intent: "chat_assistant",
      suggestion_text: "Here is a paragraph.",
      rating: 5,
      project_id: "proj-1",
      chapter_id: "ch-9",
      context: { rating_reason: undefined }, // absent key not present — see below
    });
    // reason undefined → key omitted, not undefined value
    expect(req.context).toEqual({});
  });

  it("includes rating_reason in context when provided", () => {
    const req = buildFeedbackRequest(vm, { rating: 2, reason: "too long" });
    expect(req.context).toEqual({ rating_reason: "too long" });
  });

  it("maps action accept-without-rating when only rating supplied", () => {
    const req = buildFeedbackRequest({ ...vm, action: "modify" }, { rating: 3 });
    expect(req.action).toBe("modify");
  });

  it("rejects rating outside 1..5 at build time (runtime guard)", () => {
    expect(() => buildFeedbackRequest(vm, { rating: 6 as unknown as 1 })).toThrow(
      /rating.*1.*5/i,
    );
  });

  it("does not include source_type when vm provides null (back-compat path)", () => {
    const legacy: AIRatingViewModel = { ...vm, sourceType: null as unknown as AIRatingViewModel["sourceType"] };
    // The contract types sourceType as FeedbackSourceType (non-null). We still
    // guard the builder so an accidental null becomes a missing key, not a
    // backend 422.
    // @ts-expect-error — deliberately invalid for the runtime guard test
    const req = buildFeedbackRequest({ ...vm, sourceType: null }, { rating: 4 });
    expect(req.source_type).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/contracts.test.ts lib/ai-rating/__tests__/build-feedback.test.ts`
Expected: FAIL with `Cannot find module '../contracts'`.

- [ ] **Step 3: Create `packages/web/lib/ai-rating/contracts.ts`**

```typescript
/**
 * CR-AUFG-07-24 — Shared, domain-agnostic AI rating vocabulary.
 *
 * Frontend-only contract (RULE-03): defined BEFORE any component or adapter.
 * The rating primitive is a pure VIEW + a fire-and-forget submit; it never
 * starts AI work and owns no lifecycle beyond its own REST POST.
 *
 * Mirrors the CR-AUFG-07-18 `lib/ai-diff/contracts.ts` shape: contract first,
 * component second, adapters third.
 */

import type { FeedbackAction, FeedbackSourceType } from "@/types";

/** Rating control state machine (matches UI affordances). */
export type AIRatingState =
  | "idle" // rating affordance visible, no decision yet
  | "loading" // POST /memory/feedback in flight
  | "success" // backend confirmed
  | "error" // POST failed — user may retry or skip
  | "skipped"; // user dismissed without rating

/** 1..5 inclusive rating scale. */
export type AIRatingScale = 1 | 2 | 3 | 4 | 5;

/**
 * Immutable, surface-agnostic description of "an AI output the user can rate".
 *
 * - `sourceType` is the closed-vocabulary tag (CR-AUFG-07-24 taxonomy).
 * - `sourceId` is the stable per-surface id (change id, field key, message
 *   id, suggestion id, ...) so ratings are not orphaned.
 * - `action` is the user's accept/reject/modify decision on the SAME output;
 *   rating is a follow-up signal that rides alongside, never replaces, the
 *   action. The caller has already recorded the action event if applicable.
 */
export interface AIRatingViewModel {
  readonly sourceType: FeedbackSourceType;
  readonly sourceId: string;
  readonly projectId: string;
  readonly intent: string;
  readonly suggestionText: string;
  readonly action: FeedbackAction;
  readonly chapterId: string | null;
  readonly genre: string | null;
  readonly mode: string | null;
}

/** Caller-supplied rating payload. */
export interface AIRatingInput {
  readonly rating: AIRatingScale;
  readonly reason?: string;
}
```

- [ ] **Step 4: Create `packages/web/lib/ai-rating/build-feedback.ts`**

```typescript
/**
 * CR-AUFG-07-24 — single source of truth for building a FeedbackRequest from
 * an AIRatingViewModel + AIRatingInput. DRY: every adapter goes through this.
 */

import type { FeedbackRequest } from "@/types";
import type { AIRatingInput, AIRatingScale, AIRatingViewModel } from "./contracts";

/** Validates that n is in the closed 1..5 scale. */
function assertScale(n: number): asserts n is AIRatingScale {
  if (!Number.isInteger(n) || n < 1 || n > 5) {
    throw new Error(`rating must be an integer 1..5 (got ${String(n)})`);
  }
}

/**
 * Build the canonical POST /memory/feedback payload for a rating event.
 *
 * Invariants:
 *   - `source_type` is only set when `vm.sourceType` is non-null.
 *   - `rating_reason` (when provided) lands in `context`, never as a top-level
 *     field — privacy-safe and forward-compatible.
 *   - `context` is always defined (never undefined) so the backend always sees
 *     a JSON object.
 */
export function buildFeedbackRequest(
  vm: AIRatingViewModel,
  input: AIRatingInput,
): FeedbackRequest {
  assertScale(input.rating);

  const context: Record<string, unknown> = {};
  if (input.reason && input.reason.trim().length > 0) {
    context.rating_reason = input.reason.trim();
  }

  return {
    action: vm.action,
    suggestion_id: vm.sourceId,
    source_type: vm.sourceType ?? undefined,
    intent: vm.intent,
    suggestion_text: vm.suggestionText,
    rating: input.rating,
    context,
    project_id: vm.projectId,
    chapter_id: vm.chapterId,
    genre: vm.genre,
    mode: vm.mode,
  };
}
```

- [ ] **Step 5: Create `packages/web/lib/ai-rating/index.ts`**

```typescript
/** CR-AUFG-07-24 — shared AI rating vocabulary. Public surface. */

export type {
  AIRatingInput,
  AIRatingScale,
  AIRatingState,
  AIRatingViewModel,
} from "./contracts";
export { buildFeedbackRequest } from "./build-feedback";
export { coAuthorRatingAdapter } from "./adapters/coauthor";
export { kbFieldSuggestRatingAdapter } from "./adapters/kb-field";
export { kbEnhanceRatingAdapter } from "./adapters/kb-enhance";
export { kbImproveRatingAdapter } from "./adapters/kb-improve";
export { chatRatingAdapter } from "./adapters/chat";
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/contracts.test.ts lib/ai-rating/__tests__/build-feedback.test.ts`
Expected: PASS.

- [ ] **Step 7: Checkpoint (NO commit per plan policy)**

Contract layer done. Adapters can now be built against this contract.

---

## Task 6: Frontend — `AIRating` accessible component (TDD, states machine)

**Files:**
- Create: `packages/web/components/shared/ai-rating/AIRating.tsx`
- Test: `packages/web/components/shared/ai-rating/__tests__/AIRating.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `packages/web/components/shared/ai-rating/__tests__/AIRating.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AIRating } from "../AIRating";
import type { AIRatingViewModel } from "@/lib/ai-rating/contracts";

const vm: AIRatingViewModel = {
  sourceType: "co_author_change",
  sourceId: "change-1",
  projectId: "proj-1",
  intent: "rewrite",
  suggestionText: "A revised sentence.",
  action: "accept",
  chapterId: "ch-1",
  genre: null,
  mode: null,
};

describe("AIRating", () => {
  it("renders a radiogroup with 5 options and the privacy notice", () => {
    render(
      <AIRating
        viewModel={vm}
        state="idle"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    // i18n keys resolve to themselves under setupTests.ts mock
    expect(screen.getByRole("radiogroup")).toBeTruthy();
    expect(screen.getAllByRole("radio")).toHaveLength(5);
    expect(screen.getByText("aiActions.ratingPrivacyNotice")).toBeTruthy();
  });

  it("calls onSubmit with the selected scale value and optional reason", () => {
    const onSubmit = vi.fn();
    render(
      <AIRating
        viewModel={vm}
        state="idle"
        onSubmit={onSubmit}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    fireEvent.click(screen.getAllByRole("radio")[3]); // value 4
    fireEvent.change(screen.getByPlaceholderText("aiActions.ratingReasonPlaceholder"), {
      target: { value: "good tone" },
    });
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));
    expect(onSubmit).toHaveBeenCalledWith({ rating: 4, reason: "good tone" });
  });

  it("calls onSkip when the skip button is clicked", () => {
    const onSkip = vi.fn();
    render(
      <AIRating
        viewModel={vm}
        state="idle"
        onSubmit={vi.fn()}
        onSkip={onSkip}
        onRetry={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "aiActions.skipRating" }));
    expect(onSkip).toHaveBeenCalledOnce();
  });

  it("shows a loading indicator and disables controls while state is loading", () => {
    render(
      <AIRating
        viewModel={vm}
        state="loading"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByText("aiActions.ratingSubmitting")).toBeTruthy();
    expect(screen.getByRole("button", { name: "aiActions.submitRating" })).toBeDisabled();
  });

  it("shows a success confirmation when state is success", () => {
    render(
      <AIRating
        viewModel={vm}
        state="success"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByText("aiActions.ratingSubmitted")).toBeTruthy();
  });

  it("shows an error message and a retry button when state is error", () => {
    const onRetry = vi.fn();
    render(
      <AIRating
        viewModel={vm}
        state="error"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText("aiActions.ratingError")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "aiActions.ratingRetry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders nothing extra when state is skipped (compact dismissal)", () => {
    const { container } = render(
      <AIRating
        viewModel={vm}
        state="skipped"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    // Skipped state shows a small confirmation only — no rating controls
    expect(container.querySelector("input[type='radio']")).toBeNull();
    expect(screen.getByText("aiActions.ratingSkipped")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run components/shared/ai-rating/__tests__/AIRating.test.tsx`
Expected: FAIL with `Cannot find module '../AIRating'`.

- [ ] **Step 3: Implement `AIRating.tsx`**

Create `packages/web/components/shared/ai-rating/AIRating.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import type {
  AIRatingInput,
  AIRatingScale,
  AIRatingState,
  AIRatingViewModel,
} from "@/lib/ai-rating/contracts";

interface AIRatingProps {
  readonly viewModel: AIRatingViewModel;
  readonly state: AIRatingState;
  readonly onSubmit: (input: AIRatingInput) => void;
  readonly onSkip: () => void;
  readonly onRetry: () => void;
}

const SCALE: readonly AIRatingScale[] = [1, 2, 3, 4, 5];

/**
 * Shared, accessible AI rating control (CR-AUFG-07-24).
 *
 * State machine: idle → loading → success | error → (retry → loading) | skipped.
 *
 * Accessibility:
 *   - The scale is a `radiogroup` of 5 `radio` inputs (WAI-ARIA Authoring
 *     Practices 1.2 rating pattern in its radio form — keyboard + screen-reader
 *     friendly, never color-alone).
 *   - The privacy notice is a `polite` live region sibling so screen readers
 *     announce it after the rating prompt.
 *
 * RULE-16: every visible string is an `studio.aiActions.*` i18n key.
 */
export function AIRating({ viewModel, state, onSubmit, onSkip, onRetry }: AIRatingProps) {
  const t = useTranslations("studio");
  const [value, setValue] = useState<AIRatingScale | null>(null);
  const [reason, setReason] = useState<string>("");

  if (state === "success") {
    return (
      <p className="text-xs text-muted-foreground" role="status">
        {t("aiActions.ratingSubmitted")}
      </p>
    );
  }

  if (state === "skipped") {
    return (
      <p className="text-xs text-muted-foreground">
        {t("aiActions.ratingSkipped")}
      </p>
    );
  }

  if (state === "error") {
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="text-red-600 dark:text-red-400" role="alert">
          {t("aiActions.ratingError")}
        </span>
        <button
          type="button"
          onClick={onRetry}
          className="underline hover:no-underline text-primary"
        >
          {t("aiActions.ratingRetry")}
        </button>
        <button
          type="button"
          onClick={onSkip}
          className="ml-auto text-muted-foreground hover:text-foreground"
        >
          {t("aiActions.skipRating")}
        </button>
      </div>
    );
  }

  const disabled = state === "loading";

  return (
    <section className="mt-2 rounded-md border border-border/60 p-2 text-xs" aria-label={t("aiActions.rating")}>
      <div className="flex items-center justify-between gap-2">
        <fieldset className="min-w-0">
          <legend className="sr-only">{t("aiActions.rating")}</legend>
          <div
            role="radiogroup"
            aria-label={t("aiActions.rating")}
            className="flex items-center gap-1"
          >
            {SCALE.map((n) => (
              <label key={n} className="cursor-pointer">
                <input
                  type="radio"
                  name={`rating-${viewModel.sourceType}-${viewModel.sourceId}`}
                  value={n}
                  checked={value === n}
                  disabled={disabled}
                  onChange={() => setValue(n)}
                  className="sr-only"
                />
                <span
                  aria-hidden="true"
                  className={`inline-flex h-5 w-5 items-center justify-center rounded border transition-colors ${
                    value === n
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground hover:border-primary/50"
                  }`}
                >
                  {n}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <span className="text-muted-foreground">
          {state === "loading" ? t("aiActions.ratingSubmitting") : ""}
        </span>
      </div>

      <input
        type="text"
        value={reason}
        disabled={disabled}
        onChange={(e) => setReason(e.target.value)}
        placeholder={t("aiActions.ratingReasonPlaceholder")}
        className="mt-2 w-full rounded border border-border bg-input-background px-2 py-1 text-xs"
        aria-label={t("aiActions.ratingReason")}
      />

      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-muted-foreground" aria-live="polite">
          {t("aiActions.ratingPrivacyNotice")}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSkip}
            disabled={disabled}
            className="text-muted-foreground hover:text-foreground"
          >
            {t("aiActions.skipRating")}
          </button>
          <button
            type="button"
            onClick={() => value && onSubmit({ rating: value, reason: reason || undefined })}
            disabled={disabled || value === null}
            className="rounded bg-primary px-2 py-1 text-primary-foreground disabled:opacity-50"
          >
            {t("aiActions.submitRating")}
          </button>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd packages/web && pnpm exec vitest run components/shared/ai-rating/__tests__/AIRating.test.tsx`
Expected: PASS (7 tests).

- [ ] **Step 5: Checkpoint (NO commit per plan policy)**

Reusable component done. Adoption tasks can wire it in.

---

## Task 7: Frontend — `useAIRating` hook (state machine wrapping `useRecordFeedback`)

**Files:**
- Create: `packages/web/lib/hooks/useAIRating.ts`
- Test: `packages/web/lib/hooks/__tests__/useAIRating.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `packages/web/lib/hooks/__tests__/useAIRating.test.tsx`:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import http from "msw/utility/http";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { setupServer } from "msw/node";
import { useAIRating } from "@/lib/hooks/useAIRating";
import type { AIRatingViewModel } from "@/lib/ai-rating/contracts";

const vm: AIRatingViewModel = {
  sourceType: "kb_enhance_field",
  sourceId: "field-role",
  projectId: "proj-1",
  intent: "kb_enhance",
  suggestionText: "Wise mentor",
  action: "accept",
  chapterId: null,
  genre: null,
  mode: null,
};

const server = setupServer(
  http.post("*/api/v1/memory/feedback", async () =>
    HttpResponse.json({ id: "evt-1", action: "accept", created_at: "2026-06-22T00:00:00Z" }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useAIRating", () => {
  it("starts in idle state and exposes submit + skip", () => {
    const { result } = renderHook(() => useAIRating(vm), { wrapper });
    expect(result.current.state).toBe("idle");
    expect(typeof result.current.submit).toBe("function");
    expect(typeof result.current.skip).toBe("function");
    expect(typeof result.current.reset).toBe("function");
  });

  it("transitions idle → loading → success on a successful POST", async () => {
    const { result } = renderHook(() => useAIRating(vm), { wrapper });
    act(() => {
      result.current.submit({ rating: 5 });
    });
    expect(result.current.state).toBe("loading");
    await waitFor(() => expect(result.current.state).toBe("success"));
  });

  it("skip() transitions to skipped without firing the POST", () => {
    const { result } = renderHook(() => useAIRating(vm), { wrapper });
    act(() => result.current.skip());
    expect(result.current.state).toBe("skipped");
  });

  it("reset() returns to idle from any terminal state", () => {
    const { result } = renderHook(() => useAIRating(vm), { wrapper });
    act(() => result.current.skip());
    act(() => result.current.reset());
    expect(result.current.state).toBe("idle");
  });

  it("transitions to error on a failed POST (non-blocking)", async () => {
    server.use(
      http.post("*/api/v1/memory/feedback", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    const { result } = renderHook(() => useAIRating(vm), { wrapper });
    act(() => result.current.submit({ rating: 3 }));
    await waitFor(() => expect(result.current.state).toBe("error"));
  });
});
```

> Note: `msw/utility/http` import path mirrors what existing `lib/api/__tests__/memory.test.ts` uses. Verify the exact import path by checking that file before running; if different, adjust both this test and the import. The HttpResponse import is the standard msw v2 export.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run lib/hooks/__tests__/useAIRating.test.tsx`
Expected: FAIL with `Cannot find module '@/lib/hooks/useAIRating'`.

- [ ] **Step 3: Implement `useAIRating`**

Create `packages/web/lib/hooks/useAIRating.ts`:

```typescript
"use client";

import { useCallback, useState } from "react";
import { buildFeedbackRequest } from "@/lib/ai-rating/build-feedback";
import type { AIRatingInput, AIRatingState, AIRatingViewModel } from "@/lib/ai-rating/contracts";
import { useRecordFeedback } from "@/lib/hooks/useMemory";

/**
 * CR-AUFG-07-24 — UI-level state machine for rating submission.
 *
 * Wraps the existing `useRecordFeedback` TanStack mutation with the
 * idle/loading/success/error/skipped surface the `AIRating` component needs.
 *
 * The hook is **non-blocking**: rating failures never throw to the caller.
 * Per spec, a failed rating must NOT remove or alter the AI output. The host
 * component decides whether to render the error/retry affordance.
 *
 * @param vm immutable view model describing WHAT is being rated.
 */
export function useAIRating(vm: AIRatingViewModel) {
  const [state, setState] = useState<AIRatingState>("idle");
  const record = useRecordFeedback(vm.projectId);

  const submit = useCallback(
    (input: AIRatingInput) => {
      setState("loading");
      const payload = buildFeedbackRequest(vm, input);
      // onError is intentionally non-blocking per spec; we surface it as the
      // 'error' state so the UI can offer retry/skip without affecting the
      // original AI output.
      record.mutate(payload, {
        onSuccess: () => setState("success"),
        onError: () => setState("error"),
      });
    },
    [record, vm],
  );

  const skip = useCallback(() => setState("skipped"), []);
  const reset = useCallback(() => setState("idle"), []);

  return { state, submit, skip, reset } as const;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd packages/web && pnpm exec vitest run lib/hooks/__tests__/useAIRating.test.tsx`
Expected: PASS (5 tests). If the msw import path is wrong, fix it from `lib/api/__tests__/memory.test.ts` and re-run.

- [ ] **Step 5: Checkpoint (NO commit per plan policy)**

Rating infrastructure complete: contract → builder → hook → component. Adapters next.

---

## Task 8: Co-Author adoption — `ChangeReview.tsx` + adapter

**Files:**
- Create: `packages/web/lib/ai-rating/adapters/coauthor.ts`
- Test: `packages/web/lib/ai-rating/__tests__/adapters/coauthor.test.ts`
- Modify: `packages/web/components/studio/editor/ChangeReview.tsx`
- Test: `packages/web/components/studio/editor/__tests__/ChangeReview.rating.test.tsx` (NEW)

> **Design note:** Co-Author already posts accept/reject feedback via the legacy
> `/writing/chapters/{id}/co-author/feedback` endpoint in `coauthor-apply.ts`.
> CR-AUFG-07-24 deliberately routes the NEW rating signal through the canonical
> `POST /memory/feedback` with `source_type: "co_author_change"` so all ratings
> join the same learning path (RULE-20). The legacy accept/reject endpoint is
> untouched — rating is a separate, follow-up event.

- [ ] **Step 1: Write the failing adapter test**

Create `packages/web/lib/ai-rating/__tests__/adapters/coauthor.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { ChangeDetail } from "@/lib/api/coauthor";
import { coAuthorRatingAdapter } from "@/lib/ai-rating/adapters/coauthor";

describe("coAuthorRatingAdapter", () => {
  const change: ChangeDetail = {
    id: "change-7",
    index: 6,
    original_text: "He ran fast.",
    revised_text: "He sprinted.",
    change_type: "rephrase",
  } as unknown as ChangeDetail;

  it("builds an AIRatingViewModel tagged co_author_change", () => {
    const vm = coAuthorRatingAdapter({
      change,
      projectId: "proj-1",
      chapterId: "ch-1",
      action: "accept",
    });
    expect(vm.sourceType).toBe("co_author_change");
    expect(vm.sourceId).toBe("change-7");
    expect(vm.intent).toBe("co_author");
    expect(vm.suggestionText).toBe("He sprinted.");
    expect(vm.action).toBe("accept");
    expect(vm.chapterId).toBe("ch-1");
  });

  it("passes the accept action through unchanged", () => {
    const vm = coAuthorRatingAdapter({
      change,
      projectId: "proj-1",
      chapterId: "ch-1",
      action: "reject",
    });
    expect(vm.action).toBe("reject");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/coauthor.test.ts`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement the adapter**

Create `packages/web/lib/ai-rating/adapters/coauthor.ts`:

```typescript
/** CR-AUFG-07-24 — Co-Author change → AIRatingViewModel. */

import type { ChangeDetail } from "@/lib/api/coauthor";
import type { FeedbackAction } from "@/types";
import type { AIRatingViewModel } from "../contracts";

export interface CoAuthorRatingAdapterInput {
  readonly change: ChangeDetail;
  readonly projectId: string;
  readonly chapterId: string | null;
  /** The decision the user already made on this change. */
  readonly action: FeedbackAction;
}

export function coAuthorRatingAdapter(input: CoAuthorRatingAdapterInput): AIRatingViewModel {
  return {
    sourceType: "co_author_change",
    sourceId: input.change.id,
    projectId: input.projectId,
    intent: "co_author",
    suggestionText: input.change.revised_text,
    action: input.action,
    chapterId: input.chapterId,
    genre: null,
    mode: null,
  };
}
```

- [ ] **Step 4: Run the adapter test to verify it passes**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/coauthor.test.ts`
Expected: PASS.

- [ ] **Step 5: Write the failing adoption test**

Create `packages/web/components/studio/editor/__tests__/ChangeReview.rating.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import http from "msw/utility/http";
import { setupServer } from "msw/node";
import { ChangeReview } from "@/components/studio/editor/ChangeReview";
import type { ChangeDetail } from "@/lib/api/coauthor";

const change: ChangeDetail = {
  id: "change-7",
  index: 6,
  original_text: "He ran fast.",
  revised_text: "He sprinted.",
  change_type: "rephrase",
} as unknown as ChangeDetail;

const server = setupServer(
  http.post("*/api/v1/memory/feedback", async () =>
    HttpResponse.json({ id: "evt-1", action: "accept", created_at: "2026-06-22T00:00:00Z" }),
  ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ChangeReview rating (CR-AUFG-07-24)", () => {
  it("renders AIRating after the user toggles accept", () => {
    renderWithProviders(
      <ChangeReview
        change={change}
        isAccepted
        onToggle={vi.fn()}
        projectId="proj-1"
        chapterId="ch-1"
      />,
    );
    // After accept, the rating radiogroup appears
    expect(screen.getByRole("radiogroup")).toBeTruthy();
  });

  it("posts to /memory/feedback with source_type=co_author_change on submit", async () => {
    let capturedBody: unknown = undefined;
    server.use(
      http.post("*/api/v1/memory/feedback", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ id: "evt-1", action: "accept", created_at: "x" });
      }),
    );

    renderWithProviders(
      <ChangeReview
        change={change}
        isAccepted
        onToggle={vi.fn()}
        projectId="proj-1"
        chapterId="ch-1"
      />,
    );

    fireEvent.click(screen.getAllByRole("radio")[4]); // value 5
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));

    await new Promise((r) => setTimeout(r, 0));
    expect(capturedBody).toMatchObject({
      source_type: "co_author_change",
      suggestion_id: "change-7",
      rating: 5,
      project_id: "proj-1",
    });
  });
});
```

- [ ] **Step 6: Run the adoption test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run components/studio/editor/__tests__/ChangeReview.rating.test.tsx`
Expected: FAIL — `ChangeReview` doesn't render `AIRating` yet, and doesn't accept `projectId`/`chapterId` props.

- [ ] **Step 7: Implement the adoption — modify `ChangeReview.tsx`**

Update the props interface and component. Replace the current `ChangeReviewProps` (lines 14–19) and the function body to add rating support. The full new file is:

```tsx
"use client";

import { Check, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { AIRating } from "@/components/shared/ai-rating/AIRating";
import { AIDiffView } from "@/components/shared/ai-diff/AIDiffView";
import { coAuthorRatingAdapter } from "@/lib/ai-rating/adapters/coauthor";
import { useAIRating } from "@/lib/hooks/useAIRating";
import { coAuthorChangeAdapter } from "@/lib/ai-diff/adapters/coauthor";
import type { AIDiffState } from "@/lib/ai-diff/contracts";
import type { ChangeDetail } from "@/lib/api/coauthor";

export interface ChangeReviewProps {
  readonly change: ChangeDetail;
  readonly isAccepted: boolean;
  readonly onToggle?: (changeId: string) => void;
  readonly readOnly?: boolean;
  /** Project id for the rating feedback POST. Required when rating is enabled. */
  readonly projectId?: string;
  /** Chapter id for the rating feedback POST. Optional. */
  readonly chapterId?: string | null;
}

export function ChangeReview({
  change,
  isAccepted,
  onToggle,
  readOnly = false,
  projectId,
  chapterId = null,
}: ChangeReviewProps) {
  const t = useTranslations("studio");
  const viewModel = coAuthorChangeAdapter(change);
  const diffState: AIDiffState = isAccepted ? "accepted" : "suggested";

  const ratingVm =
    projectId !== undefined
      ? coAuthorRatingAdapter({
          change,
          projectId,
          chapterId,
          action: isAccepted ? "accept" : "reject",
        })
      : null;
  const rating = useAIRating(ratingVm ?? SKIP_VM);

  return (
    <div
      className={`rounded-lg border transition-all ${
        isAccepted ? "border-green-500/50 bg-green-500/5" : "border-border hover:border-primary/30"
      }`}
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/50">
        <span className="text-xs text-muted-foreground">#{change.index + 1}</span>
        {!readOnly && onToggle && (
          <button
            type="button"
            onClick={() => onToggle(change.id)}
            aria-label={isAccepted ? t("aiDiff.rejectChange") : t("aiDiff.acceptChange")}
            className={`flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md transition-all ${
              isAccepted
                ? "bg-green-500/10 text-green-600 dark:text-green-400 hover:bg-green-500/20"
                : "bg-muted text-muted-foreground hover:bg-accent"
            }`}
          >
            {isAccepted ? (
              <>
                <X className="w-3 h-3" />
                <span>{t("aiActions.reject")}</span>
              </>
            ) : (
              <>
                <Check className="w-3 h-3" />
                <span>{t("aiActions.accept")}</span>
              </>
            )}
          </button>
        )}
      </div>

      <div className="px-3 py-2.5">
        <AIDiffView viewModel={viewModel} state={diffState} />
        {ratingVm && (isAccepted || !readOnly) && (
          <AIRating
            viewModel={ratingVm}
            state={rating.state}
            onSubmit={rating.submit}
            onSkip={rating.skip}
            onRetry={rating.reset}
          />
        )}
      </div>
    </div>
  );
}

// A no-op view model so useAIRating's hook order stays stable when rating is
// disabled (rules-of-hooks compliance). It is never rendered because the host
// gates rendering on ratingVm !== null.
const SKIP_VM = {
  sourceType: "co_author_change",
  sourceId: "__disabled__",
  projectId: "__disabled__",
  intent: "co_author",
  suggestionText: "",
  action: "accept",
  chapterId: null,
  genre: null,
  mode: null,
} as const;
```

Then update callers of `ChangeReview` to pass `projectId`/`chapterId` from their host context. Search:

Run: `cd packages/web && rg "ChangeReview" --type tsx --type ts -l`
For each non-test caller, add the props from the surrounding context (the Co-Author review container already has novelId/chapterId). If a caller is read-only (e.g. a history view), leave `projectId` undefined to keep rating disabled.

- [ ] **Step 8: Run the adoption test + existing ChangeReview tests to verify they pass**

Run: `cd packages/web && pnpm exec vitest run components/studio/editor/__tests__/ChangeReview`
Expected: PASS — both pre-existing CR-AUFG-07-18 tests and the new rating test.

- [ ] **Step 9: Checkpoint (NO commit per plan policy)**

Co-Author surface done. KB surfaces next.

---

## Task 9: KB Enhance adoption — `EnhanceReviewCard.tsx` + adapter

**Files:**
- Create: `packages/web/lib/ai-rating/adapters/kb-enhance.ts`
- Test: `packages/web/lib/ai-rating/__tests__/adapters/kb-enhance.test.ts`
- Modify: `packages/web/components/studio/kb/_components/EnhanceReviewCard.tsx`
- Test: `packages/web/components/studio/kb/__tests__/KBEnhanceReview.rating.test.tsx` (NEW)

- [ ] **Step 1: Write the failing adapter test**

Create `packages/web/lib/ai-rating/__tests__/adapters/kb-enhance.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";
import { kbEnhanceRatingAdapter } from "@/lib/ai-rating/adapters/kb-enhance";

const enhancement: KBEnhancementResult = {
  field_key: "role",
  original_value: "Mentor",
  suggested_value: "Wise mentor",
  reasoning: "more evocative",
} as unknown as KBEnhancementResult;

describe("kbEnhanceRatingAdapter", () => {
  it("builds an AIRatingViewModel tagged kb_enhance_field", () => {
    const vm = kbEnhanceRatingAdapter({
      enhancement,
      projectId: "proj-1",
      fieldLabel: "Role",
      action: "accept",
    });
    expect(vm.sourceType).toBe("kb_enhance_field");
    expect(vm.sourceId).toBe("role");
    expect(vm.intent).toBe("kb_enhance");
    expect(vm.suggestionText).toBe("Wise mentor");
    expect(vm.action).toBe("accept");
    expect(vm.chapterId).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/kb-enhance.test.ts`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement the adapter**

Create `packages/web/lib/ai-rating/adapters/kb-enhance.ts`:

```typescript
/** CR-AUFG-07-24 — KB enhance field → AIRatingViewModel. */

import type { KBEnhancementResult } from "@/lib/api/kb-sessions";
import type { FeedbackAction } from "@/types";
import type { AIRatingViewModel } from "../contracts";

export interface KBEnhanceRatingAdapterInput {
  readonly enhancement: KBEnhancementResult;
  readonly projectId: string;
  readonly fieldLabel: string;
  readonly action: FeedbackAction;
}

export function kbEnhanceRatingAdapter(input: KBEnhanceRatingAdapterInput): AIRatingViewModel {
  return {
    sourceType: "kb_enhance_field",
    sourceId: input.enhancement.field_key,
    projectId: input.projectId,
    intent: "kb_enhance",
    suggestionText: input.enhancement.suggested_value,
    action: input.action,
    chapterId: null,
    genre: null,
    mode: null,
  };
}
```

- [ ] **Step 4: Run the adapter test to verify it passes**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/kb-enhance.test.ts`
Expected: PASS.

- [ ] **Step 5: Write the failing adoption test**

Create `packages/web/components/studio/kb/__tests__/KBEnhanceReview.rating.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import http from "msw/utility/http";
import { setupServer } from "msw/node";
import { EnhanceReviewCard } from "@/components/studio/kb/_components/EnhanceReviewCard";
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";

const enhancement: KBEnhancementResult = {
  field_key: "role",
  original_value: "Mentor",
  suggested_value: "Wise mentor",
  reasoning: "more evocative",
} as unknown as KBEnhancementResult;

const server = setupServer(
  http.post("*/api/v1/memory/feedback", async () =>
    HttpResponse.json({ id: "evt-1", action: "accept", created_at: "x" }),
  ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("EnhanceReviewCard rating (CR-AUFG-07-24)", () => {
  it("renders AIRating when projectId is supplied", () => {
    renderWithProviders(
      <EnhanceReviewCard
        enhancement={enhancement}
        isSelected
        onToggle={vi.fn()}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        fieldLabel="Role"
        projectId="proj-1"
        t={(k: string) => k}
      />,
    );
    expect(screen.getByRole("radiogroup")).toBeTruthy();
  });

  it("posts to /memory/feedback with source_type=kb_enhance_field on submit", async () => {
    let capturedBody: unknown = undefined;
    server.use(
      http.post("*/api/v1/memory/feedback", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ id: "evt-1", action: "accept", created_at: "x" });
      }),
    );
    renderWithProviders(
      <EnhanceReviewCard
        enhancement={enhancement}
        isSelected
        onToggle={vi.fn()}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        fieldLabel="Role"
        projectId="proj-1"
        t={(k: string) => k}
      />,
    );
    fireEvent.click(screen.getAllByRole("radio")[3]);
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));
    await new Promise((r) => setTimeout(r, 0));
    expect(capturedBody).toMatchObject({
      source_type: "kb_enhance_field",
      suggestion_id: "role",
      rating: 4,
      project_id: "proj-1",
    });
  });
});
```

- [ ] **Step 6: Run the adoption test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run components/studio/kb/__tests__/KBEnhanceReview.rating.test.tsx`
Expected: FAIL — `EnhanceReviewCard` doesn't render `AIRating` and doesn't accept `projectId`.

- [ ] **Step 7: Modify `EnhanceReviewCard.tsx`**

Add `projectId?: string` to the props and render `AIRating` after the accept/reject footer when `projectId` is defined. Concretely, replace the props interface and footer block:

Update the `EnhanceReviewCardProps` interface to add `readonly projectId?: string;` (after `fieldLabel: string;`).

Import at top of file:

```tsx
import { AIRating } from "@/components/shared/ai-rating/AIRating";
import { kbEnhanceRatingAdapter } from "@/lib/ai-rating/adapters/kb-enhance";
import { useAIRating } from "@/lib/hooks/useAIRating";
```

Inside the component (before the `return`), compute the rating view model conditionally:

```tsx
const ratingVm =
  projectId !== undefined
    ? kbEnhanceRatingAdapter({
        enhancement,
        projectId,
        fieldLabel,
        action: isSelected ? "accept" : "reject",
      })
    : null;
```

After the existing footer `<div className="flex justify-end gap-2 p-3 ...">...</div>`, render:

```tsx
      {ratingVm && (
        <AIRating
          viewModel={ratingVm}
          state={rating.state}
          onSubmit={rating.submit}
          onSkip={rating.skip}
          onRetry={rating.reset}
        />
      )}
```

Also call the hook at the top of the component (rules-of-hooks — unconditional):

```tsx
const rating = useAIRating(
  ratingVm ?? {
    sourceType: "kb_enhance_field",
    sourceId: "__disabled__",
    projectId: "__disabled__",
    intent: "kb_enhance",
    suggestionText: "",
    action: "accept",
    chapterId: null,
    genre: null,
    mode: null,
  },
);
```

> Note: declare `ratingVm` before `rating` so the hook receives the right value. Re-order if needed.

Update the single caller of `EnhanceReviewCard` (search `rg "EnhanceReviewCard" --type tsx -l` and follow the existing `KBEnhanceReview.tsx` host to pass `projectId={novelId}`).

- [ ] **Step 8: Run all KB Enhance tests**

Run: `cd packages/web && pnpm exec vitest run components/studio/kb/__tests__/KBEnhanceReview`
Expected: PASS (existing + new rating tests).

- [ ] **Step 9: Checkpoint (NO commit per plan policy)**

KB Enhance surface done.

---

## Task 10: KB Improve adoption — `ImproveSuggestionCard.tsx` + adapter

**Files:**
- Create: `packages/web/lib/ai-rating/adapters/kb-improve.ts`
- Test: `packages/web/lib/ai-rating/__tests__/adapters/kb-improve.test.ts`
- Modify: `packages/web/components/studio/kb/_components/ImproveSuggestionCard.tsx`
- Test: `packages/web/components/studio/kb/__tests__/KBImprovePanel.rating.test.tsx` (NEW or extend existing)

- [ ] **Step 1: Write the failing adapter test**

Create `packages/web/lib/ai-rating/__tests__/adapters/kb-improve.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { ImproveSuggestion } from "@/lib/api/kb-improve";
import { kbImproveRatingAdapter } from "@/lib/ai-rating/adapters/kb-improve";

const suggestion: ImproveSuggestion = {
  suggestion_id: 12,
  type: "plot_hole",
  description: "Add a motivation for the antagonist.",
  proposed_content: "She wants revenge.",
  confidence: 0.82,
  reasoning: "current text lacks stakes",
  related_entity_name: null,
} as unknown as ImproveSuggestion;

describe("kbImproveRatingAdapter", () => {
  it("builds an AIRatingViewModel tagged kb_improve_suggestion", () => {
    const vm = kbImproveRatingAdapter({
      suggestion,
      projectId: "proj-1",
      action: "accept",
    });
    expect(vm.sourceType).toBe("kb_improve_suggestion");
    expect(vm.sourceId).toBe("12");
    expect(vm.intent).toBe("kb_improve");
    expect(vm.suggestionText).toBe("Add a motivation for the antagonist.");
    expect(vm.action).toBe("accept");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/kb-improve.test.ts`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement the adapter**

Create `packages/web/lib/ai-rating/adapters/kb-improve.ts`:

```typescript
/** CR-AUFG-07-24 — KB improve suggestion → AIRatingViewModel. */

import type { ImproveSuggestion } from "@/lib/api/kb-improve";
import type { FeedbackAction } from "@/types";
import type { AIRatingViewModel } from "../contracts";

export interface KBImproveRatingAdapterInput {
  readonly suggestion: ImproveSuggestion;
  readonly projectId: string;
  readonly action: FeedbackAction;
}

export function kbImproveRatingAdapter(input: KBImproveRatingAdapterInput): AIRatingViewModel {
  return {
    sourceType: "kb_improve_suggestion",
    sourceId: String(input.suggestion.suggestion_id),
    projectId: input.projectId,
    intent: "kb_improve",
    suggestionText: input.suggestion.description,
    action: input.action,
    chapterId: null,
    genre: null,
    mode: null,
  };
}
```

- [ ] **Step 4: Run the adapter test to verify it passes**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/kb-improve.test.ts`
Expected: PASS.

- [ ] **Step 5: Write the failing adoption test**

Create `packages/web/components/studio/kb/__tests__/KBImprovePanel.rating.test.tsx` (mirror the EnhanceReview rating test, swapping in `ImproveSuggestionCard` and `kbImproveRatingAdapter`). Assert the POST body contains `source_type: "kb_improve_suggestion"`, `suggestion_id: "12"`, `rating: 5`, `project_id: "proj-1"`.

Use the existing `KBImprovePanel.test.tsx` as the harness template (read it first via Read tool to copy the render setup).

- [ ] **Step 6: Run the test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run components/studio/kb/__tests__/KBImprovePanel.rating.test.tsx`
Expected: FAIL.

- [ ] **Step 7: Modify `ImproveSuggestionCard.tsx`**

Same pattern as EnhanceReviewCard:

1. Add `readonly projectId?: string;` to `ImproveSuggestionCardProps`.
2. Add imports: `AIRating`, `kbImproveRatingAdapter`, `useAIRating`.
3. Compute `ratingVm` (action = `isSelected ? "accept" : "reject"`).
4. Call `useAIRating` unconditionally (disabled fallback VM).
5. Render `<AIRating ... />` after the accept/reject footer when `ratingVm` is set.
6. Update the caller (`KBImprovePanel.tsx`) to pass `projectId={novelId}`.

- [ ] **Step 8: Run all KB Improve tests**

Run: `cd packages/web && pnpm exec vitest run components/studio/kb/__tests__/KBImprovePanel`
Expected: PASS.

- [ ] **Step 9: Checkpoint (NO commit per plan policy)**

KB Improve surface done.

---

## Task 11: KB Field Suggest adoption — `FieldSuggestionReview.tsx` + adapter

**Files:**
- Create: `packages/web/lib/ai-rating/adapters/kb-field.ts`
- Test: `packages/web/lib/ai-rating/__tests__/adapters/kb-field.test.ts`
- Modify: `packages/web/components/studio/kb/_components/FieldSuggestionReview.tsx`
- Test: `packages/web/components/studio/kb/__tests__/FieldSuggestionReview.rating.test.tsx` (NEW)

- [ ] **Step 1: Inspect the host component to learn its prop shape**

Run: `cd packages/web && cat components/studio/kb/_components/FieldSuggestionReview.tsx`

Identify the suggestion type (likely from `@/lib/api/kb-sessions` or a session-suggest type) and its stable id (the `field_key` or session-issued suggestion id).

- [ ] **Step 2: Write the failing adapter test**

Create `packages/web/lib/ai-rating/__tests__/adapters/kb-field.test.ts` with the same shape as the others. The view model asserts:
- `sourceType: "kb_field_suggest"`
- `sourceId`: the field key or session suggestion id from the host
- `intent: "kb_field_suggest"`
- `suggestionText`: the suggested field value

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/kb-field.test.ts`
Expected: FAIL.

- [ ] **Step 4: Implement the adapter**

Create `packages/web/lib/ai-rating/adapters/kb-field.ts` with `kbFieldSuggestRatingAdapter(input)` returning the `kb_field_suggest` view model.

- [ ] **Step 5: Run the adapter test to verify it passes**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/kb-field.test.ts`
Expected: PASS.

- [ ] **Step 6: Write the failing adoption test**

Create `packages/web/components/studio/kb/__tests__/FieldSuggestionReview.rating.test.tsx` following the same harness pattern. Assert the POST body uses `source_type: "kb_field_suggest"`.

- [ ] **Step 7: Run the test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run components/studio/kb/__tests__/FieldSuggestionReview.rating.test.tsx`
Expected: FAIL.

- [ ] **Step 8: Modify `FieldSuggestionReview.tsx`**

Apply the same adoption recipe (add `projectId?` prop, add `AIRating`, gate render on `ratingVm`).

- [ ] **Step 9: Run all field-suggest tests**

Run: `cd packages/web && pnpm exec vitest run components/studio/kb/__tests__/FieldSuggestionReview components/studio/kb/__tests__/KBAssistedCreation`
Expected: PASS.

- [ ] **Step 10: Checkpoint (NO commit per plan policy)**

All three KB surfaces done.

---

## Task 12: Chat adoption — `ChatMessage.tsx` + adapter

**Files:**
- Create: `packages/web/lib/ai-rating/adapters/chat.ts`
- Test: `packages/web/lib/ai-rating/__tests__/adapters/chat.test.ts`
- Modify: `packages/web/components/studio/editor/ChatMessage.tsx`
- Test: `packages/web/components/studio/editor/__tests__/ChatMessage.rating.test.tsx` (NEW)

> **Scope guardrail:** Per spec "Rating every token/chunk during streaming" is **out of scope**. The Chat adapter rates only completed assistant messages with a `prose` block AND a stable `message.id`. While `isStreaming` is true for the host message, the rating control must not render.

- [ ] **Step 1: Write the failing adapter test**

Create `packages/web/lib/ai-rating/__tests__/adapters/chat.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { chatRatingAdapter } from "@/lib/ai-rating/adapters/chat";

describe("chatRatingAdapter", () => {
  it("builds an AIRatingViewModel tagged chat_message from a prose block", () => {
    const vm = chatRatingAdapter({
      messageId: "msg-42",
      prose: "Here is a paragraph the assistant produced.",
      projectId: "proj-1",
      action: "accept",
    });
    expect(vm.sourceType).toBe("chat_message");
    expect(vm.sourceId).toBe("msg-42");
    expect(vm.intent).toBe("chat_assistant");
    expect(vm.suggestionText).toBe("Here is a paragraph the assistant produced.");
    expect(vm.action).toBe("accept");
    expect(vm.chapterId).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/chat.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement the adapter**

Create `packages/web/lib/ai-rating/adapters/chat.ts`:

```typescript
/** CR-AUFG-07-24 — Chat assistant message → AIRatingViewModel. */

import type { FeedbackAction } from "@/types";
import type { AIRatingViewModel } from "../contracts";

export interface ChatRatingAdapterInput {
  readonly messageId: string;
  readonly prose: string;
  readonly projectId: string;
  readonly action: FeedbackAction;
}

export function chatRatingAdapter(input: ChatRatingAdapterInput): AIRatingViewModel {
  return {
    sourceType: "chat_message",
    sourceId: input.messageId,
    projectId: input.projectId,
    intent: "chat_assistant",
    suggestionText: input.prose,
    action: input.action,
    chapterId: null,
    genre: null,
    mode: null,
  };
}
```

- [ ] **Step 4: Run the adapter test to verify it passes**

Run: `cd packages/web && pnpm exec vitest run lib/ai-rating/__tests__/adapters/chat.test.ts`
Expected: PASS.

- [ ] **Step 5: Write the failing adoption test**

Create `packages/web/components/studio/editor/__tests__/ChatMessage.rating.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import http from "msw/utility/http";
import { setupServer } from "msw/node";
import { ChatMessage, type Message } from "@/components/studio/editor/ChatMessage";

const message: Message = {
  id: "msg-42",
  role: "assistant",
  content: "Here you go.",
  prose: "A polished paragraph.",
};

const server = setupServer(
  http.post("*/api/v1/memory/feedback", async () =>
    HttpResponse.json({ id: "evt-1", action: "accept", created_at: "x" }),
  ),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ChatMessage rating (CR-AUFG-07-24)", () => {
  it("renders AIRating under the prose block when projectId is set", () => {
    renderWithProviders(
      <ChatMessage
        message={message}
        isAdded={false}
        onAddToDraft={vi.fn()}
        aiDraftBadge="x"
        addToDraftLabel="x"
        addedToDraftLabel="x"
        projectId="proj-1"
      />,
    );
    expect(screen.getByRole("radiogroup")).toBeTruthy();
  });

  it("omits AIRating when projectId is absent (legacy callers)", () => {
    renderWithProviders(
      <ChatMessage
        message={message}
        isAdded={false}
        onAddToDraft={vi.fn()}
        aiDraftBadge="x"
        addToDraftLabel="x"
        addedToDraftLabel="x"
      />,
    );
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });

  it("posts with source_type=chat_message on submit", async () => {
    let capturedBody: unknown = undefined;
    server.use(
      http.post("*/api/v1/memory/feedback", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ id: "evt-1", action: "accept", created_at: "x" });
      }),
    );
    renderWithProviders(
      <ChatMessage
        message={message}
        isAdded={false}
        onAddToDraft={vi.fn()}
        aiDraftBadge="x"
        addToDraftLabel="x"
        addedToDraftLabel="x"
        projectId="proj-1"
      />,
    );
    fireEvent.click(screen.getAllByRole("radio")[4]);
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));
    await new Promise((r) => setTimeout(r, 0));
    expect(capturedBody).toMatchObject({
      source_type: "chat_message",
      suggestion_id: "msg-42",
      rating: 5,
      project_id: "proj-1",
    });
  });
});
```

- [ ] **Step 6: Run the adoption test to verify it fails**

Run: `cd packages/web && pnpm exec vitest run components/studio/editor/__tests__/ChatMessage.rating.test.tsx`
Expected: FAIL.

- [ ] **Step 7: Modify `ChatMessage.tsx`**

Add `projectId?: string` to `ChatMessageProps`. After the existing "Add to Draft" footer inside the prose block card, render `<AIRating ... />` only when `projectId` is defined AND `message.prose` is truthy AND the message is an assistant message (it already is, per the render guard). Hook ordering: compute `ratingVm` first, then `useAIRating`.

Concrete edits:

1. Update the imports:

```tsx
import { AIRating } from "@/components/shared/ai-rating/AIRating";
import { chatRatingAdapter } from "@/lib/ai-rating/adapters/chat";
import { useAIRating } from "@/lib/hooks/useAIRating";
```

2. Add `readonly projectId?: string;` to `ChatMessageProps`.

3. Inside the memoized component, after the `addToDraft` button block (still inside the prose card), add:

```tsx
            {projectId && message.prose && (
              <ChatRatingControl
                messageId={message.id}
                prose={message.prose}
                projectId={projectId}
              />
            )}
```

4. Add a small sibling component below `ChatMessage` (in the same file, for RULE-04 — keeps the rating concern separate from the memoized bubble):

```tsx
function ChatRatingControl({
  messageId,
  prose,
  projectId,
}: {
  readonly messageId: string;
  readonly prose: string;
  readonly projectId: string;
}) {
  const vm = chatRatingAdapter({ messageId, prose, projectId, action: "accept" });
  const rating = useAIRating(vm);
  return (
    <AIRating
      viewModel={vm}
      state={rating.state}
      onSubmit={rating.submit}
      onSkip={rating.skip}
      onRetry={rating.reset}
    />
  );
}
```

> Why a sub-component: `ChatMessage` is `memo`'d — extracting the rating control keeps the bubble's memoization intact and avoids re-rendering the whole bubble on every rating keystroke.

5. Update the single caller (`ChatPanel.tsx`) to pass `projectId={novelId}`.

- [ ] **Step 8: Run all ChatMessage tests**

Run: `cd packages/web && pnpm exec vitest run components/studio/editor/__tests__/ChatMessage`
Expected: PASS (existing + new rating tests).

- [ ] **Step 9: Checkpoint (NO commit per plan policy)**

All five adoption surfaces complete: Co-Author, KB Field Suggest, KB Enhance, KB Improve, Chat.

---

## Task 13: Platform — AI Operation Inventory updates

**Files:**
- Modify: `scripts/checks/ai_operation_inventory.yaml`

- [ ] **Step 1: Inspect the inventory schema for the rating field**

Run: `cd /home/kiesow/projects/narrare && rg "rating" scripts/checks/ai_operation_inventory.yaml scripts/checks/_ai_interaction_checks/`
If no `rating_support` field is recognized by the gate, add it as an informational field that documents rating adoption without breaking the gate (verify by reading `scripts/checks/_ai_interaction_checks/` for the gate's field whitelist).

- [ ] **Step 2: Add a `rating_support` block to each rated operation**

For `writing.co_author`, `kb.field_suggest`, `kb.enhance`, `kb.improve`, and `chat.free_assistant`, add (indent to match the operation's existing keys):

```yaml
    rating_support:
      enabled: true
      source_type: co_author_change  # use the matching FeedbackSourceType value per operation
      adapter: packages/web/lib/ai-rating/adapters/coauthor.ts  # adjust per operation
      endpoint: POST /api/v1/memory/feedback
      aufg_id: CR-AUFG-07-24
```

Use the correct `source_type` value per operation:
- `writing.co_author` → `co_author_change` → `adapters/coauthor.ts`
- `kb.field_suggest` → `kb_field_suggest` → `adapters/kb-field.ts`
- `kb.enhance` → `kb_enhance_field` → `adapters/kb-enhance.ts`
- `kb.improve` → `kb_improve_suggestion` → `adapters/kb-improve.ts`
- `chat.free_assistant` → `chat_message` → `adapters/chat.ts`

- [ ] **Step 3: Run the inventory gate to verify nothing breaks**

Run: `cd /home/kiesow/projects/narrare && python scripts/check_architecture.py`
Expected: PASS (no regressions). If the gate complains about an unknown field, either (a) add the field to the gate's whitelist in `scripts/checks/_ai_interaction_checks/` (preferred — make it a tracked field) or (b) move the block under a clearly-labeled `cr_aufg_07_24_notes:` extension key the gate already ignores.

- [ ] **Step 4: Checkpoint (NO commit per plan policy)**

Inventory evidence recorded. Platform layer partial (parity test next).

---

## Task 14: Platform — API↔Frontend source-type parity test

**Files:**
- Create: `tests/integration/memory/test_feedback_source_type_parity.py`

- [ ] **Step 1: Write the parity test**

Create `tests/integration/memory/test_feedback_source_type_parity.py`:

```python
"""Cross-layer source taxonomy parity (CR-AUFG-07-24).

Asserts the canonical enum, the API Pydantic Literal, and the frontend
TypeScript union all describe the SAME closed set of source types. A drift
in any one of the three layers must fail CI here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from narrare_core.memory.source_types import FeedbackSourceType


REPO_ROOT = Path(__file__).resolve().parents[3]


def _extract_ts_union() -> set[str]:
    ts_path = REPO_ROOT / "packages" / "web" / "types" / "feedback.ts"
    text = ts_path.read_text(encoding="utf-8")
    # Match the body of `export type FeedbackSourceType = ... | "...";`
    match = re.search(
        r"export\s+type\s+FeedbackSourceType\s*=\s*([^;]+);",
        text,
    )
    assert match is not None, "FeedbackSourceType union missing in types/feedback.ts"
    return {p.strip().strip('"').strip("'") for p in match.group(1).split("|") if p.strip()}


def _extract_api_literal() -> set[str]:
    schemas_path = REPO_ROOT / "apps" / "api" / "narrare" / "memory" / "schemas.py"
    text = schemas_path.read_text(encoding="utf-8")
    # Match every `FeedbackSourceType.<NAME>.value` inside the Literal[...] alias.
    member_names = re.findall(r"FeedbackSourceType\.([A-Z_]+)\.value", text)
    assert member_names, "No FeedbackSourceType members referenced in schemas.py Literal"
    return {FeedbackSourceType[name].value for name in member_names}


class TestFeedbackSourceTypeParity:
    def test_core_enum_matches_api_literal(self) -> None:
        core = {m.value for m in FeedbackSourceType}
        assert _extract_api_literal() == core

    def test_core_enum_matches_frontend_union(self) -> None:
        core = {m.value for m in FeedbackSourceType}
        assert _extract_ts_union() == core

    def test_frontend_union_matches_api_literal(self) -> None:
        assert _extract_ts_union() == _extract_api_literal()

    def test_required_sources_are_present(self) -> None:
        """Spec-named sources must exist in the canonical enum."""
        core = {m.value for m in FeedbackSourceType}
        required = {
            "co_author_change",
            "kb_field_suggest",
            "kb_enhance_field",
            "kb_improve_suggestion",
            "chat_message",
        }
        assert required.issubset(core)
```

- [ ] **Step 2: Run the parity test**

Run: `pytest tests/integration/memory/test_feedback_source_type_parity.py -v`
Expected: PASS (4 tests). If any layer drifted (e.g. the TS union is missing a member), the test fails with a diff — fix the offending layer and re-run.

- [ ] **Step 3: Run the integration memory API test to confirm end-to-end still works**

Run: `pytest tests/integration/memory/test_memory_api.py -v`
Expected: PASS — the new `source_type` field is optional, so existing requests still succeed; new requests with `source_type` persist it into the `context` JSONB.

- [ ] **Step 4: Checkpoint (NO commit per plan policy)**

Platform layer complete. Docs next.

---

## Task 15: i18n — DE/EN/FR keys for rating affordances

**Files:**
- Modify: `packages/i18n/messages/en/studio.json`
- Modify: `packages/i18n/messages/de/studio.json`
- Modify: `packages/i18n/messages/fr/studio.json`

- [ ] **Step 1: Identify the keys the component references**

From `AIRating.tsx` (Task 6), the `studio.aiActions.*` keys used are:
- `rating` (exists — line 1745)
- `submitRating` (exists — line 1748)
- `skipRating` (exists — line 1749)
- `ratingSubmitted` (exists — line 1750)
- `ratingPrivacyNotice` (NEW)
- `ratingReason` (NEW)
- `ratingReasonPlaceholder` (NEW)
- `ratingSubmitting` (NEW)
- `ratingError` (NEW)
- `ratingRetry` (NEW)
- `ratingSkipped` (NEW)

- [ ] **Step 2: Add the new keys to EN**

In `packages/i18n/messages/en/studio.json`, inside the `"aiActions"` object, after the existing `"ratingSubmitted"` key, add:

```json
    "ratingPrivacyNotice": "Ratings are stored locally to help the AI learn your style (LEARN-001).",
    "ratingReason": "Optional reason",
    "ratingReasonPlaceholder": "Tell the AI why (optional)...",
    "ratingSubmitting": "Submitting...",
    "ratingError": "Could not submit rating.",
    "ratingRetry": "Retry",
    "ratingSkipped": "Rating skipped.",
```

- [ ] **Step 3: Add the matching keys to DE**

In `packages/i18n/messages/de/studio.json`, in the same position inside `aiActions`:

```json
    "ratingPrivacyNotice": "Bewertungen werden lokal gespeichert, damit die AI deinen Stil lernt (LEARN-001).",
    "ratingReason": "Optionale Begründung",
    "ratingReasonPlaceholder": "Sag der AI, warum (optional)...",
    "ratingSubmitting": "Wird gesendet...",
    "ratingError": "Bewertung konnte nicht gesendet werden.",
    "ratingRetry": "Erneut versuchen",
    "ratingSkipped": "Bewertung übersprungen.",
```

- [ ] **Step 4: Add the matching keys to FR**

In `packages/i18n/messages/fr/studio.json`, in the same position inside `aiActions`:

```json
    "ratingPrivacyNotice": "Les évaluations sont stockées localement pour aider l'IA à apprendre votre style (LEARN-001).",
    "ratingReason": "Raison facultative",
    "ratingReasonPlaceholder": "Dites à l'IA pourquoi (facultatif)...",
    "ratingSubmitting": "Envoi...",
    "ratingError": "Impossible d'envoyer l'évaluation.",
    "ratingRetry": "Réessayer",
    "ratingSkipped": "Évaluation ignorée.",
```

- [ ] **Step 5: Run the i18n parity gate**

Run: `cd /home/kiesow/projects/narrare && python scripts/check_architecture.py`
Expected: PASS — i18n parity gate (Check 6 / parity check) green for all three locales.

- [ ] **Step 6: Checkpoint (NO commit per plan policy)**

i18n complete.

---

## Task 16: Docs — LEARN-001/INFRA-005 help text + AUFG registry evidence

**Files:**
- Modify: `docs/architecture/governance/aufg-registry.md`
- Modify: LEARN-001 / INFRA-005 help docs (locate via the registry pointer; see Step 1)

- [ ] **Step 1: Locate the LEARN-001 and INFRA-005 doc paths**

Run: `cd /home/kiesow/projects/narrare && rg -l "LEARN-001|INFRA-005" docs/ --type md | head -20`

Expected hits include a LEARN-001 feature spec and an INFRA-005 privacy/infra note. Read the most relevant one (likely `docs/features/learning/` or `docs/features/memory/`).

- [ ] **Step 2: Add a "Rating expansion" subsection to the LEARN-001 doc**

Append (or update) a short subsection describing:
- Rating is now collected on Co-Author change review, KB field-suggest/enhance/improve, and Chat assistant prose blocks.
- Ratings ride the existing `POST /memory/feedback` endpoint with the closed `source_type` taxonomy.
- No raw prose is forwarded to mem0 — only the action, intent, rating, reason, and `source_type` (RULE-22 / INFRA-005).

Concrete content to insert (adapt to the doc's existing heading style):

```markdown
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
```

- [ ] **Step 3: Update the AUFG registry lifecycle pointer**

In `docs/architecture/governance/aufg-registry.md`, locate the CR-AUFG-07-24 row in the CR-07 Phase C table (around line 485). Update its lifecycle status and add an exit-evidence pointer. Replace the row:

```markdown
| CR-AUFG-07-24 | C | AI feedback rating expansion | `open` | P2 | Extend rating to Co-Author, KB flows, and Chat through LEARN-001-compatible persistence/memory contract. |
```

with:

```markdown
| CR-AUFG-07-24 | C | AI feedback rating expansion | `resolved` | P2 | Extend rating to Co-Author, KB flows, and Chat through LEARN-001-compatible persistence/memory contract. Implementation: `packages/core/narrare_core/memory/source_types.py`, `apps/api/narrare/memory/schemas.py` (`source_type`), `packages/web/lib/ai-rating/*`, `packages/web/components/shared/ai-rating/AIRating.tsx`, adoption in `ChangeReview`/`EnhanceReviewCard`/`ImproveSuggestionCard`/`FieldSuggestionReview`/`ChatMessage`. Enforcement: `tests/integration/memory/test_feedback_source_type_parity.py` + per-surface vitest tests. See plan `docs/superpowers/plans/2026-06-22-cr-07-phase-c-07-24-feedback-rating.md`. |
```

Also update the "Last updated" line at the top of the registry to mention CR-AUFG-07-24 resolved with the date.

- [ ] **Step 4: Run the architecture gate**

Run: `cd /home/kiesow/projects/narrare && python scripts/check_architecture.py`
Expected: PASS.

- [ ] **Step 5: Checkpoint (NO commit per plan policy)**

Docs complete. All tasks done.

---

## Final verification (run after Task 16)

- [ ] **Backend:** `pytest tests/unit/core/memory/ tests/unit/api/memory/ tests/integration/memory/ -v` — all green.
- [ ] **Frontend type check:** `cd packages/web && pnpm exec tsc --noEmit` — no errors.
- [ ] **Frontend unit/component tests:** `cd packages/web && pnpm exec vitest run lib/ai-rating components/shared/ai-rating lib/hooks/__tests__/useAIRating components/studio/editor/__tests__/ChangeReview components/studio/editor/__tests__/ChatMessage components/studio/kb/__tests__/KBEnhanceReview components/studio/kb/__tests__/KBImprovePanel components/studio/kb/__tests__/FieldSuggestionReview` — all green.
- [ ] **Architecture gate:** `python scripts/check_architecture.py` — green (RULE-04 file sizes, RULE-16 i18n, inventory gate).
- [ ] **Parity:** `pytest tests/integration/memory/test_feedback_source_type_parity.py -v` — green (3 layers in sync).
- [ ] **Self-review checklist below** — completed.

---

## Self-Review

**1. Spec coverage:**

| Spec requirement | Covered? | Task |
|------------------|----------|------|
| Reuse `record_feedback`, no new `record()` | ✅ | Tasks 2/3 add only a field; no contract method added |
| Typed source taxonomy (5 values) | ✅ | Task 1 enum, Task 2 schema Literal, Task 4 TS union, Task 14 parity |
| Stable `suggestion_id` (no orphan ratings) | ✅ | Task 5 contract requires `sourceId`; adapters pull host-native ids |
| Co-Author rating | ✅ | Task 8 |
| KB field/enhance/improve rating | ✅ | Tasks 9, 10, 11 |
| Chat rating | ✅ | Task 12 |
| Non-blocking, skip, loading/success/error/retry | ✅ | Task 6 component + Task 7 hook state machine |
| Privacy copy (LEARN-001/INFRA-005) | ✅ | Task 15 `ratingPrivacyNotice` + Task 16 docs |
| No raw excerpts to mem0 | ✅ | Existing `_translate_to_memory_text` already privacy-safe; only metadata added (Task 3 Step 5) |
| Reuse `feedback_events.context` JSONB (no migration) | ✅ | Task 3 — no Alembic step |
| i18n DE/EN/FR | ✅ | Task 15 |
| Backend tests (taxonomy + privacy-safe event) | ✅ | Tasks 1, 2, 3 |
| Frontend tests (submission/skip/error per surface) | ✅ | Tasks 6, 7, 8–12 |
| API↔Frontend schema parity | ✅ | Task 14 |
| AI Operation Inventory updates | ✅ | Task 13 |
| Out-of-scope: streaming rating | ✅ respected | Task 12 scope guardrail |

**2. Placeholder scan:**

Searched plan for: "TBD", "TODO", "implement later", "fill in", "Add appropriate", "handle edge cases", "Similar to Task N". The only intentionally-soft instructions are:
- Task 11 Step 2 ("identify the suggestion type via Read") — this is a deliberate discovery step because `FieldSuggestionReview.tsx`'s prop shape was not pre-read; the test code in Step 2 is fully specified once the type is known. Acceptable: the step tells the engineer exactly what to assert.
- Task 16 Step 1 ("locate the doc via rg") — same pattern; the doc content in Step 2 is fully written.

No other placeholders.

**3. Type consistency:**

- `AIRatingViewModel` fields used in `build-feedback.ts`, every adapter, and every adoption test match `contracts.ts` exactly: `sourceType`, `sourceId`, `projectId`, `intent`, `suggestionText`, `action`, `chapterId`, `genre`, `mode`. ✓
- `AIRatingState` values used in `AIRating.tsx` (`idle|loading|success|error|skipped`) match the hook's `useState<AIRatingState>` and the test assertions. ✓
- `FeedbackSourceType` string values are identical across `source_types.py`, the Pydantic Literal, and the TS union — enforced by Task 14. ✓
- Adapter function names match `lib/ai-rating/index.ts` exports: `coAuthorRatingAdapter`, `kbFieldSuggestRatingAdapter`, `kbEnhanceRatingAdapter`, `kbImproveRatingAdapter`, `chatRatingAdapter`. ✓
- Hook return shape `{ state, submit, skip, reset }` is consistent across `useAIRating.ts`, every adoption block, and the adoption tests. ✓

**4. Architecture gate alignment:**

- RULE-04 (file size): every new file is single-responsibility and small; no existing file grows past its limit (largest modification is `ChangeReview.tsx` at ~110 lines, well under any threshold).
- RULE-16 (i18n): every visible string in `AIRating.tsx` and the adoption code paths uses `studio.aiActions.*` keys; no hardcoded English.
- RULE-20 (no parallel learning store): all ratings go through `POST /memory/feedback`.
- RULE-22 (privacy): mem0 receives only metadata, never raw prose.
- Cross-layer ordering: Core (1) → Backend (2, 3) → Frontend types (4) → Frontend shared (5, 6, 7) → Adoption (8–12) → Platform (13, 14) → Docs (15, 16). No task depends on a later task.

**5. Known risks / trade-offs accepted:**

- **Dual feedback endpoints for Co-Author.** Co-Author already uses `/writing/chapters/{id}/co-author/feedback` for accept/reject. CR-AUFG-07-24 adds the rating through the canonical `/memory/feedback`. This is intentional (RULE-20: one learning path for ratings). The legacy endpoint is untouched. Mitigation: documented in Task 8 design note + LEARN-001 doc update (Task 16). Trigger to revisit: if/when Co-Author accept/reject is migrated to `/memory/feedback` wholesale.
- **Rating is REST, not SSE.** Per spec explicit framing. No SSE infrastructure is bypassed — there is no streaming feedback endpoint to consume.
- **`source_type` is optional on the schema.** Chosen for back-compat: existing callers (annotation rating, generation panel) continue to work without changes. New rating surfaces always set it. Task 14 parity test enforces the closed set when it IS set.
- **`AIRating` always renders the privacy notice.** Slightly more chrome per rated surface; accepted because the spec explicitly requires the privacy copy to be visible at the rating affordance.

---

## Execution Handoff

After the coordinator approves this plan, the recommended execution mode is **subagent-driven** (one fresh subagent per task, two-stage review between tasks) given the cross-layer scope. Alternative: inline execution with checkpoints after each layer (Core/Backend → Frontend shared → Adoption → Platform/Docs).

The plan contains **no commit steps**. The coordinator decides when to commit (suggested: one commit per layer, or one commit at the very end with the AUFG registry update).
