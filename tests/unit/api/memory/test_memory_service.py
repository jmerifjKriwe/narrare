"""Unit tests for MemoryFeedbackService — API-layer feedback recording.

Tests the API service that wraps the core FeedbackService with DB
persistence. The core FeedbackService is faked via fixtures in
``conftest.py``. Preference-service tests live in
``test_memory_preference_service.py`` (split for RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from narrare.memory.schemas import (
    FeedbackRequest,
    FeedbackResponse,
)
from tests.unit.api.memory.conftest import make_feedback_request

if TYPE_CHECKING:
    from tests.unit.api.memory.conftest import FakeCoreFeedback


class TestRecordFeedback:
    async def test_record_feedback_creates_event_and_calls_core(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        user_id = uuid4()
        request = make_feedback_request()

        await feedback_service.record_feedback(request, user_id)

        assert len(fake_core_feedback.recorded) == 1
        event = fake_core_feedback.recorded[0]
        assert event.user_id == user_id
        assert event.project_id == request.project_id
        assert event.action.value == "accept"
        assert event.suggestion_text == "The forest was dark and mysterious."

    async def test_record_feedback_with_rating(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        request = make_feedback_request(rating=4)

        response = await feedback_service.record_feedback(request, uuid4())

        assert isinstance(response, FeedbackResponse)
        assert response.action == "accept"
        event = fake_core_feedback.recorded[0]
        assert event.rating == 4

    async def test_record_feedback_enriches_context_with_chapter_genre_mode(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        chapter_id = uuid4()
        request = make_feedback_request(
            chapter_id=chapter_id,
            genre="Fantasy",
            mode="creative",
        )

        await feedback_service.record_feedback(request, uuid4())

        event = fake_core_feedback.recorded[0]
        assert event.context["chapter_id"] == str(chapter_id)
        assert event.context["genre"] == "Fantasy"
        assert event.context["mode"] == "creative"

    async def test_record_feedback_modification_action(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        request = make_feedback_request(
            action="modify",
            modification="Changed to past tense.",
        )

        response = await feedback_service.record_feedback(request, uuid4())

        assert response.action == "modify"
        event = fake_core_feedback.recorded[0]
        assert event.modification == "Changed to past tense."

    async def test_record_feedback_validates_required_action(
        self,
    ) -> None:
        """Pydantic validates the action field pattern."""
        with pytest.raises(ValueError):
            FeedbackRequest(
                action="invalid_action",
                suggestion_id=uuid4(),
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    async def test_record_feedback_propagates_source_type_into_context(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        """source_type flows schema → service → event.context (CR-AUFG-07-24)."""
        request = make_feedback_request(source_type="co_author_change")

        await feedback_service.record_feedback(request, uuid4())

        event = fake_core_feedback.recorded[0]
        assert event.context["source_type"] == "co_author_change"

    async def test_record_feedback_omits_source_type_key_when_none(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        """Back-compat: existing callers without source_type must not see a key."""
        request = make_feedback_request()  # source_type defaults to None

        await feedback_service.record_feedback(request, uuid4())

        event = fake_core_feedback.recorded[0]
        assert "source_type" not in event.context

    async def test_record_feedback_resolves_source_id_to_uuid(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        request = make_feedback_request(
            suggestion_id=None,
            source_id="kb-field:entry-title",
            source_type="kb_field_suggest",
        )

        await feedback_service.record_feedback(request, uuid4())

        event = fake_core_feedback.recorded[0]
        assert event.suggestion_id is not None
        assert event.suggestion_id.version == 5

    async def test_record_feedback_resolves_same_source_identity_to_same_uuid(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        user_id = uuid4()
        project_id = uuid4()
        first = make_feedback_request(
            suggestion_id=None,
            project_id=project_id,
            source_id="  coauthor-change-42  ",
            source_type="co_author_change",
        )
        second = make_feedback_request(
            suggestion_id=None,
            project_id=project_id,
            source_id="coauthor-change-42",
            source_type="co_author_change",
        )

        await feedback_service.record_feedback(first, user_id)
        await feedback_service.record_feedback(second, user_id)

        assert (
            fake_core_feedback.recorded[0].suggestion_id
            == fake_core_feedback.recorded[1].suggestion_id
        )

    async def test_record_feedback_resolves_different_source_parts_to_different_uuids(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        user_id = uuid4()
        project_id = uuid4()
        cases = [
            make_feedback_request(
                suggestion_id=None,
                project_id=project_id,
                source_id="source-a",
                source_type="kb_field_suggest",
            ),
            make_feedback_request(
                suggestion_id=None,
                project_id=uuid4(),
                source_id="source-a",
                source_type="kb_field_suggest",
            ),
            make_feedback_request(
                suggestion_id=None,
                project_id=project_id,
                source_id="source-a",
                source_type="kb_enhance_field",
            ),
            make_feedback_request(
                suggestion_id=None,
                project_id=project_id,
                source_id="source-b",
                source_type="kb_field_suggest",
            ),
        ]

        for request in cases:
            await feedback_service.record_feedback(request, user_id)

        suggestion_ids = {event.suggestion_id for event in fake_core_feedback.recorded}
        assert len(suggestion_ids) == len(cases)

    async def test_record_feedback_does_not_forward_raw_source_id_in_context(
        self,
        feedback_service: Any,
        fake_core_feedback: FakeCoreFeedback,
    ) -> None:
        request = make_feedback_request(
            suggestion_id=None,
            source_id="raw-frontend-id-123",
            source_type="chat_message",
        )

        await feedback_service.record_feedback(request, uuid4())

        event = fake_core_feedback.recorded[0]
        assert "source_id" not in event.context
        assert event.context["source_type"] == "chat_message"
        assert event.context["source_id_hash"] != "raw-frontend-id-123"
