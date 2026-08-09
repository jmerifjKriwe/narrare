"""Event publisher — in-process event bus for domain events.

Provides a simple in-process event bus for publishing domain events.
Events are dispatched to registered handlers synchronously.
Supports both broadcast handlers (receive all events) and typed
handlers (receive events of a specific type only).
Handlers run in-process (ADR-080) and may trigger further in-process
background work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

import structlog
from fastapi import Depends

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from narrare_core.events.types import EventType

logger = structlog.get_logger(__name__)


class EventPublisher:
    """Simple in-process event publisher for domain events.

    Handlers are registered via ``add_handler()`` (broadcast — receives
    all events) or ``subscribe()`` (typed — receives only matching events).
    When an event is published, typed handlers are called first, then
    broadcast handlers.

    Handlers run in-process (ADR-080); a handler may forward events to
    in-process background tasks.
    """

    def __init__(self) -> None:
        self._handlers: list[Any] = []
        self._typed_handlers: dict[str, list[Any]] = {}

    def add_handler(self, handler: Any) -> None:
        """Register a broadcast handler (receives all events).

        Args:
            handler: A callable that accepts domain events.
        """
        self._handlers.append(handler)

    def subscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Register a handler for a specific event type.

        The handler is called only when the dispatched event's
        ``event_type`` matches ``event_type``.

        Args:
            event_type: Event type string (e.g. ``"kb.entry.updated"``).
            handler: Async callable accepting a single DomainEvent.
        """
        self._typed_handlers.setdefault(event_type, []).append(handler)

    async def publish(
        self,
        event_type: EventType,
        *,
        aggregate_id: UUID,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Publish a domain event to subscribed handlers (in-process, ADR-080).

        Constructs a :class:`~narrare_core.events.types.DomainEvent` and
        dispatches it to typed handlers whose subscribed event-type string
        matches ``str(event_type)`` (``EventType`` is a ``StrEnum``).

        Args:
            event_type: The ``EventType`` to publish.
            aggregate_id: The primary entity the event is about.
            payload: Arbitrary data relevant to the event (may be empty).
        """
        from narrare_core.events.types import DomainEvent

        event = DomainEvent(
            event_type=event_type,
            aggregate_id=aggregate_id,
            payload=payload or {},
        )
        await self._dispatch(event)

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

        Typed handlers matching the event's ``event_type`` are called
        first, then broadcast handlers.  Handler failures are logged but
        do not prevent other handlers from running (RULE-11: no silent
        failures, but no cascading failures either).

        Args:
            event: The domain event to dispatch.
        """
        event_type_str = str(getattr(event, "event_type", ""))

        # Typed handlers (specific event type)
        for handler in self._typed_handlers.get(event_type_str, []):
            try:
                await handler(event)
            except Exception:
                logger.warning(
                    "typed_event_handler_failed",
                    handler=handler.__class__.__name__,
                    event_type=event_type_str,
                    exc_info=True,
                )

        # Broadcast handlers (all events)
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


def get_wiki_event_publisher(request: Any) -> EventPublisher | None:
    """Return the in-process wiki ``EventPublisher`` from ``app.state``.

    The lifespan binds ``app.state.wiki_event_publisher`` at startup. When
    initialisation failed (the lifespan swallows that error) the attribute
    is absent and this returns ``None`` — producers then degrade to a
    no-op (graceful degradation, RULE-11).

    Args:
        request: The FastAPI ``Request`` (``request.app.state`` is read).

    Returns:
        The shared ``EventPublisher`` or ``None`` if unbound.
    """
    return getattr(request.app.state, "wiki_event_publisher", None)


# FastAPI dependency alias (avoids bare ``Depends()`` in default arguments —
# ruff B008 — matching the ``SessionDep`` Annotated pattern). Resolves the
# in-process wiki EventPublisher from ``app.state``, or ``None``.
WikiEventPublisherDep = Annotated[EventPublisher | None, Depends(get_wiki_event_publisher)]
