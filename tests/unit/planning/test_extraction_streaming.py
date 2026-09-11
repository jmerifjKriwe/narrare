"""Unit tests for stream_extraction (SSE variant) in TimelineExtractionService.

Tests the async generator that yields ExtractedEventResponse per chapter.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.planning.timeline_schemas import ExtractedEventResponse
from narrare_core.shared.errors import NotFoundError

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


class TestStreamExtraction:
    """Test stream_extraction async generator directly."""

    async def test_stream_yields_per_chapter(
        self,
        service_with_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """stream_extraction yields ExtractedEventResponse per chapter."""
        from narrare_core.agents.temporal_extraction_types import (
            ExtractedTemporalExpression,
            TemporalExtractionOutput,
        )

        ch1_id = uuid.uuid4()

        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            _make_chapter(id=ch1_id, title="Ch 1", position=0, summary="Content"),
        ]

        fake_output = TemporalExtractionOutput(
            extracted=[
                ExtractedTemporalExpression(expression="day 1", event_name="Start"),
                ExtractedTemporalExpression(expression="day 2", event_name="Middle"),
            ],
        )

        mock_model = AsyncMock(spec=[])
        # Task-6b-2: model resolution flows through the prepare() assembly point.
        mock_registry.prepare.return_value = SimpleNamespace(
            model=mock_model, model_settings=None, usage_limits=None
        )

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = fake_output

        with patch(
            "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
            return_value=mock_agent_instance,
        ):
            results: list[ExtractedEventResponse] = []
            async for event in service_with_config.stream_extraction(
                novel_id, user_id, chapter_ids=None
            ):
                results.append(event)

        assert len(results) == 2
        assert all(isinstance(r, ExtractedEventResponse) for r in results)
        assert results[0].event_name == "Start"
        assert results[1].event_name == "Middle"

    async def test_stream_skips_empty_chapters(
        self,
        service_with_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Chapters with empty summary should be skipped."""
        ch1_id = uuid.uuid4()

        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            _make_chapter(id=ch1_id, title="Empty Ch", position=0, summary=""),
        ]

        mock_model = AsyncMock(spec=[])
        # Task-6b-2: model resolution flows through the prepare() assembly point.
        mock_registry.prepare.return_value = SimpleNamespace(
            model=mock_model, model_settings=None, usage_limits=None
        )

        mock_agent_instance = AsyncMock()
        with patch(
            "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
            return_value=mock_agent_instance,
        ):
            results: list[ExtractedEventResponse] = []
            async for event in service_with_config.stream_extraction(
                novel_id, user_id, chapter_ids=None
            ):
                results.append(event)

        assert len(results) == 0
        # Agent should NOT be called for empty chapters. Task-6b-2 note: the
        # stateless agent wrapper is now constructed once before the loop
        # (loop-invariant model + system prompt); the preserved contract is
        # that empty chapters never reach agent.run() and yield nothing.
        mock_agent_instance.run.assert_not_called()

    async def test_stream_handles_chapter_failure_gracefully(
        self,
        service_with_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Agent failure on one chapter should not stop the stream."""
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

        output_ch2 = TemporalExtractionOutput(
            extracted=[
                ExtractedTemporalExpression(expression="later", event_name="Later Event"),
            ],
        )

        mock_model = AsyncMock(spec=[])
        # Task-6b-2: model resolution flows through the prepare() assembly point.
        mock_registry.prepare.return_value = SimpleNamespace(
            model=mock_model, model_settings=None, usage_limits=None
        )

        # First call raises, second succeeds
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.side_effect = [RuntimeError("Agent failed"), output_ch2]

        with patch(
            "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
            return_value=mock_agent_instance,
        ):
            results: list[ExtractedEventResponse] = []
            async for event in service_with_config.stream_extraction(
                novel_id, user_id, chapter_ids=None
            ):
                results.append(event)

        # Should still get results from the second chapter
        assert len(results) == 1
        assert results[0].event_name == "Later Event"

    async def test_stream_novel_not_found(
        self,
        service_with_config: TimelineExtractionService,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """NotFoundError raised when novel doesn't exist."""
        mock_novel_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            async for _ in service_with_config.stream_extraction(
                novel_id, user_id, chapter_ids=None
            ):
                pass  # pragma: no cover
