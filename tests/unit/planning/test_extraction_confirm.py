"""Unit tests for confirm_extracted_event in TimelineAnalysisService (PLAN-004 Phase 2).

Tests confirming extracted temporal expressions into persistent timeline events.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare_core.agents.temporal_extraction_types import ExtractedTemporalExpression
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.shared.errors import ConfigurationError, NotFoundError


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
        "novel_id": overrides.get("novel_id", uuid.uuid4()),
        "event_name": overrides.get("event_name", "Battle"),
        "description": overrides.get("description", ""),
        "event_type": overrides.get("event_type", "plot_point"),
        "timestamp_raw": overrides.get("timestamp_raw", "Day 1"),
        "timestamp_normalized": overrides.get("timestamp_normalized", ""),
        "temporal_order": overrides.get("temporal_order", 1),
        "chapter_id": overrides.get("chapter_id"),
        "character_refs": overrides.get("character_refs", []),
        "location_ref": overrides.get("location_ref"),
        "causes": overrides.get("causes", ""),
        "consequences": overrides.get("consequences", ""),
        "source": overrides.get("source", "manual"),
        "confidence": overrides.get("confidence"),
        "is_confirmed": overrides.get("is_confirmed", True),
        "created_at": overrides.get("created_at", "2025-01-01T00:00:00Z"),
        "updated_at": overrides.get("updated_at", "2025-01-01T00:00:00Z"),
    }
    defaults.update(overrides)
    event = MagicMock(
        spec=[
            "id",
            "novel_id",
            "event_name",
            "description",
            "event_type",
            "timestamp_raw",
            "timestamp_normalized",
            "temporal_order",
            "chapter_id",
            "character_refs",
            "location_ref",
            "causes",
            "consequences",
            "source",
            "confidence",
            "is_confirmed",
            "created_at",
            "updated_at",
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
def model_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


@pytest.fixture
def service_with_config(
    mock_novel_repo: AsyncMock,
    mock_chapter_repo: AsyncMock,
    mock_registry: AsyncMock,
    mock_event_repo: AsyncMock,
    model_config: ResolvedModelConfig,
) -> TimelineAnalysisService:
    """Service with model config and event repo for confirm tests."""
    return TimelineAnalysisService(
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        model_registry=mock_registry,
        model_config=model_config,
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
        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel

        created_event = _make_event(
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
        model_config: ResolvedModelConfig,
    ) -> None:
        """ConfigurationError raised when no event_repo is available."""
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_config=model_config,
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
        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel

        created_event = _make_event(
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
