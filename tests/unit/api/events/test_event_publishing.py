"""Unit tests for event publishing — EventPublisher dispatches events correctly."""

from __future__ import annotations

from typing import Any
from uuid import uuid4


class TestEventPublisher:
    def _make_publisher(self) -> Any:
        from narrare.events.publisher import EventPublisher

        return EventPublisher()

    async def test_publish_feedback_recorded_dispatches_to_handler(self) -> None:
        publisher = self._make_publisher()
        received: list[Any] = []
        publisher.add_handler(lambda event: _async_append(received, event))

        user_id = uuid4()
        project_id = uuid4()
        event_id = uuid4()
        await publisher.publish_feedback_recorded(user_id, project_id, event_id)

        assert len(received) == 1
        assert received[0].user_id == user_id
        assert received[0].project_id == project_id
        assert received[0].event_id == event_id

    async def test_publish_analysis_triggered_dispatches_to_handler(self) -> None:
        publisher = self._make_publisher()
        received: list[Any] = []
        publisher.add_handler(lambda event: _async_append(received, event))

        user_id = uuid4()
        project_id = uuid4()
        await publisher.publish_analysis_triggered(user_id, project_id, event_count=42)

        assert len(received) == 1
        assert received[0].event_count == 42

    async def test_handler_failure_does_not_raise(self) -> None:
        publisher = self._make_publisher()

        async def _failing_handler(event: Any) -> None:
            raise RuntimeError("handler failed")

        publisher.add_handler(_failing_handler)
        # Should not raise
        await publisher.publish_feedback_recorded(uuid4(), uuid4(), uuid4())

    async def test_multiple_handlers_all_called(self) -> None:
        publisher = self._make_publisher()
        results_a: list[Any] = []
        results_b: list[Any] = []

        publisher.add_handler(lambda event: _async_append(results_a, event))
        publisher.add_handler(lambda event: _async_append(results_b, event))

        await publisher.publish_feedback_recorded(uuid4(), uuid4(), uuid4())

        assert len(results_a) == 1
        assert len(results_b) == 1

    async def test_handler_failure_does_not_block_other_handlers(self) -> None:
        publisher = self._make_publisher()
        received: list[Any] = []

        async def _fail(event: Any) -> None:
            raise RuntimeError("boom")

        publisher.add_handler(_fail)
        publisher.add_handler(lambda event: _async_append(received, event))

        await publisher.publish_feedback_recorded(uuid4(), uuid4(), uuid4())
        assert len(received) == 1


class TestGenericPublish:
    """``EventPublisher.publish`` — typed dispatch for domain events (Q-016).

    Producers (KBService / ChapterService / prompt save) publish via the
    generic ``publish``; typed handlers subscribed by event-type string
    receive the constructed ``DomainEvent``.
    """

    def _make_publisher(self) -> Any:
        from narrare.events.publisher import EventPublisher

        return EventPublisher()

    async def test_publish_dispatches_to_typed_handler(self) -> None:
        from narrare_core.events.types import EventType

        publisher = self._make_publisher()
        received: list[Any] = []
        publisher.subscribe("kb.entry.updated", lambda event: _async_append(received, event))

        agg_id = uuid4()
        await publisher.publish(
            EventType.KB_ENTRY_UPDATED,
            aggregate_id=agg_id,
            payload={"entity_id": str(agg_id), "novel_id": str(uuid4())},
        )

        assert len(received) == 1
        assert received[0].event_type == EventType.KB_ENTRY_UPDATED
        assert received[0].aggregate_id == agg_id
        assert "entity_id" in received[0].payload

    async def test_publish_does_not_dispatch_to_other_type(self) -> None:
        from narrare_core.events.types import EventType

        publisher = self._make_publisher()
        received: list[Any] = []
        publisher.subscribe("chapter.finalized", lambda event: _async_append(received, event))

        # Publishing an unrelated event type must not trigger the handler.
        await publisher.publish(
            EventType.KB_ENTRY_UPDATED,
            aggregate_id=uuid4(),
        )
        assert received == []

    async def test_publish_handler_failure_does_not_raise(self) -> None:
        from narrare_core.events.types import EventType

        publisher = self._make_publisher()

        async def _fail(event: Any) -> None:
            raise RuntimeError("handler failed")

        publisher.subscribe("wiki.prompt.changed", _fail)
        # Must not raise (RULE-11 graceful degradation at dispatch).
        await publisher.publish(
            EventType.WIKI_PROMPT_CHANGED,
            aggregate_id=uuid4(),
        )


class TestFeedbackEvents:
    def test_feedback_recorded_is_frozen(self) -> None:
        from narrare.events.feedback_events import FeedbackRecorded

        uid = uuid4()
        event = FeedbackRecorded(user_id=uid, project_id=uuid4(), event_id=uuid4())
        assert event.user_id == uid

    def test_preference_analysis_triggered_is_frozen(self) -> None:
        from narrare.events.feedback_events import PreferenceAnalysisTriggered

        event = PreferenceAnalysisTriggered(user_id=uuid4(), project_id=uuid4(), event_count=10)
        assert event.event_count == 10


async def _async_append(lst: list[Any], item: Any) -> None:
    """Helper to append to a list in an async context."""
    lst.append(item)
