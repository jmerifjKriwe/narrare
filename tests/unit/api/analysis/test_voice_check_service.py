"""Behavioural tests for CharacterVoiceCheckerService (WRITE-010)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._voice_check_test_helpers import (
    FakeVoiceProfileConsumer,
    consume,
    make_agent_output,
    make_chapter,
    make_novel,
    make_profile,
    make_service,
    patch_mode1,
)


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


class TestVoiceCheckPipeline:
    """The service orchestrates the ADR-057 read-only checking pipeline."""

    @pytest.mark.asyncio
    async def test_happy_path_yields_blended_result_events(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena"), make_profile("Marc")])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = await consume(service.check(chapter.id, uuid.uuid4()))

        assert [event.event for event in events] == ["progress", "result", "result", "done"]
        result_events = [event for event in events if event.event == "result"]
        elena = next(
            event.result
            for event in result_events
            if event.result and event.result.character_name == "Elena"
        )
        assert elena is not None
        assert elena.has_profile is True
        assert elena.match_score is not None
        assert 0.0 <= elena.match_score <= 100.0
        assert elena.band in {"green", "yellow", "fair", "red"}
        assert elena.match_judgment == "mostly_consistent"
        assert elena.qualitative_sub_score == 80.0
        assert elena.metric_delta_subscore is not None
        assert elena.n_comparable_metrics > 0
        assert elena.flagged_lines[0].reason.startswith("Too casual")
        assert events[-1].is_final is True

    @pytest.mark.asyncio
    async def test_uses_consumer_checking_contract_and_one_agent_call(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena"), make_profile("Marc")])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.check(chapter.id, uuid.uuid4()))

        assert ("provider", novel.id) in consumer.calls
        assert ("assemble_for_checking", novel.id) in consumer.calls
        mock_agent.run.assert_awaited_once()
        deps = mock_agent.run.call_args.kwargs["deps"]
        assert set(deps.character_names) == {"Elena", "Marc"}

    @pytest.mark.asyncio
    async def test_read_only_never_calls_profile_mutators(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.check(chapter.id, uuid.uuid4()))

        assert consumer.mutator_calls == []


class TestVoiceCheckGracefulPaths:
    """No dialogue / no profile produce explicit graceful events."""

    @pytest.mark.asyncio
    async def test_no_profile_yields_has_profile_false_without_agent_call(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            events = await consume(service.check(chapter.id, uuid.uuid4()))

        result_events = [event for event in events if event.event == "result"]
        assert len(result_events) == 2
        assert all(event.result and event.result.has_profile is False for event in result_events)
        assert all(event.result and event.result.match_score is None for event in result_events)
        MockAgent.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_dialogue_yields_progress_done_without_agent_call(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id, content="The wind howled. No one spoke.")
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            events = await consume(service.check(chapter.id, uuid.uuid4()))

        assert [event.event for event in events] == ["progress", "done"]
        assert events[0].progress == "No attributed dialogue found in the chapter."
        assert events[-1].is_final is True
        MockAgent.assert_not_called()
