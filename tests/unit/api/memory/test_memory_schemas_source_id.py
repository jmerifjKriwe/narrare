"""Schema tests for the source_id identifier policy (CR-AUFG-07-24).

Extracted from ``test_memory_schemas.py`` to respect RULE-04 file-size limits.
Covers the ``FeedbackRequest`` acceptance of canonical frontend source IDs,
trimming, length bounds, and mutual-exclusion with ``suggestion_id``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare.memory.schemas import FeedbackRequest


class TestFeedbackRequestSourceId:
    def test_accepts_source_id_with_source_type_without_suggestion_id(self) -> None:
        """API boundary accepts frontend canonical IDs before service UUID resolution."""
        req = FeedbackRequest(
            action="accept",
            source_id="kb-field:entry-title",
            source_type="kb_field_suggest",
            intent="write",
            suggestion_text="text",
            project_id=uuid4(),
        )
        assert req.suggestion_id is None
        assert req.source_id == "kb-field:entry-title"

    def test_source_id_is_trimmed_before_service_resolution(self) -> None:
        req = FeedbackRequest(
            action="accept",
            source_id="  coauthor-change-42  ",
            source_type="co_author_change",
            intent="write",
            suggestion_text="text",
            project_id=uuid4(),
        )
        assert req.source_id == "coauthor-change-42"

    def test_missing_suggestion_id_and_source_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    def test_source_id_without_source_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                source_id="kb-field:entry-title",
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    def test_blank_source_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                source_id="   ",
                source_type="kb_field_suggest",
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    def test_too_long_source_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                source_id="x" * 257,
                source_type="kb_field_suggest",
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    def test_invalid_non_uuid_suggestion_id_without_source_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                suggestion_id="not-a-uuid",  # type: ignore[arg-type]  # intentional invalid for validation test
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )
