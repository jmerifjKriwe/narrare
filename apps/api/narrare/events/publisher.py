"""Event publisher — in-process event bus for domain events.

Provides a simple in-process event bus for publishing domain events.
Events are dispatched to registered handlers synchronously.
For TaskIQ integration, handlers forward events to task workers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger(__name__)


class EventPublisher:
    """Simple in-process event publisher for domain events.

    Handlers are registered via ``add_handler()``. When an event is
    published, all registered handlers are called in order.

    For TaskIQ integration, a handler is registered that forwards
    events to the appropriate TaskIQ task.
    """

    def __init__(self) -> None:
        self._handlers: list[Any] = []

    def add_handler(self, handler: Any) -> None:
        """Register an event handler callable.

        Args:
            handler: A callable that accepts domain events.
        """
        self._handlers.append(handler)

    async def publish_feedback_recorded(
        self,
        user_id: UUID,
        project_id: UUID,
        event_id: UUID,
    ) -> None:
        """Publish a FeedbackRecorded event.

        Args:
            user_id: The user who provided feedback.
            project_id: The project the feedback belongs to.
            event_id: The ID of the recorded event.
        """
        from narrare.events.feedback_events import FeedbackRecorded

        event = FeedbackRecorded(
            user_id=user_id,
            project_id=project_id,
            event_id=event_id,
        )
        await self._dispatch(event)

    async def publish_analysis_triggered(
        self,
        user_id: UUID,
        project_id: UUID,
        event_count: int,
    ) -> None:
        """Publish a PreferenceAnalysisTriggered event.

        Args:
            user_id: The user whose preferences should be analyzed.
            project_id: The project to analyze.
            event_count: Number of events at trigger time.
        """
        from narrare.events.feedback_events import PreferenceAnalysisTriggered

        event = PreferenceAnalysisTriggered(
            user_id=user_id,
            project_id=project_id,
            event_count=event_count,
        )
        await self._dispatch(event)

    async def _dispatch(self, event: Any) -> None:
        """Dispatch an event to all registered handlers.

        Handler failures are logged but do not prevent other handlers
        from running (RULE-11: no silent failures, but no cascading
        failures either).

        Args:
            event: The domain event to dispatch.
        """
        for handler in self._handlers:
            try:
                await handler(event)
            except Exception:
                logger.warning(
                    "event_handler_failed",
                    handler=handler.__class__.__name__,
                    event_type=type(event).__name__,
                    exc_info=True,
                )
