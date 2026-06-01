"""Unit tests for TimelineEventRepository.

Tests CRUD operations with a fake async session. Follows the repository
pattern established in the codebase: all SQLAlchemy queries live in the
repository, services never write SQL.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.planning.models import TimelineEvent
from narrare.planning.timeline_repository import TimelineEventRepository


class FakeTimelineEvent:
    """Fake TimelineEvent that bypasses SQLAlchemy instrumentation."""

    def __init__(self, **overrides: object) -> None:
        import uuid
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        defaults: dict[str, object] = {
            "id": uuid.uuid4(),
            "novel_id": uuid.uuid4(),
            "event_name": "Test Event",
            "description": "A test event",
            "event_type": "plot_point",
            "timestamp_raw": "Day 1",
            "timestamp_normalized": "Day 1",
            "temporal_order": 1,
            "chapter_id": None,
            "character_refs": [],
            "location_ref": None,
            "causes": "",
            "consequences": "",
            "source": "manual",
            "confidence": None,
            "is_confirmed": True,
            "created_at": now,
            "updated_at": now,
        }
        defaults.update(overrides)
        for k, v in defaults.items():
            setattr(self, k, v)


class FakeScalarResult:
    """Fake SQLAlchemy scalar result for testing."""

    def __init__(self, items: list[FakeTimelineEvent] | None = None, single: object = None) -> None:
        self._items = items
        self._single = single

    def scalar_one_or_none(self) -> object:
        return self._single

    def scalars(self) -> list[FakeTimelineEvent]:
        return self._items if self._items is not None else []  # type: ignore[return-value]


class FakeRowcountResult:
    """Fake delete result with rowcount."""

    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    # session.add() is synchronous — override the auto-async mock
    session.add = MagicMock(spec=[])
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> TimelineEventRepository:
    """Create a TimelineEventRepository with mock session."""
    return TimelineEventRepository(mock_session)


class TestGetById:
    async def test_get_by_id_returns_event_when_found(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        event_id = uuid.uuid4()
        event = FakeTimelineEvent(id=event_id)
        mock_session.execute.return_value = FakeScalarResult(single=event)

        result = await repo.get_by_id(event_id)

        assert result is not None
        assert result.id == event_id
        mock_session.execute.assert_awaited_once()

    async def test_get_by_id_returns_none_when_not_found(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        mock_session.execute.return_value = FakeScalarResult(single=None)

        result = await repo.get_by_id(uuid.uuid4())

        assert result is None


class TestListByNovel:
    async def test_list_by_novel_returns_ordered_events(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        novel_id = uuid.uuid4()
        events = [FakeTimelineEvent(novel_id=novel_id, temporal_order=i) for i in range(3)]
        mock_session.execute.return_value = FakeScalarResult(items=events)

        result = await repo.list_by_novel(novel_id)

        assert len(result) == 3
        mock_session.execute.assert_awaited_once()

    async def test_list_by_novel_with_event_type_filter(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        novel_id = uuid.uuid4()
        mock_session.execute.return_value = FakeScalarResult(items=[])

        await repo.list_by_novel(novel_id, event_type="plot_point")

        mock_session.execute.assert_awaited_once()

    async def test_list_by_novel_with_multiple_filters(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        novel_id = uuid.uuid4()
        mock_session.execute.return_value = FakeScalarResult(items=[])

        await repo.list_by_novel(
            novel_id, event_type="plot_point", source="manual", is_confirmed=True
        )

        mock_session.execute.assert_awaited_once()


class TestCreate:
    async def test_create_event_with_all_fields(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        novel_id = uuid.uuid4()

        with patch.object(repo, "_flush_and_refresh", new_callable=AsyncMock) as mock_fr:
            result = await repo.create(
                novel_id=novel_id,
                event_name="Battle of Helm",
                description="The great battle",
                event_type="battle",
                timestamp_raw="Day 15",
                source="manual",
                is_confirmed=True,
            )

        assert isinstance(result, TimelineEvent)
        mock_session.add.assert_called_once()
        mock_fr.assert_awaited_once()


class TestUpdate:
    async def test_update_existing_event(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        event_id = uuid.uuid4()
        event = FakeTimelineEvent(id=event_id, event_name="Old Name")

        with (
            patch.object(repo, "get_by_id", new_callable=AsyncMock, return_value=event),
            patch.object(repo, "_flush_and_refresh", new_callable=AsyncMock),
        ):
            result = await repo.update(event_id, event_name="New Name")

        assert isinstance(result, FakeTimelineEvent)

    async def test_update_nonexistent_event_raises_not_found(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        event_id = uuid.uuid4()

        with patch.object(repo, "get_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(Exception) as exc_info:
                await repo.update(event_id, event_name="New Name")
            assert "TimelineEvent" in str(exc_info.value)


class TestDelete:
    async def test_delete_existing_event_returns_true(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        mock_session.execute.return_value = FakeRowcountResult(rowcount=1)
        mock_session.flush = AsyncMock()

        result = await repo.delete(uuid.uuid4())

        assert result is True

    async def test_delete_nonexistent_event_returns_false(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        mock_session.execute.return_value = FakeRowcountResult(rowcount=0)
        mock_session.flush = AsyncMock()

        result = await repo.delete(uuid.uuid4())

        assert result is False


class TestBulkCreate:
    async def test_bulk_create_multiple_events(
        self, repo: TimelineEventRepository, mock_session: AsyncMock
    ) -> None:
        novel_id = uuid.uuid4()
        events_data: list[dict[str, object]] = [
            {"novel_id": novel_id, "event_name": f"Event {i}", "source": "manual"} for i in range(3)
        ]

        with (
            patch.object(repo, "_flush", new_callable=AsyncMock) as mock_flush,
            patch.object(repo, "_session") as mock_sess,
        ):
            mock_sess.add = MagicMock(spec=[])  # sync method
            mock_sess.refresh = AsyncMock()

            result = await repo.bulk_create(events_data)

        assert len(result) == 3
        assert mock_sess.add.call_count == 3
        assert mock_sess.refresh.call_count == 3
        mock_flush.assert_awaited_once()
