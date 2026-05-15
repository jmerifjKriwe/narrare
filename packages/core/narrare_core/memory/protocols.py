"""Protocol contracts for the memory subsystem.

Defines the interfaces that memory adapters must implement.
All implementations are injected via constructor (DI pattern).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from narrare_core.memory.models import (
        FeedbackEvent,
        PreferenceProfile,
    )


class FeedbackCollector(Protocol):
    """Collects and retrieves user feedback on AI suggestions."""

    async def record(self, event: FeedbackEvent) -> None:
        """Persist a feedback event."""
        ...

    async def get_history(
        self,
        user_id: object,
        project_id: object,
        *,
        limit: int = 100,
    ) -> list[FeedbackEvent]:
        """Retrieve recent feedback events for a user/project pair."""
        ...


class PreferenceProvider(Protocol):
    """Provides aggregated user preferences derived from feedback."""

    async def get_preferences(
        self,
        user_id: object,
        project_id: object,
    ) -> PreferenceProfile:
        """Return the current preference profile for a user/project pair."""
        ...

    async def reset(self, user_id: object, project_id: object) -> None:
        """Clear stored preferences for a user/project pair."""
        ...


class MemoryFacade(Protocol):
    """Combined memory interface: feedback collection + preference retrieval.

    Implementations provide both feedback tracking and preference derivation
    in a single object, simplifying DI wiring at the service layer.
    """

    async def record(self, event: FeedbackEvent) -> None:
        """Persist a feedback event."""
        ...

    async def get_history(
        self,
        user_id: object,
        project_id: object,
        *,
        limit: int = 100,
    ) -> list[FeedbackEvent]:
        """Retrieve recent feedback events for a user/project pair."""
        ...

    async def get_preferences(
        self,
        user_id: object,
        project_id: object,
    ) -> PreferenceProfile:
        """Return the current preference profile for a user/project pair."""
        ...

    async def reset(self, user_id: object, project_id: object) -> None:
        """Clear stored preferences for a user/project pair."""
        ...
