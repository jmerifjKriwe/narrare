"""Fake memory repository implementations for unit tests.

Provides:
    - ``FakeFeedbackRepository`` — in-memory fake for ``FeedbackRepositoryProtocol``
    - ``FakePreferenceProfileRepository`` — in-memory fake for
      ``PreferenceProfileRepositoryProtocol``

Usage:
    fake_repo = FakeFeedbackRepository()
    fake_repo.seed_count(user_id, project_id, count=10)

    # Or seed actual events:
    fake_repo.seed(event1, event2)
"""

from __future__ import annotations

import uuid
from typing import Any

from narrare.memory.models import FeedbackEventModel, PreferenceProfileModel
from tests.fakes._shared import CallRecord


class FakeFeedbackRepository:
    """In-memory fake for FeedbackRepositoryProtocol.

    Supports seeding event counts and actual events for analysis tests.
    All methods track calls via ``self.calls``.
    """

    def __init__(self) -> None:
        self._events: list[FeedbackEventModel] = []
        self._count_overrides: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *events: FeedbackEventModel) -> None:
        """Pre-populate the store with feedback events."""
        self._events.extend(events)

    def seed_count(self, user_id: uuid.UUID, project_id: uuid.UUID, *, count: int) -> None:
        """Override the event count for a user/project pair.

        Useful for testing the analysis threshold without creating
        many event objects.
        """
        self._count_overrides[(user_id, project_id)] = count
        # Also ensure _events reflect the count for get_events_batch
        if count > len(
            [e for e in self._events if e.user_id == user_id and e.project_id == project_id]
        ):
            # Create minimal events to match the count
            existing = [
                e for e in self._events if e.user_id == user_id and e.project_id == project_id
            ]
            needed = count - len(existing)
            for _ in range(needed):
                event = FeedbackEventModel(
                    user_id=user_id,
                    project_id=project_id,
                    suggestion_id=uuid.uuid4(),
                    action="accept",
                    intent="write",
                    suggestion_text="Seeded event.",
                )
                self._events.append(event)

    async def create(self, event: FeedbackEventModel) -> FeedbackEventModel:
        """Persist a feedback event."""
        self.calls.append(CallRecord("create", kwargs={"event": event}))
        self._events.append(event)
        return event

    async def get_event_count(self, user_id: uuid.UUID, project_id: uuid.UUID) -> int:
        """Count feedback events for a user/project pair."""
        self.calls.append(
            CallRecord("get_event_count", kwargs={"user_id": user_id, "project_id": project_id})
        )
        # Check for override first
        if (user_id, project_id) in self._count_overrides:
            return self._count_overrides[(user_id, project_id)]
        return len([e for e in self._events if e.user_id == user_id and e.project_id == project_id])

    async def get_events_batch(
        self, user_id: uuid.UUID, project_id: uuid.UUID, *, limit: int = 50
    ) -> list[FeedbackEventModel]:
        """Retrieve recent feedback events for agent analysis."""
        self.calls.append(
            CallRecord(
                "get_events_batch",
                kwargs={"user_id": user_id, "project_id": project_id, "limit": limit},
            )
        )
        matching = [e for e in self._events if e.user_id == user_id and e.project_id == project_id]
        return matching[:limit]

    async def list_by_user_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID, *, limit: int = 100
    ) -> list[FeedbackEventModel]:
        """Retrieve recent feedback events for a user/project pair."""
        self.calls.append(
            CallRecord(
                "list_by_user_project",
                kwargs={"user_id": user_id, "project_id": project_id, "limit": limit},
            )
        )
        matching = [e for e in self._events if e.user_id == user_id and e.project_id == project_id]
        return matching[:limit]

    async def delete_by_user_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> int:
        """Delete all feedback events for a user/project pair. Returns count deleted."""
        self.calls.append(
            CallRecord(
                "delete_by_user_project", kwargs={"user_id": user_id, "project_id": project_id}
            )
        )
        before = len(self._events)
        self._events = [
            e for e in self._events if not (e.user_id == user_id and e.project_id == project_id)
        ]
        # Clear count override too
        self._count_overrides.pop((user_id, project_id), None)
        return before - len(self._events)

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def call_count(self, method: str) -> int:
        """Count how many times a method was called."""
        return sum(1 for c in self.calls if c.method == method)

    def assert_called(self, method: str, **kwargs: Any) -> None:
        """Assert that a method was called with the given kwargs."""
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")

    def assert_called_once(self, method: str) -> None:
        """Assert a method was called exactly once."""
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def assert_not_called(self, method: str) -> None:
        """Assert a method was never called."""
        count = self.call_count(method)
        if count > 0:
            raise AssertionError(f"Expected 0 calls to {method}, got {count}")


class FakePreferenceProfileRepository:
    """In-memory fake for PreferenceProfileRepositoryProtocol.

    Supports seeding profiles and call tracking.
    """

    def __init__(self) -> None:
        self._profiles: dict[tuple[uuid.UUID, uuid.UUID], PreferenceProfileModel] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *profiles: PreferenceProfileModel) -> None:
        """Pre-populate the store with profiles."""
        for p in profiles:
            self._profiles[(p.user_id, p.project_id)] = p

    async def upsert(self, profile: PreferenceProfileModel) -> PreferenceProfileModel:
        """Insert or update a preference profile."""
        self.calls.append(CallRecord("upsert", kwargs={"profile": profile}))
        key = (profile.user_id, profile.project_id)
        if key in self._profiles:
            existing = self._profiles[key]
            # Update fields like the real repo does
            for field_name in (
                "style_patterns",
                "content_patterns",
                "avoidance_patterns",
                "confidence",
                "summary",
                "event_count_at_analysis",
            ):
                setattr(existing, field_name, getattr(profile, field_name))
            return existing

        # Simulate DB server defaults for new inserts.
        # SQLAlchemy models typed as Mapped[datetime] can be None at runtime
        # before a DB flush — this Fake simulates the DB's server_default.
        from datetime import UTC, datetime

        if not profile.id:
            profile.id = uuid.uuid4()
        if not profile.created_at:  # type: ignore[truthy-bool]
            profile.created_at = datetime.now(UTC)  # type: ignore[assignment]
        if not profile.updated_at:  # type: ignore[truthy-bool]
            profile.updated_at = datetime.now(UTC)  # type: ignore[assignment]
        self._profiles[key] = profile
        return profile

    async def get(self, user_id: uuid.UUID, project_id: uuid.UUID) -> PreferenceProfileModel | None:
        """Get a preference profile by user/project pair."""
        self.calls.append(CallRecord("get", kwargs={"user_id": user_id, "project_id": project_id}))
        return self._profiles.get((user_id, project_id))

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def call_count(self, method: str) -> int:
        """Count how many times a method was called."""
        return sum(1 for c in self.calls if c.method == method)

    def assert_called(self, method: str, **kwargs: Any) -> None:
        """Assert that a method was called with the given kwargs."""
        for call in self.calls:
            if call.method == method and call.matches(kwargs):
                return
        raise AssertionError(f"No call to {method} with {kwargs}")

    def assert_called_once(self, method: str) -> None:
        """Assert a method was called exactly once."""
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def assert_not_called(self, method: str) -> None:
        """Assert a method was never called."""
        count = self.call_count(method)
        if count > 0:
            raise AssertionError(f"Expected 0 calls to {method}, got {count}")
