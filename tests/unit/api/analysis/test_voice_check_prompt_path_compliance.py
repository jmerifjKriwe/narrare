"""Prompt-path compliance tests for CharacterVoiceCheckerService."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.intents import LLMIntent
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


class TestVoiceCheckMode1PromptPath:
    """WRITE-010 uses LLMIntent.VOICE + context mode voice_check via Mode 1."""

    @pytest.mark.asyncio
    async def test_compose_invocation_uses_voice_intent_and_voice_check_mode(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel(title="The Arrival")
        chapter = make_chapter(novel_id=novel.id, title="Opening")
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.check(chapter.id, uuid.uuid4()))

        mock_compose.assert_awaited_once()
        kwargs = mock_compose.call_args.kwargs
        assert kwargs.get("intent") == LLMIntent.VOICE
        assert kwargs.get("composer") is not None
        assert kwargs.get("prompt_context") is not None
        assert "manual_injection" not in kwargs
        ctx = kwargs["prompt_context"]
        assert ctx.mode == "voice_check"
        assert ctx.project_title == "The Arrival"
        assert ctx.chapter_title == "Opening"

    @pytest.mark.asyncio
    async def test_composed_system_prompt_reaches_agent_constructor(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)

        with patch_mode1(system="VOICE-CHECK-SYSTEM") as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.check(chapter.id, uuid.uuid4()))

        assert MockAgent.call_args.kwargs["system_prompt"] == "VOICE-CHECK-SYSTEM"

    @pytest.mark.asyncio
    async def test_runtime_prompt_carries_dialogue_profiles_and_metric_delta(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)
        captured: dict[str, str] = {}

        with patch_mode1(user="") as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])

            async def capture_run(prompt: str, **kwargs: object) -> object:
                captured["prompt"] = prompt
                return make_agent_output()

            mock_agent.run = capture_run
            MockAgent.return_value = mock_agent

            await consume(service.check(chapter.id, uuid.uuid4()))

        run_prompt = captured["prompt"]
        assert "Dialogue:" in run_prompt
        assert "Elena:" in run_prompt
        assert "Stored voice profiles:" in run_prompt
        assert "Metric deltas" in run_prompt
