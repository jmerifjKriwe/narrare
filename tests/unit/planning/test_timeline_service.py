"""Unit tests for TimelineService (CRUD) — create and list operations.

Tests the service layer with a fake repository and novel repository.
Verifies ownership checks, chapter validation, and proper delegation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from narrare.novels.models import Novel
from narrare.planning.models import TimelineEvent
from narrare.planning.timeline_schemas import (
    TimelineEventCreateRequest,
    TimelineEventCRUDResponse,
)
from narrare.planning.timeline_service import TimelineService
from narrare_core.shared.errors import NotFoundError


def _make_novel_mock(**overrides: object) -> AsyncMock:
    """Create a mock novel with Novel spec."""
    novel = AsyncMock(spec=Novel)
    novel.id = overrides.get("id", uuid.uuid4())
    novel.title = overrides.get("title", "Test Novel")
    return novel


def _make_event_orm(**overrides: object) -> AsyncMock:
    """Create a mock TimelineEvent ORM object."""
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


class TestCreateEvent:
    async def test_create_event_with_valid_request_returns_response(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        mock_novel_repo.get_by_id.return_value = _make_novel_mock(id=novel_id)
        created = _make_event_orm(novel_id=novel_id, event_name="Battle")
        mock_event_repo.create.return_value = created

        request = TimelineEventCreateRequest(
            event_name="Battle",
            description="The great battle",
        )
        result = await service.create_event(novel_id, user_id, request)

        assert isinstance(result, TimelineEventCRUDResponse)
        assert result.event_name == "Battle"
        mock_event_repo.create.assert_awaited_once()

    async def test_create_event_nonexistent_novel_raises_not_found(
        self,
        service: TimelineService,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        mock_novel_repo.get_by_id.return_value = None

        request = TimelineEventCreateRequest(event_name="Battle")
        with pytest.raises(NotFoundError):
            await service.create_event(novel_id, user_id, request)

    async def test_create_event_invalid_chapter_raises_not_found(
        self,
        service: TimelineService,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        mock_novel_repo.get_by_id.return_value = _make_novel_mock(id=novel_id)
        mock_chapter_repo.get_by_id.return_value = None

        chapter_id = uuid.uuid4()
        request = TimelineEventCreateRequest(event_name="Battle", chapter_id=chapter_id)
        with pytest.raises(NotFoundError):
            await service.create_event(novel_id, user_id, request)

    async def test_create_event_with_character_refs(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        mock_novel_repo.get_by_id.return_value = _make_novel_mock(id=novel_id)
        created = _make_event_orm(novel_id=novel_id)
        mock_event_repo.create.return_value = created

        request = TimelineEventCreateRequest(
            event_name="Meeting",
            character_refs=[{"id": str(uuid.uuid4()), "name": "John"}],
        )
        result = await service.create_event(novel_id, user_id, request)

        assert isinstance(result, TimelineEventCRUDResponse)
        call_kwargs = mock_event_repo.create.call_args[1]
        assert len(call_kwargs["character_refs"]) == 1


class TestListEvents:
    async def test_list_events_returns_all_for_novel(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        mock_novel_repo.get_by_id.return_value = _make_novel_mock(id=novel_id)
        events = [_make_event_orm(novel_id=novel_id) for _ in range(3)]
        mock_event_repo.list_by_novel.return_value = events

        result = await service.list_events(novel_id, user_id)

        assert len(result) == 3
        assert all(isinstance(r, TimelineEventCRUDResponse) for r in result)

    async def test_list_events_with_filters(
        self,
        service: TimelineService,
        mock_event_repo: AsyncMock,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        mock_novel_repo.get_by_id.return_value = _make_novel_mock(id=novel_id)
        mock_event_repo.list_by_novel.return_value = []

        result = await service.list_events(novel_id, user_id, event_type="battle", source="manual")

        assert result == []
        mock_event_repo.list_by_novel.assert_awaited_once()

    async def test_list_events_nonexistent_novel_raises_not_found(
        self,
        service: TimelineService,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        mock_novel_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.list_events(novel_id, user_id)
