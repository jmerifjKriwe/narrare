"""Fake user-providers repository for unit tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

from tests.fakes._shared import CallRecord


class FakeUserProvidersRepository:
    """In-memory fake for UserProvidersCountProtocol.

    Supports ``count_by_user()`` for testing provider-existence checks.
    """

    def __init__(self) -> None:
        self._counts: dict[uuid.UUID, int] = {}
        self.calls: list[CallRecord] = []

    def seed_count(self, user_id: uuid.UUID, count: int) -> None:
        """Pre-set the provider count for a user."""
        self._counts[user_id] = count

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        self.calls.append(CallRecord("count_by_user", kwargs={"user_id": user_id}))
        return self._counts.get(user_id, 0)
