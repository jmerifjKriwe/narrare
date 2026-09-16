"""Unit tests for TimelineConsistencyService — deterministic checks (PLAN-004 Phase 2).

Tests deterministic checks integration and NotFoundError when novel doesn't exist.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.planning.timeline_consistency_service import TimelineConsistencyService
from narrare_core.shared.errors import NotFoundError


def _make_novel(**overrides: object) -> MagicMock:
    """Create a mock novel."""
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=["id", "title", "genre", "writing_language"])
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def _make_event(**overrides: object) -> MagicMock:
    """Create a mock TimelineEvent."""
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "event_name": overrides.get("event_name", "Battle"),
        "event_type": overrides.get("event_type", "plot_point"),
        "temporal_order": overrides.get("temporal_order", 1),
        "causes": overrides.get("causes", ""),
        "consequences": overrides.get("consequences", ""),
        "timestamp_raw": overrides.get("timestamp_raw", "Day 1"),
        "timestamp_normalized": overrides.get("timestamp_normalized", ""),
        "chapter_id": overrides.get("chapter_id"),
        "character_refs": overrides.get("character_refs", []),
        "location_ref": overrides.get("location_ref"),
    }
    defaults.update(overrides)
    event = MagicMock(
        spec=[
            "id",
            "event_name",
            "event_type",
            "temporal_order",
            "causes",
            "consequences",
            "timestamp_raw",
            "timestamp_normalized",
            "chapter_id",
            "character_refs",
            "location_ref",
        ]
    )
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
def service(
    mock_event_repo: AsyncMock,
    mock_novel_repo: AsyncMock,
) -> TimelineConsistencyService:
    """Service without LLM (deterministic-only mode — no resolution wired,
    ADR-086 L23: the lazy resolve only runs when a cascade is injected)."""
    return TimelineConsistencyService(
        event_repo=mock_event_repo,
        novel_repo=mock_novel_repo,
        model_registry=None,
    )


class TestDeterministicChecks:
    """Test deterministic checks integration."""

    async def test_check_consistency_with_no_events(
        self,
        service: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Empty event list should produce no issues and pass."""
        mock_novel_repo.get_by_id.return_value = _make_novel(id=novel_id)
        mock_event_repo.list_by_novel.return_value = []

        result = await service.check_consistency(novel_id, user_id)

        assert result.deterministic_pass is True
        assert len(result.issues) == 0
        assert "No temporal issues" in result.overall_assessment

    async def test_check_consistency_with_valid_events(
        self,
        service: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Events with unique temporal_order should pass deterministic checks."""
        mock_novel_repo.get_by_id.return_value = _make_novel(id=novel_id)
        mock_event_repo.list_by_novel.return_value = [
            _make_event(event_name="Event A", temporal_order=1, timestamp_raw="Day 1"),
            _make_event(event_name="Event B", temporal_order=2, timestamp_raw="Day 2"),
        ]

        result = await service.check_consistency(novel_id, user_id)

        assert result.deterministic_pass is True

    async def test_check_consistency_detects_duplicate_temporal_order(
        self,
        service: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Events sharing temporal_order should produce a warning."""
        mock_novel_repo.get_by_id.return_value = _make_novel(id=novel_id)
        mock_event_repo.list_by_novel.return_value = [
            _make_event(event_name="Event A", temporal_order=1, timestamp_raw="Day 1"),
            _make_event(event_name="Event B", temporal_order=1, timestamp_raw="Day 2"),
        ]

        result = await service.check_consistency(novel_id, user_id)

        assert result.deterministic_pass is True  # warnings, not errors
        duplicate_issues = [i for i in result.issues if i.rule_id == "duplicate_temporal_order"]
        assert len(duplicate_issues) == 1

    async def test_check_consistency_detects_missing_temporal_order(
        self,
        service: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Events without temporal_order should produce an info issue."""
        mock_novel_repo.get_by_id.return_value = _make_novel(id=novel_id)
        mock_event_repo.list_by_novel.return_value = [
            _make_event(event_name="Event A", temporal_order=None),
        ]

        result = await service.check_consistency(novel_id, user_id)

        missing_issues = [i for i in result.issues if i.rule_id == "missing_temporal_order"]
        assert len(missing_issues) == 1
        assert missing_issues[0].severity == "info"

    async def test_check_consistency_novel_not_found(
        self,
        service: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """NotFoundError raised when novel doesn't exist."""
        mock_novel_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.check_consistency(novel_id, user_id)

    async def test_assessment_reflects_warnings(
        self,
        service: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Overall assessment should reflect the severity of issues found."""
        mock_novel_repo.get_by_id.return_value = _make_novel(id=novel_id)
        # Events with duplicate temporal_order produce warnings
        mock_event_repo.list_by_novel.return_value = [
            _make_event(event_name="A", temporal_order=1, timestamp_raw="Day 1"),
            _make_event(event_name="B", temporal_order=1, timestamp_raw="Day 1"),
        ]

        result = await service.check_consistency(novel_id, user_id)

        # Should mention warnings
        assert "warning" in result.overall_assessment.lower()
