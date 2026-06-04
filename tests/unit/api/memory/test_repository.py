"""Unit tests for memory repository — FeedbackRepository and PreferenceProfileRepository."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from narrare.memory.models import FeedbackEventModel, PreferenceProfileModel


class FakeScalars:
    """Fake SQLAlchemy Scalars result wrapper."""

    def __init__(self, items: list[Any] | None = None) -> None:
        self._items = items if items is not None else []

    def all(self) -> list[Any]:
        return self._items


class FakeResult:
    """Fake SQLAlchemy Result returned by FakeAsyncSession.execute().

    Provides the same interface as SQLAlchemy's ``Result`` object
    (``scalar_one_or_none``, ``scalars``, ``scalar``) without requiring
    a real database connection.
    """

    def __init__(
        self,
        *,
        scalar_one: Any | None = None,
        scalars: list[Any] | None = None,
        scalar_value: Any = 0,
    ) -> None:
        self._scalar_one = scalar_one
        self._scalars = FakeScalars(scalars)
        self._scalar_value = scalar_value

    def scalar_one_or_none(self) -> Any | None:
        return self._scalar_one

    def scalars(self) -> FakeScalars:
        return self._scalars

    def scalar(self) -> Any:
        return self._scalar_value


class FakeAsyncSession:
    """Minimal fake async session for unit testing repositories."""

    def __init__(self) -> None:
        self._data: list[Any] = []
        self._flushed: list[Any] = []

    def add(self, entity: Any) -> None:
        self._data.append(entity)

    async def flush(self) -> None:
        self._flushed.extend(self._data)

    async def refresh(self, entity: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> FakeResult:
        return FakeResult()

    async def delete(self, entity: Any) -> None:
        if entity in self._data:
            self._data.remove(entity)


class TestFeedbackRepository:
    def setup_method(self) -> None:
        from narrare.memory.repository import FeedbackRepository

        self.session = FakeAsyncSession()
        self.repo = FeedbackRepository(self.session)  # type: ignore[arg-type]

    async def test_create_persists_event(self) -> None:
        event = FeedbackEventModel(
            user_id=uuid4(),
            project_id=uuid4(),
            suggestion_id=uuid4(),
            action="accept",
            intent="write",
            suggestion_text="Some text",
        )
        result = await self.repo.create(event)
        assert result in self.session._data

    async def test_create_with_rating(self) -> None:
        event = FeedbackEventModel(
            user_id=uuid4(),
            project_id=uuid4(),
            suggestion_id=uuid4(),
            action="accept",
            intent="write",
            suggestion_text="Some text",
            rating=4,
        )
        result = await self.repo.create(event)
        assert result.rating == 4


class TestPreferenceProfileRepository:
    def setup_method(self) -> None:
        from narrare.memory.repository import PreferenceProfileRepository

        self.session = FakeAsyncSession()
        self.repo = PreferenceProfileRepository(self.session)  # type: ignore[arg-type]

    async def test_upsert_new_profile(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        profile = PreferenceProfileModel(
            user_id=user_id,
            project_id=project_id,
            style_patterns=["concise sentences"],
            content_patterns=["dialogue-heavy"],
            avoidance_patterns=["cliffhangers"],
            confidence=0.8,
            summary="User prefers concise dialogue.",
            event_count_at_analysis=10,
        )
        result = await self.repo.upsert(profile)
        assert result in self.session._data

    async def test_get_returns_none_when_not_found(self) -> None:
        result = await self.repo.get(uuid4(), uuid4())
        assert result is None
