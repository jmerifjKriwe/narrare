"""Unit tests for confirm_extracted_event in TimelineAnalysisService (PLAN-004 Phase 2).

Tests confirming extracted temporal expressions into persistent timeline events.

The §7 follow-up (extracted names → KB entity refs) lives in the sibling
``test_extraction_confirm_kb_refs.py``; shared value-container factories come
from ``_extraction_confirm_helpers``.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare_core.agents.temporal_extraction_types import ExtractedTemporalExpression
from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.unit.planning._extraction_confirm_helpers import make_event, make_novel
from tests.unit.planning._timeline_test_helpers import make_static_resolution


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_novel_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_chapter_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_event_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_registry() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service_with_config(
    mock_novel_repo: AsyncMock,
    mock_chapter_repo: AsyncMock,
    mock_registry: AsyncMock,
    mock_event_repo: AsyncMock,
) -> TimelineAnalysisService:
    """Service with a resolved model and event repo for confirm tests."""
    return TimelineAnalysisService(
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        model_registry=mock_registry,
        model_resolution=make_static_resolution(),
        event_repo=mock_event_repo,
    )


class TestConfirmExtractedEvent:
    """Test confirm_extracted_event method."""

    async def test_confirm_creates_event_with_source_extracted(
        self,
        service_with_config: TimelineAnalysisService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Confirmed event should be created with source='extracted'."""
        novel = make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel

        created_event = make_event(
            novel_id=novel_id,
            event_name="Arrival",
            source="extracted",
            confidence=0.9,
        )
        mock_event_repo.create.return_value = created_event

        extracted = ExtractedTemporalExpression(
            expression="three days later",
            event_name="Arrival",
            timestamp_raw="Day 3",
            chapter_reference="Ch 1",
            character_names=["Hero"],
            location_name="Castle",
            confidence=0.9,
            context="After three days later, they arrived.",
        )

        result = await service_with_config.confirm_extracted_event(novel_id, user_id, extracted)

        # Verify the result was returned
        assert result is not None

        # Verify create was called with source='extracted'
        call_kwargs = mock_event_repo.create.call_args
        assert call_kwargs.kwargs["source"] == "extracted"
        assert call_kwargs.kwargs["confidence"] == 0.9
        assert call_kwargs.kwargs["event_name"] == "Arrival"

    async def test_confirm_novel_not_found(
        self,
        service_with_config: TimelineAnalysisService,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """NotFoundError raised when novel doesn't exist."""
        mock_novel_repo.get_by_id.return_value = None

        extracted = ExtractedTemporalExpression(
            expression="test",
            event_name="Test Event",
            confidence=0.5,
        )

        with pytest.raises(NotFoundError):
            await service_with_config.confirm_extracted_event(novel_id, user_id, extracted)

    async def test_confirm_without_event_repo_raises(
        self,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
    ) -> None:
        """ConfigurationError raised when no event_repo is available."""
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_resolution=make_static_resolution(),
            event_repo=None,  # No event repo
        )

        extracted = ExtractedTemporalExpression(
            expression="test",
            event_name="Test Event",
            confidence=0.5,
        )

        with pytest.raises(ConfigurationError, match="Event repository not available"):
            await service.confirm_extracted_event(novel_id, user_id, extracted)

    async def test_confirm_uses_expression_as_fallback_name(
        self,
        service_with_config: TimelineAnalysisService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """When event_name is empty, expression should be used as fallback."""
        novel = make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel

        created_event = make_event(
            novel_id=novel_id,
            event_name="three days later",  # fallback from expression
            source="extracted",
            confidence=0.7,
        )
        mock_event_repo.create.return_value = created_event

        extracted = ExtractedTemporalExpression(
            expression="three days later",
            event_name="",  # Empty event_name
            confidence=0.7,
        )

        await service_with_config.confirm_extracted_event(novel_id, user_id, extracted)

        call_kwargs = mock_event_repo.create.call_args
        # Should use expression as fallback when event_name is empty
        assert call_kwargs.kwargs["event_name"] == "three days later"
