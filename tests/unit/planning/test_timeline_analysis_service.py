"""Behavioural unit tests for TimelineAnalysisService.

Verifies the AI-powered timeline analysis. Confirms the service resolves its
prompt through ``PromptComposer.build(LLMIntent.PLAN, mode="timeline")``
(ADR-049 FIND-011 / D9) and returns the expected analysis shape.

Prompt-path / source-inspection compliance tests live in
``test_timeline_analysis_prompt_path.py`` (RULE-04 split).

See:
    ADR-049 — Prompt-Surface Identity & Path Contract Retrofit
    CONSTRAINTS.md RULE-02/02a/02b
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.unit.planning._timeline_test_helpers import (
    FakeComposer,
    NoProviderResolution,
    make_chapter,
    make_mock_agent,
    make_novel_model,
    make_static_resolution,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_novel_repo() -> MagicMock:
    from unittest.mock import AsyncMock

    return AsyncMock()


@pytest.fixture
def mock_chapter_repo() -> MagicMock:
    from unittest.mock import AsyncMock

    return AsyncMock()


@pytest.fixture
def mock_registry() -> MagicMock:
    from unittest.mock import AsyncMock

    return AsyncMock()


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def model_resolution() -> NoProviderResolution:
    """A resolution whose cascade finds no provider — the degraded state."""
    return NoProviderResolution()


@pytest.fixture
def service(
    mock_novel_repo: MagicMock,
    mock_chapter_repo: MagicMock,
    mock_registry: MagicMock,
    composer: FakeComposer,
    model_resolution: NoProviderResolution,
) -> TimelineAnalysisService:
    return TimelineAnalysisService(
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        model_registry=mock_registry,
        model_resolution=model_resolution,
        composer=composer,  # type: ignore[arg-type]
    )


@pytest.fixture
def service_with_config(
    mock_novel_repo: MagicMock,
    mock_chapter_repo: MagicMock,
    mock_registry: MagicMock,
    composer: FakeComposer,
) -> TimelineAnalysisService:
    """Service with a resolved model config — needed for generate_timeline."""
    return TimelineAnalysisService(
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        model_registry=mock_registry,
        model_resolution=make_static_resolution(),
        composer=composer,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Regression (ADR-049 FIND-011 / D9): composer-driven prompt path
# ---------------------------------------------------------------------------


class TestGenerateTimelineUsesComposer:
    """ADR-049 D9: generate_timeline must resolve the prompt via
    PromptComposer.build(LLMIntent.PLAN, mode="timeline"), not via an inline
    f-string feature prompt (RULE-02/RULE-02a)."""

    async def test_generate_timeline_calls_composer_with_plan_and_timeline_mode(
        self,
        service_with_config: TimelineAnalysisService,
        mock_novel_repo: MagicMock,
        mock_chapter_repo: MagicMock,
        mock_registry: MagicMock,
        composer: FakeComposer,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        novel = make_novel_model(id=novel_id, title="My Epic", genre="fantasy")
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            make_chapter(position=0, title="Ch 1"),
            make_chapter(position=1, title="Ch 2"),
        ]
        mock_registry.get_model.return_value = MagicMock(spec=[])

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            await service_with_config.generate_timeline(novel_id, user_id)

        # AC-1: PromptComposer.build() was called exactly once
        composer.build.assert_awaited_once()

        # AC-1: build() was called with LLMIntent.PLAN
        from narrare_core.llm.intents import LLMIntent

        assert composer.last_intent == LLMIntent.PLAN, (
            f"Expected LLMIntent.PLAN, got {composer.last_intent!r}"
        )

        # AC-1: build() was called with mode="timeline" (ADR-049 D7/D9)
        context_mode = getattr(composer.last_context, "mode", None)
        assert context_mode == "timeline", f"Expected mode='timeline', got {context_mode!r}"

        # AC-1: project metadata propagated to the context
        assert getattr(composer.last_context, "project_title", None) == "My Epic"
        assert getattr(composer.last_context, "genre", None) == "fantasy"


# ---------------------------------------------------------------------------
# Existing coverage: happy path, novel-not-found, no-provider guard
# ---------------------------------------------------------------------------


class TestGenerateTimeline:
    async def test_generate_timeline_returns_analysis(
        self,
        service_with_config: TimelineAnalysisService,
        mock_novel_repo: MagicMock,
        mock_chapter_repo: MagicMock,
        mock_registry: MagicMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        novel = make_novel_model(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            make_chapter(position=0, title="Ch 1"),
            make_chapter(position=1, title="Ch 2"),
        ]
        mock_registry.get_model.return_value = MagicMock(spec=[])

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            result = await service_with_config.generate_timeline(novel_id, user_id)

        assert result.overall_assessment == "Good"
        assert len(result.timeline_events) == 1
        assert result.temporal_conflicts == ["Conflict 1"]
        assert result.coverage_gaps == ["Gap 1"]

    async def test_generate_timeline_nonexistent_novel_raises(
        self,
        service: TimelineAnalysisService,
        mock_novel_repo: MagicMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        mock_novel_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.generate_timeline(novel_id, user_id)

    async def test_generate_timeline_no_provider_raises_config_error(
        self,
        service: TimelineAnalysisService,
        mock_novel_repo: MagicMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Service with a no-provider resolution should raise the preserved
        ConfigurationError (ADR-086 L22 graceful entry-point policy)."""
        novel = make_novel_model(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel

        with pytest.raises(ConfigurationError, match="No AI provider configured"):
            await service.generate_timeline(novel_id, user_id)

    async def test_generate_timeline_no_composer_raises_config_error(
        self,
        mock_novel_repo: MagicMock,
        mock_chapter_repo: MagicMock,
        mock_registry: MagicMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Service without a composer must fail loudly (RULE-11) rather than
        silently fall back to inline prompt assembly (ADR-049 D9)."""
        novel = make_novel_model(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel

        service_no_composer = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_resolution=make_static_resolution(),
            composer=None,
        )

        with pytest.raises(ConfigurationError, match="PromptComposer is not configured"):
            await service_no_composer.generate_timeline(novel_id, user_id)
