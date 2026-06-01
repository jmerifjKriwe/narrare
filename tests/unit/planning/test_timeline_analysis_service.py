"""Unit tests for TimelineAnalysisService.

Tests the AI-powered timeline analysis with mocked repositories
and model registry. Verifies the agent is called with correct deps.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.novels.models import Novel
from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.shared.errors import ConfigurationError, NotFoundError


def _make_novel_model(**overrides: object) -> Novel:
    """Create a mock novel using Novel spec."""
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=Novel)
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def _make_chapter(**overrides: object) -> MagicMock:
    """Create a mock chapter using Chapter spec."""
    from narrare.chapters.models import Chapter

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Chapter 1"),
        "position": overrides.get("position", 0),
        "summary": overrides.get("summary", "A summary"),
        "timeline_position": overrides.get("timeline_position", "Day 1"),
    }
    defaults.update(overrides)
    chapter = MagicMock(spec=Chapter)
    for k, v in defaults.items():
        setattr(chapter, k, v)
    return chapter


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
def mock_registry() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def model_config() -> ResolvedModelConfig:
    """Provide a resolved model config for tests that call generate_timeline."""
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


@pytest.fixture
def service(
    mock_novel_repo: AsyncMock,
    mock_chapter_repo: AsyncMock,
    mock_registry: AsyncMock,
) -> TimelineAnalysisService:
    return TimelineAnalysisService(
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        model_registry=mock_registry,
        model_config=None,
    )


@pytest.fixture
def service_with_config(
    mock_novel_repo: AsyncMock,
    mock_chapter_repo: AsyncMock,
    mock_registry: AsyncMock,
    model_config: ResolvedModelConfig,
) -> TimelineAnalysisService:
    """Service with a real model config — needed for generate_timeline."""
    return TimelineAnalysisService(
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        model_registry=mock_registry,
        model_config=model_config,
    )


class TestGenerateTimeline:
    async def test_generate_timeline_returns_analysis(
        self,
        service_with_config: TimelineAnalysisService,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        novel = _make_novel_model(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            _make_chapter(position=0, title="Ch 1"),
            _make_chapter(position=1, title="Ch 2"),
        ]

        # Mock model and agent
        mock_model = AsyncMock(spec=[])
        mock_registry.get_model.return_value = mock_model

        # Use a dict-based fake instead of spec=[] MagicMock
        # which blocks attribute access
        class FakeEvent:
            def model_dump(self) -> dict[str, object]:
                return {
                    "event_name": "Battle",
                    "description": "",
                    "timestamp": "Day 1",
                    "chapter_reference": "Ch 1",
                    "characters_involved": [],
                    "location": "",
                    "causes": [],
                    "consequences": [],
                }

        class FakeAgentResult:
            def __init__(self) -> None:
                self.timeline_events = [FakeEvent()]
                self.temporal_conflicts = ["Conflict 1"]
                self.coverage_gaps = ["Gap 1"]
                self.overall_assessment = "Good"

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = FakeAgentResult()

        with (
            patch(
                "narrare_core.agents.timeline_agent.TimelineAgent",
                return_value=mock_agent_instance,
            ),
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            result = await service_with_config.generate_timeline(novel_id, user_id)

        assert result.overall_assessment == "Good"
        assert len(result.timeline_events) == 1
        assert result.temporal_conflicts == ["Conflict 1"]
        assert result.coverage_gaps == ["Gap 1"]

    async def test_generate_timeline_nonexistent_novel_raises(
        self,
        service: TimelineAnalysisService,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        mock_novel_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.generate_timeline(novel_id, user_id)

    async def test_generate_timeline_no_provider_raises_config_error(
        self,
        service: TimelineAnalysisService,
        mock_novel_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Service with None model_config should raise ConfigurationError."""
        novel = _make_novel_model(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel

        with pytest.raises(ConfigurationError, match="No AI provider configured"):
            await service.generate_timeline(novel_id, user_id)
