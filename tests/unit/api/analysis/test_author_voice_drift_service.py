"""Behavioural tests for AuthorVoiceDriftService (ANAL-009 Phase 2B / ADR-074).

Verifies the ADR-074 author-drift happy path (the narrator-voice analogue of
Phase 1's character-drift service):

- Happy path: a stored profile with metrics + >=1 chapter with prose -> progress
  + result (trend + jumps + overall score/band + agent classification) + done,
  with exactly ONE agent call (one narrator per novel).
- Read-only: the service never calls the repository mutators (ADR-073 D5).
- run() aggregates the stream into an AuthorVoiceDriftResponse (RULE-13).

RULE-11 graceful paths (no profile / no metrics / no prose) live in
``test_author_voice_drift_service_pipeline.py``; error paths (missing novel /
config / composer) in ``test_author_voice_drift_service_errors.py`` — both
split from this file for RULE-04 compliance (test file < 300 lines).

See:
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (the Phase 1 parallel mirrored here).
    CONSTRAINTS.md RULE-02/02a/02b, RULE-07, RULE-11, RULE-13.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._author_voice_drift_test_helpers import (
    FakeAuthorVoiceRepository,
    FakeChapter,
    _CountingResolution,
    consume,
    make_author_profile,
    make_chapter,
    make_drift_result,
    make_novel,
    make_service,
    patch_mode1,
)


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def _two_chapters(novel_id: uuid.UUID) -> list[FakeChapter]:
    return [
        make_chapter(
            novel_id=novel_id,
            title="Chapter 1",
            content=(
                "The wind moved through the long grass like a rumour. She "
                'paused at the threshold. "You came," she said quietly.'
            ),
        ),
        make_chapter(
            novel_id=novel_id,
            title="Chapter 2",
            content=(
                "Evening deepened around them, patient and full of unspoken "
                "things. The candles guttered as the storm drew closer."
            ),
        ),
    ]


class TestAuthorVoiceDriftPipeline:
    """The service orchestrates the ADR-074 read-only narrator-drift pipeline."""

    @pytest.mark.asyncio
    async def test_happy_path_yields_result_with_trend_jumps_and_classification(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """Stored profile + metrics + prose → progress + result + done."""
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        profile = make_author_profile()
        service = make_service(novel=novel, chapters=chapters, profile=profile, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            events = await consume(
                service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest())
            )

        event_types = [event.event for event in events]
        assert event_types[0] == "progress"
        assert event_types[-1] == "done"
        assert events[-1].is_final is True
        # Author voice is one narrator per novel → exactly one result event.
        result_events = [event for event in events if event.event == "result"]
        assert len(result_events) == 1
        assert len([e for e in events if e.event == "no_profile"]) == 0

        result = result_events[0].result
        assert result is not None
        assert result.novel_id == str(novel.id)
        # Two chapters with prose → two trend points.
        assert len(result.trend) == 2
        assert all(0.0 <= point.match_subscore <= 100.0 for point in result.trend)
        assert result.overall_match_score is not None
        assert 0.0 <= result.overall_match_score <= 100.0
        assert result.overall_band in {"stable", "minor", "moderate", "major"}
        assert result.drift.drift_type == "evolution"

    @pytest.mark.asyncio
    async def test_reads_profile_via_repository_and_runs_one_agent_call(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """Profile read via AuthorVoiceRepository.load; agent called once."""
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        profile = make_author_profile()
        repository = FakeAuthorVoiceRepository(profile)
        service = make_service(
            novel=novel,
            chapters=chapters,
            profile=profile,
            config=config,
            author_voice_repo=repository,
        )

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))

        # The repository's load was called once for the novel.
        assert repository.load_calls == [novel.id]
        # One narrator → exactly one agent call.
        mock_agent.run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_read_only_never_calls_repository_mutators(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """The drift service is read-only (ADR-073 D5) — no storage mutation."""
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        profile = make_author_profile()
        repository = FakeAuthorVoiceRepository(profile)
        service = make_service(
            novel=novel,
            chapters=chapters,
            profile=profile,
            config=config,
            author_voice_repo=repository,
        )

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))

        assert repository.save_calls == []
        assert repository.clear_calls == []


class TestAuthorVoiceDriftNonStreamingRun:
    """run() aggregates the stream into an AuthorVoiceDriftResponse (RULE-13)."""

    @pytest.mark.asyncio
    async def test_run_aggregates_result(self, config: ResolvedModelConfig) -> None:
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        profile = make_author_profile()
        service = make_service(novel=novel, chapters=chapters, profile=profile, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            response = await service.run(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest())

        assert response.novel_id == str(novel.id)
        assert response.result is not None
        assert response.result.novel_id == str(novel.id)
        assert len(response.result.trend) == 2
        assert response.no_profile is None

    @pytest.mark.asyncio
    async def test_run_aggregates_no_profile(self, config: ResolvedModelConfig) -> None:
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        service = make_service(novel=novel, chapters=chapters, profile=None, config=config)

        with patch_mode1() as (_MockAgent, _mock_compose):
            response = await service.run(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest())

        assert response.novel_id == str(novel.id)
        assert response.result is None
        assert response.no_profile is not None
        assert response.no_profile.reason == "no_stored_profile"


# ---------------------------------------------------------------------------
# ADR-086: lazy model resolution at the service boundary
# ---------------------------------------------------------------------------


class TestLazyModelResolution:
    """ADR-086 lazy semantics at the service boundary.

    The DI factory runs pre-body-validation (FastAPI solves all
    sub-dependencies first), so the service must NOT resolve at
    construction. The first ``ensure_resolved()`` / ``run_stream()``
    resolves exactly once; repeat calls reuse the cached triple.
    """

    @pytest.mark.asyncio
    async def test_no_resolution_at_construction(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        resolution = _CountingResolution()
        make_service(
            novel=make_novel(),
            chapters=[],
            profile=None,
            config=config,
            model_resolution=resolution,
        )
        assert resolution.calls == 0

    @pytest.mark.asyncio
    async def test_ensure_resolved_resolves_once_and_is_idempotent(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        resolution = _CountingResolution()
        service = make_service(
            novel=make_novel(),
            chapters=[],
            profile=None,
            config=config,
            model_resolution=resolution,
        )

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert resolution.calls == 1
        assert first is second

    @pytest.mark.asyncio
    async def test_run_stream_resolves_lazily_on_first_use(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        resolution = _CountingResolution()
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        profile = make_author_profile()
        service = make_service(
            novel=novel,
            chapters=chapters,
            profile=profile,
            config=config,
            model_resolution=resolution,
        )

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))

        assert resolution.calls == 1

    @pytest.mark.asyncio
    async def test_run_stream_after_ensure_resolved_reuses_cache(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        resolution = _CountingResolution()
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        profile = make_author_profile()
        service = make_service(
            novel=novel,
            chapters=chapters,
            profile=profile,
            config=config,
            model_resolution=resolution,
        )

        await service.ensure_resolved()

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))

        assert resolution.calls == 1
