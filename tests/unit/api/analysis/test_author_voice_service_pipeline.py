"""Pipeline-behaviour tests for AuthorVoiceService (ANAL-007 / ADR-074).

Split from ``test_author_voice_service.py`` for RULE-04 compliance
(test file < 300 lines). Covers the pipeline edge cases the happy-path file
does not:

- Profile assembly: descriptive group ← agent output (TestProfileAssembly).
- Min-chapter soft warning: surfaces a warning, does NOT block
  (TestMinChapterWarning).
- RULE-11 graceful degradation: no chapters → empty result, no LLM call
  (TestGracefulDegradation).

See:
    ADR-074 — Author Voice Storage Contract.
    CONSTRAINTS.md RULE-04 / RULE-11.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.analysis.author_voice_service import MIN_CHAPTERS_FOR_PROFILE
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._author_voice_test_helpers import (
    FakeAuthorVoiceRepository,
    FakeComposer,
    consume,
    make_agent_output,
    make_chapter,
    make_novel,
    make_service,
    patch_mode1,
)


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


# ---------------------------------------------------------------------------
# Profile assembly: descriptive group ← agent; metric group ← analyzers
# ---------------------------------------------------------------------------


class TestProfileAssembly:
    """The descriptive group comes from the agent; the metric group from analyzers."""

    @pytest.mark.asyncio
    async def test_descriptive_group_comes_from_agent_output(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapters = [make_chapter(novel_id=novel.id) for _ in range(3)]
        repository = FakeAuthorVoiceRepository()

        service = make_service(composer, config, repository=repository)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)

        agent_output = make_agent_output(
            formality=0.3,
            vocabulary_level="simple",
            sentence_profile="short",
            emotional_range="restricted",
            cultural_regional_markers="southern dialect",
            author_examples=["Yeah. Nope."],
        )
        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=agent_output)
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))

        result_event = next(e for e in events if e.event == "result")
        assert result_event.result is not None
        profile = result_event.result.profile
        assert profile is not None
        assert profile.voice_analysis is not None
        assert profile.voice_analysis.formality == 0.3
        assert profile.voice_analysis.vocabulary_level == "simple"
        assert profile.voice_analysis.sentence_profile == "short"
        assert profile.voice_analysis.emotional_range == "restricted"
        assert profile.voice_analysis.cultural_regional_markers == "southern dialect"
        assert profile.voice_analysis.voice_examples == ["Yeah. Nope."]


# ---------------------------------------------------------------------------
# Min-chapter soft warning (RULE-11 — surfaces a warning, does NOT block)
# ---------------------------------------------------------------------------


class TestMinChapterWarning:
    """Below MIN_CHAPTERS_FOR_PROFILE the service surfaces a soft warning."""

    @pytest.mark.asyncio
    async def test_below_minimum_surfaces_warning_progress(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        # Below MIN_CHAPTERS_FOR_PROFILE (default 3).
        chapters = [make_chapter(novel_id=novel.id) for _ in range(1)]

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))

        progress_events = [e for e in events if e.event == "progress"]
        # The first progress event is the soft warning.
        assert progress_events[0].progress is not None
        assert "Warning" in progress_events[0].progress
        assert str(MIN_CHAPTERS_FOR_PROFILE) in progress_events[0].progress
        # Analysis still proceeds — there is a result event.
        assert any(e.event == "result" for e in events)


# ---------------------------------------------------------------------------
# RULE-11 graceful degradation: no chapters → empty result, no LLM call
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """No chapters → sensible empty result, no crash, no LLM call."""

    @pytest.mark.asyncio
    async def test_no_chapters_yields_done_without_agent_call(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[])

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))

            # Agent must NOT be called when there are no chapters.
            MockAgent.assert_not_called()

        event_types = [e.event for e in events]
        assert "progress" in event_types
        assert event_types[-1] == "done"
        assert events[-1].is_final is True
        # No result event — the pipeline did not run.
        assert not any(e.event == "result" for e in events)
