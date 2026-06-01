"""Unit tests for TimelineService (CRUD) — get, update, delete operations.

Split from test_timeline_service.py to respect the 300-line file limit (RULE-04).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from narrare.novels.models import Novel
from narrare.planning.models import TimelineEvent
from narrare.planning.timeline_schemas import (
    TimelineEventCRUDResponse,
    TimelineEventUpdateRequest,
)
from narrare.planning.timeline_service import TimelineService
from narrare_core.shared.errors import NotFoundError


def _make_novel_mock(**overrides: object) -> AsyncMock:
    """Create a mock novel with Novel spec."""
    novel = AsyncMock(spec=Novel)
    novel.id = overrides.get("id", uuid.uuid4())
    return novel


def _make_event_orm(**overrides: object) -> AsyncMock:
    """Create a mock TimelineEvent ORM object."""
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "novel_id": uuid.uuid4(),
        "event_name": "Test Event",
        "description": "",
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
    event = AsyncMock(spec=TimelineEvent)
    for k, v in defaults.items():
        setattr(event, k, v)
    return event


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_event_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_novel_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_chapter_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_event_repo: AsyncMock,
    mock_novel_repo: AsyncMock,
    mock_chapter_repo: AsyncMock,
) -> TimelineService:
    return TimelineService(
        event_repo=mock_event_repo,
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
    )


class TestGetEvent:
    async def test_get_event_returns_response(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        event = _make_event_orm(novel_id=novel_id)
        mock_event_repo.get_by_id.return_value = event
        mock_novel_repo.get_by_id.return_value = _make_novel_mock(id=novel_id)

        result = await service.get_event(event.id, user_id)

        assert isinstance(result, TimelineEventCRUDResponse)

    async def test_get_event_nonexistent_raises_not_found(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_event_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.get_event(uuid.uuid4(), user_id)


class TestUpdateEvent:
    async def test_update_event_changes_specified_fields(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        event = _make_event_orm(novel_id=novel_id, event_name="Old Name")
        mock_event_repo.get_by_id.return_value = event
        mock_novel_repo.get_by_id.return_value = _make_novel_mock(id=novel_id)

        updated = _make_event_orm(novel_id=novel_id, event_name="New Name")
        mock_event_repo.update.return_value = updated

        request = TimelineEventUpdateRequest(event_name="New Name")
        result = await service.update_event(event.id, user_id, request)

        assert isinstance(result, TimelineEventCRUDResponse)
        mock_event_repo.update.assert_awaited_once()

    async def test_update_event_nonexistent_raises_not_found(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_event_repo.get_by_id.return_value = None

        request = TimelineEventUpdateRequest(event_name="New Name")
        with pytest.raises(NotFoundError):
            await service.update_event(uuid.uuid4(), user_id, request)


class TestDeleteEvent:
    async def test_delete_existing_event_returns_true(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        event = _make_event_orm(novel_id=novel_id)
        mock_event_repo.get_by_id.return_value = event
        mock_novel_repo.get_by_id.return_value = _make_novel_mock(id=novel_id)
        mock_event_repo.delete.return_value = True

        result = await service.delete_event(event.id, user_id)

        assert result is True
        mock_event_repo.delete.assert_awaited_once_with(event.id)

    async def test_delete_nonexistent_event_returns_false(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        mock_event_repo.get_by_id.return_value = None

        result = await service.delete_event(uuid.uuid4(), user_id)

        assert result is False

    async def test_delete_event_wrong_owner_raises_not_found(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        event = _make_event_orm(novel_id=uuid.uuid4())
        mock_event_repo.get_by_id.return_value = event
        mock_novel_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.delete_event(event.id, user_id)
