"""Behavioural tests for CharacterVoiceDriftService (ANAL-009).

Error + lazy-resolution coverage lives in
``test_voice_drift_service_errors.py`` (RULE-04 split, L11).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.analysis.schemas_voice_drift import VoiceDriftRequest
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._voice_drift_test_helpers import (
    CHAPTER_ONE_DIALOGUE,
    CHAPTER_TWO_DIALOGUE,
    FakeVoiceProfileConsumer,
    consume,
    make_chapter,
    make_drift_result,
    make_novel,
    make_profile,
    make_service,
    patch_mode1,
)


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def _two_chapters(novel_id: uuid.UUID) -> list[object]:
    return [
        make_chapter(novel_id=novel_id, title="Chapter 1", content=CHAPTER_ONE_DIALOGUE),
        make_chapter(novel_id=novel_id, title="Chapter 2", content=CHAPTER_TWO_DIALOGUE),
    ]


class TestVoiceDriftPipeline:
    """The service orchestrates the ADR-073 read-only longitudinal pipeline."""

    @pytest.mark.asyncio
    async def test_happy_path_yields_character_result_and_no_profile(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """Elena (profile+metrics+speaks) → character_result; Marc (no profile) → no_profile."""
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapters=chapters, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            events = await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

        event_types = [event.event for event in events]
        assert event_types[0] == "progress"
        assert event_types[-1] == "done"
        assert events[-1].is_final is True

        result_events = [event for event in events if event.event == "character_result"]
        no_profile_events = [event for event in events if event.event == "no_profile"]
        assert len(result_events) == 1
        assert len(no_profile_events) == 1

        elena = result_events[0].result
        assert elena is not None
        assert elena.character_name == "Elena"
        assert len(elena.trend) == 2  # Elena speaks in both chapters
        assert all(0.0 <= point.match_subscore <= 100.0 for point in elena.trend)
        assert elena.overall_match_score is not None
        assert 0.0 <= elena.overall_match_score <= 100.0
        assert elena.overall_band in {"stable", "minor", "moderate", "major"}
        assert elena.drift.drift_type == "evolution"

        marc = no_profile_events[0].no_profile
        assert marc is not None
        assert marc.character_name == "Marc"
        assert marc.reason == "no_stored_profile"

    @pytest.mark.asyncio
    async def test_uses_consumer_checking_contract_and_one_agent_call_per_character(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """Profiles read via assemble_for_checking; agent called once per analysable character."""
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapters=chapters, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

        assert ("provider", novel.id) in consumer.calls
        assert ("assemble_for_checking", novel.id) in consumer.calls
        # One agent call for Elena (Marc has no profile → no agent call).
        mock_agent.run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_read_only_never_calls_profile_mutators(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """The drift service is read-only (ADR-073 D5) — no KB mutation."""
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapters=chapters, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

        assert consumer.mutator_calls == []


class TestVoiceDriftGracefulPaths:
    """No profile / no metrics / no dialogue produce explicit graceful events."""

    @pytest.mark.asyncio
    async def test_profile_without_voice_metrics_yields_no_profile(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """A profile with no voice_metrics → no_profile (no_voice_metrics), no agent call."""
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena", with_metrics=False)])
        service = make_service(novel=novel, chapters=chapters, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            events = await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

        no_profile_events = [event for event in events if event.event == "no_profile"]
        # Elena (no_voice_metrics) + Marc (no_stored_profile) both skip.
        elena_skip = next(
            event
            for event in no_profile_events
            if event.no_profile and event.no_profile.character_name == "Elena"
        )
        assert elena_skip.no_profile.reason == "no_voice_metrics"
        MockAgent.assert_not_called()

    @pytest.mark.asyncio
    async def test_profiled_character_silent_in_all_chapters_yields_no_profile(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """A profiled character who does not speak → no_profile (no_dialogue), no agent call."""
        novel = make_novel()
        # Only Marc speaks; Elena has a profile but is silent.
        chapters = [
            make_chapter(
                novel_id=novel.id,
                content='"Yeah. Nope," Marc replied.\n',
            )
        ]
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapters=chapters, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            events = await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

        no_profile_events = [event for event in events if event.event == "no_profile"]
        reasons = [event.no_profile.reason for event in no_profile_events]
        assert "no_dialogue_in_selected_chapters" in reasons
        MockAgent.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_chapters_yields_progress_done_without_agent_call(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """A novel with no chapters → progress + done, no agent call."""
        novel = make_novel()
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapters=[], consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            events = await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

        assert [event.event for event in events] == ["progress", "done"]
        assert events[-1].is_final is True
        MockAgent.assert_not_called()


class TestVoiceDriftNonStreamingRun:
    """run() aggregates the stream into a VoiceDriftResponse (RULE-13)."""

    @pytest.mark.asyncio
    async def test_run_aggregates_results_and_no_profiles(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapters=chapters, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            response = await service.run(novel.id, uuid.uuid4(), VoiceDriftRequest())

        assert response.novel_id == str(novel.id)
        assert len(response.results) == 1
        assert response.results[0].character_name == "Elena"
        assert len(response.no_profile) == 1
        assert response.no_profile[0].character_name == "Marc"
