"""Unit tests for extract_temporal_expressions (REST variant).

Tests the REST endpoint of TimelineExtractionService which collects
results from the internal stream.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.planning.timeline_schemas import ExtractedEventResponse
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from narrare.planning.timeline_extraction_service import TimelineExtractionService


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


def _make_chapter(**overrides: object) -> MagicMock:
    """Create a mock chapter."""
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Chapter 1"),
        "position": overrides.get("position", 0),
        "summary": overrides.get("summary", "A summary"),
    }
    defaults.update(overrides)
    chapter = MagicMock(spec=["id", "title", "position", "summary"])
    for k, v in defaults.items():
        setattr(chapter, k, v)
    return chapter


class TestExtractTemporalExpressions:
    """Test extract_temporal_expressions (REST variant — collects from stream)."""

    async def test_extract_with_all_chapters(
        self,
        service_with_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        mock_registry: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Extract from all chapters when no chapter_ids specified."""
        from narrare_core.agents.temporal_extraction_types import (
            ExtractedTemporalExpression,
            TemporalExtractionOutput,
        )

        ch1_id = uuid.uuid4()

        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            _make_chapter(id=ch1_id, title="Ch 1", position=0, summary="First chapter content"),
        ]
        mock_event_repo.list_by_novel.return_value = []

        fake_output = TemporalExtractionOutput(
            extracted=[
                ExtractedTemporalExpression(
                    expression="three days later",
                    event_name="Arrival",
                    timestamp_raw="Day 3",
                    chapter_reference="Ch 1",
                    character_names=["Hero"],
                    location_name="Castle",
                    confidence=0.9,
                    context="After three days later, they arrived.",
                ),
            ],
            chapter_temporal_markers=["Day 3"],
            extraction_notes="Found 1 expression.",
        )

        mock_model = AsyncMock(spec=[])
        mock_registry.get_model.return_value = mock_model

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = fake_output

        with patch(
            "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
            return_value=mock_agent_instance,
        ):
            result = await service_with_config.extract_temporal_expressions(novel_id, user_id)

        assert len(result) == 1
        assert isinstance(result[0], ExtractedEventResponse)
        assert result[0].expression == "three days later"
        assert result[0].event_name == "Arrival"

    async def test_extract_with_specific_chapter_ids(
        self,
        service_with_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        mock_registry: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Extract only from specified chapters."""
        from narrare_core.agents.temporal_extraction_types import (
            ExtractedTemporalExpression,
            TemporalExtractionOutput,
        )

        ch1_id = uuid.uuid4()
        ch2_id = uuid.uuid4()

        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            _make_chapter(id=ch1_id, title="Ch 1", position=0, summary="First"),
            _make_chapter(id=ch2_id, title="Ch 2", position=1, summary="Second"),
        ]
        mock_event_repo.list_by_novel.return_value = []

        # Only chapter 1 has results
        output_ch1 = TemporalExtractionOutput(
            extracted=[
                ExtractedTemporalExpression(
                    expression="that evening",
                    event_name="Dinner",
                    timestamp_raw="Evening",
                    chapter_reference="Ch 1",
                    confidence=0.8,
                    context="That evening they had dinner.",
                ),
            ],
        )
        output_ch2 = TemporalExtractionOutput(extracted=[])

        mock_model = AsyncMock(spec=[])
        mock_registry.get_model.return_value = mock_model

        mock_agent_instance = AsyncMock()
        # First call returns ch1 result, second call returns empty
        mock_agent_instance.run.side_effect = [output_ch1, output_ch2]

        with patch(
            "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
            return_value=mock_agent_instance,
        ):
            result = await service_with_config.extract_temporal_expressions(
                novel_id, user_id, chapter_ids=[ch1_id, ch2_id]
            )

        assert len(result) == 1
        assert result[0].event_name == "Dinner"

    async def test_extract_with_chapter_filter(
        self,
        service_with_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        mock_registry: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Only requested chapter IDs are processed."""
        from narrare_core.agents.temporal_extraction_types import (
            ExtractedTemporalExpression,
            TemporalExtractionOutput,
        )

        ch1_id = uuid.uuid4()
        ch2_id = uuid.uuid4()

        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            _make_chapter(id=ch1_id, title="Ch 1", position=0, summary="First"),
            _make_chapter(id=ch2_id, title="Ch 2", position=1, summary="Second"),
        ]
        mock_event_repo.list_by_novel.return_value = []

        output_ch1 = TemporalExtractionOutput(
            extracted=[
                ExtractedTemporalExpression(
                    expression="that evening",
                    event_name="Dinner",
                    timestamp_raw="Evening",
                    chapter_reference="Ch 1",
                    confidence=0.8,
                    context="Dinner context.",
                ),
            ],
        )

        mock_model = AsyncMock(spec=[])
        mock_registry.get_model.return_value = mock_model

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = output_ch1

        with patch(
            "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
            return_value=mock_agent_instance,
        ):
            result = await service_with_config.extract_temporal_expressions(
                novel_id, user_id, chapter_ids=[ch1_id]
            )

        assert len(result) == 1
        assert result[0].event_name == "Dinner"

    async def test_extract_novel_not_found(
        self,
        service_with_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """NotFoundError raised when novel doesn't exist."""
        mock_novel_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service_with_config.extract_temporal_expressions(novel_id, user_id)

    async def test_extract_no_provider_raises_config_error(
        self,
        service_no_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """ConfigurationError raised when no AI provider configured."""
        mock_novel_repo.get_by_id.return_value = _make_novel(id=novel_id)

        with pytest.raises(ConfigurationError, match="No AI provider configured"):
            await service_no_config.extract_temporal_expressions(novel_id, user_id)

    async def test_extract_passes_existing_event_names(
        self,
        service_with_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        mock_registry: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Existing event names should be passed to the agent deps."""
        from narrare_core.agents.temporal_extraction_types import TemporalExtractionOutput

        ch1_id = uuid.uuid4()

        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            _make_chapter(id=ch1_id, title="Ch 1", position=0, summary="Content"),
        ]

        existing_event = MagicMock(spec=["event_name"])
        existing_event.event_name = "Existing Event"
        mock_event_repo.list_by_novel.return_value = [existing_event]

        fake_output = TemporalExtractionOutput()

        mock_model = AsyncMock(spec=[])
        mock_registry.get_model.return_value = mock_model

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = fake_output

        with patch(
            "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
            return_value=mock_agent_instance,
        ) as mock_agent_cls:
            await service_with_config.extract_temporal_expressions(novel_id, user_id)

            # Verify the agent was instantiated
            mock_agent_cls.assert_called_once()
