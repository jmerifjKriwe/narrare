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
