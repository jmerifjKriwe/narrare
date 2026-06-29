"""Prompt-Path-Compliance tests for CharacterVoiceService (ANAL-008).

Verifies the RULE-02/02a/02b contract for character-voice analysis:

- ``compose_invocation`` is called in Mode 1 (``composer=`` +
  ``prompt_context=`` + ``intent=``), with NO ``manual_injection=`` kwarg.
- The intent is ``LLMIntent.VOICE`` (ADR-055 D4 — VOICE is routeable).
- The prompt context mode is ``"character_voice"``.
- The composed system prompt reaches the ``CharacterVoiceAgent`` CONSTRUCTOR
  (``system_prompt=``), not a run-time kwarg (pydantic-ai binds
  ``system_prompt`` at construction).
- The attributed dialogue + metrics flow as runtime data in the agent run
  prompt (user channel, RULE-02a category 3) — not inline feature framing.

See:
    ADR-055 — Character voice storage contract (Decision 4 VOICE route).
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    ADR-046 — Prompt-Path-Compliance.
    CONSTRAINTS.md RULE-02/02a/02b.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._character_voice_test_helpers import (
    FakeComposer,
    consume,
    make_agent_output,
    make_chapter,
    make_kb_entry,
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


class TestComposeInvocationMode1:
    """ADR-054 D1: the service routes through ``compose_invocation`` in Mode 1."""

    @pytest.mark.asyncio
    async def test_compose_invocation_called_in_mode1(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        kb_repo = AsyncMock()
        kb_repo.get_by_name = AsyncMock(return_value=make_kb_entry(name="Elena"))

        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        mock_compose.assert_awaited_once()
        kwargs = mock_compose.call_args.kwargs

        # Mode 1: composer-driven (composer= + prompt_context= + intent=)
        assert kwargs.get("composer") is composer, (
            "compose_invocation must be called with composer= (Mode 1, "
            "composer-driven), not manual_injection= (Mode 2)."
        )
        assert kwargs.get("prompt_context") is not None, (
            "compose_invocation must be called with prompt_context= (Mode 1)."
        )
        assert kwargs.get("intent") == LLMIntent.VOICE, (
            f"Expected intent=LLMIntent.VOICE, got {kwargs.get('intent')!r}."
        )
        # Mode 2 contract must NOT be used
        assert "manual_injection" not in kwargs, (
            "manual_injection= kwarg must not be passed — the service is Mode 1 (ADR-054 D7)."
        )

    @pytest.mark.asyncio
    async def test_prompt_context_uses_character_voice_mode(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel(title="The Arrival", genre="Fantasy", writing_language="en")
        chapter = make_chapter(novel_id=novel.id)
        kb_repo = AsyncMock()
        kb_repo.get_by_name = AsyncMock(return_value=make_kb_entry(name="Elena"))

        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        assert getattr(ctx, "mode", None) == "character_voice", (
            f"Expected prompt_context.mode='character_voice', got {getattr(ctx, 'mode', None)!r}."
        )
        assert getattr(ctx, "project_title", "") == "The Arrival"


class TestComposedPromptReachesAgent:
    """ADR-054 D1: the composed system prompt reaches the agent constructor."""

    @pytest.mark.asyncio
    async def test_composed_system_prompt_reaches_agent_constructor(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        kb_repo = AsyncMock()
        kb_repo.get_by_name = AsyncMock(return_value=make_kb_entry(name="Elena"))

        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1(system="COMPOSED-CHARACTER-VOICE-SYSTEM") as (
            MockAgent,
            _MockDeps,
            _mc,
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        construct_kwargs = MockAgent.call_args.kwargs
        assert construct_kwargs.get("system_prompt") == "COMPOSED-CHARACTER-VOICE-SYSTEM", (
            "CharacterVoiceAgent must be constructed with composed.system as its "
            "system_prompt (pydantic-ai binds system_prompt at construction, "
            "not at run-time)."
        )

    @pytest.mark.asyncio
    async def test_run_prompt_carries_dialogue_as_runtime_content(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """The attributed dialogue flows as runtime data in the run prompt
        (RULE-02a category 3) — not inline feature framing."""
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        kb_repo = AsyncMock()
        kb_repo.get_by_name = AsyncMock(return_value=make_kb_entry(name="Elena"))

        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        captured: dict[str, str] = {}

        with patch_mode1(user="") as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])

            async def capture_run(prompt: str, **_kwargs: object) -> object:
                captured["prompt"] = prompt
                return make_agent_output()

            mock_agent.run = capture_run
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        run_prompt = captured.get("prompt", "")
        # The attributed dialogue (speaker-tagged) must appear in the run prompt.
        assert "Elena:" in run_prompt or "Marc:" in run_prompt, (
            "The attributed dialogue must flow as runtime data in the agent run "
            "prompt (user channel, RULE-02a category 3)."
        )
