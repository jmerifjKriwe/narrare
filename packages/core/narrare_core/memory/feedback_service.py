"""Feedback service — records user feedback and forwards to mem0.

Implements the FeedbackCollector protocol. Persists feedback events
to the feedback_events table (via injected callback) and translates
them to mem0 memory inputs for semantic preference extraction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.memory.models import FeedbackAction, FeedbackEvent

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger(__name__)


class FeedbackService:
    """Records feedback events and forwards to mem0 for preference extraction.

    Uses dual storage (D3):

    1. ``feedback_events`` table (via ``persist_fn`` callback) — immutable
       audit trail.
    2. mem0 ``AsyncMemory`` — semantic preference extraction.

    mem0 forwarding is best-effort: failures are logged as warnings and
    never raised, ensuring the audit trail is always preserved.

    Implements:
        FeedbackCollector protocol.
    """

    def __init__(
        self,
        mem0_client: Any,  # mem0 AsyncMemory or NullMemoryClient
        persist_fn: Any,  # async callable(event: FeedbackEvent) -> None
    ) -> None:
        self._mem0 = mem0_client
        self._persist = persist_fn

    async def record(self, event: FeedbackEvent) -> None:
        """Record a feedback event to DB and forward to mem0.

        DB persist always happens. mem0 forward is best-effort:
        failures are logged as warnings, not raised.
        """
        # Always persist to DB first
        await self._persist(event)

        # Forward to mem0 (best-effort)
        try:
            memory_text = self._translate_to_memory_text(event)
            await self._mem0.add(
                data=memory_text,
                user_id=str(event.user_id),
                app_id=str(event.project_id),
                metadata={
                    "action": event.action.value,
                    "intent": event.intent,
                    "suggestion_id": str(event.suggestion_id),
                },
            )
        except Exception:
            logger.warning(
                "mem0_forward_failed",
                event_id=str(event.id),
                action=event.action.value,
            )

    async def get_history(
        self,
        user_id: UUID,
        project_id: UUID,
        *,
        limit: int = 100,
    ) -> list[FeedbackEvent]:
        """Retrieve recent feedback events from DB.

        Delegates to the API layer's repository for actual DB queries.
        Returns an empty list until the API memory module is wired up.
        """
        # Actual DB query lives in the API layer via repository.
        # This method satisfies protocol conformance and will be
        # populated when the API memory module is built.
        return []

    @staticmethod
    def _translate_to_memory_text(event: FeedbackEvent) -> str:
        """Translate a FeedbackEvent into mem0-compatible memory text.

        Formats the event as natural language that mem0 can extract
        preferences from. Includes rating and enriched context when
        available.
        """
        if event.action == FeedbackAction.ACCEPT:
            text = f'User accepted a {event.intent} suggestion: "{event.suggestion_text[:200]}"'
        elif event.action == FeedbackAction.REJECT:
            text = f'User rejected a {event.intent} suggestion: "{event.suggestion_text[:200]}"'
            if event.modification:
                text += f" (reason: {event.modification})"
        elif event.action == FeedbackAction.MODIFY:
            text = (
                f"User modified a {event.intent} suggestion. "
                f'Original: "{event.suggestion_text[:100]}". '
                f'Their version: "{event.modification[:100]}"'
            )
        else:
            text = f"User interacted with a {event.intent} suggestion."

        # Append rating if present
        if event.rating:
            text += f" (rating: {event.rating}/5)"

        # Append enriched context (chapter_id, genre, mode)
        extra_parts: list[str] = []
        if event.context.get("chapter_id"):
            extra_parts.append(f"chapter: {event.context['chapter_id']}")
        if event.context.get("genre"):
            extra_parts.append(f"genre: {event.context['genre']}")
        if event.context.get("mode"):
            extra_parts.append(f"mode: {event.context['mode']}")
        if extra_parts:
            text += f" [{', '.join(extra_parts)}]"

        return text
