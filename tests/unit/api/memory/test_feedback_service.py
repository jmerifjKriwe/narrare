"""Unit tests for MemoryFeedbackService — event publishing and enriched context."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from narrare.memory.schemas import FeedbackRequest
from tests.fakes import FakeCoreFeedbackService, FakeEventPublisher, FakeFeedbackRepository


class TestMemoryFeedbackService:
    def _make_service(
        self, *, with_publisher: bool = False
    ) -> tuple[Any, FakeCoreFeedbackService, FakeEventPublisher | None]:
        from narrare.memory.service import MemoryFeedbackService

        core = FakeCoreFeedbackService()
        publisher = FakeEventPublisher() if with_publisher else None
        repo = FakeFeedbackRepository()
        service = MemoryFeedbackService(
            repository=repo,
            core_feedback=core,
            event_publisher=publisher,
        )
        return service, core, publisher

    async def test_record_feedback_passes_rating_to_event(self) -> None:
        service, core, _ = self._make_service()
        user_id = uuid4()
        request = FeedbackRequest(
            action="accept",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="The forest was dark.",
            project_id=uuid4(),
            rating=4,
        )

        response = await service.record_feedback(request, user_id)

        assert len(core.recorded) == 1
        event = core.recorded[0]
        assert event.rating == 4
        assert response.action == "accept"

    async def test_record_feedback_enriches_context_with_genre(self) -> None:
        service, core, _ = self._make_service()
        request = FeedbackRequest(
            action="accept",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="The moon shone.",
            project_id=uuid4(),
            genre="Fantasy",
            mode="creative",
            chapter_id=uuid4(),
        )

        await service.record_feedback(request, uuid4())

        event = core.recorded[0]
        assert event.context["genre"] == "Fantasy"
        assert event.context["mode"] == "creative"
        assert "chapter_id" in event.context

    async def test_record_feedback_without_rating(self) -> None:
        service, core, _ = self._make_service()
        request = FeedbackRequest(
            action="reject",
            suggestion_id=uuid4(),
            intent="edit",
            suggestion_text="He walked slowly.",
            project_id=uuid4(),
        )

        await service.record_feedback(request, uuid4())

        event = core.recorded[0]
        assert event.rating is None

    async def test_record_feedback_publishes_event(self) -> None:
        service, _core, publisher = self._make_service(with_publisher=True)
        user_id = uuid4()
        request = FeedbackRequest(
            action="accept",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="Good text.",
            project_id=uuid4(),
            rating=5,
        )

        await service.record_feedback(request, user_id)

        assert publisher is not None
        assert len(publisher.published) == 1
        assert publisher.published[0]["user_id"] == user_id
        assert publisher.published[0]["project_id"] == request.project_id

    async def test_record_feedback_without_publisher_still_works(self) -> None:
        service, _core, _ = self._make_service(with_publisher=False)
        request = FeedbackRequest(
            action="modify",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="Original",
            modification="Changed",
            project_id=uuid4(),
        )

        response = await service.record_feedback(request, uuid4())
        assert response.action == "modify"

    async def test_record_feedback_publisher_failure_does_not_raise(self) -> None:
        service, core, _ = self._make_service(with_publisher=False)

        failing_publisher = FakeEventPublisher()
        failing_publisher.fail_on_publish(ConnectionError("broker down"))
        service._event_publisher = failing_publisher

        request = FeedbackRequest(
            action="accept",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="Text",
            project_id=uuid4(),
        )

        # Should NOT raise
        response = await service.record_feedback(request, uuid4())
        assert response.action == "accept"
        assert len(core.recorded) == 1
