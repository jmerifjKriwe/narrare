"""Mode-1 prompt-path compliance test for AuthorVoiceService (RULE-02/02b).

Verifies the service routes its system prompt through
:func:`compose_invocation` Mode 1 (``LLMIntent.VOICE`` +
``context_mode="author_voice"``) — NOT an inline f-string, NOT a direct
composer call. The governed ``author_voice`` template IS the system prompt.

Mirrors ``test_character_voice_prompt_path_compliance.py`` (ADR-054
precedent).

See:
    ADR-074 — Author Voice Storage Contract (prompt-surface wiring).
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-02 / RULE-02a / RULE-02b.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.analysis.author_voice_prompt import resolve_author_voice_prompt
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._author_voice_test_helpers import (
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


class TestMode1PromptPathCompliance:
    """The service resolves its prompt via compose_invocation Mode 1."""

    @pytest.mark.asyncio
    async def test_analyze_routes_through_compose_invocation(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapters = [make_chapter(novel_id=novel.id) for _ in range(3)]

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        # compose_invocation must be called exactly once per analyze().
        mock_compose.assert_awaited_once()
        # The intent passed to compose_invocation is LLMIntent.VOICE.
        call_kwargs = mock_compose.call_args.kwargs
        assert call_kwargs.get("intent") == LLMIntent.VOICE

    @pytest.mark.asyncio
    async def test_compose_invocation_receives_author_voice_mode(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """The PromptContext.mode is ``"author_voice"`` (the 4th VOICE mode)."""
        novel = make_novel()
        chapters = [make_chapter(novel_id=novel.id) for _ in range(3)]

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        prompt_context = mock_compose.call_args.kwargs.get("prompt_context")
        assert prompt_context is not None
        assert getattr(prompt_context, "mode", None) == "author_voice"

    @pytest.mark.asyncio
    async def test_resolved_system_prompt_passed_to_agent_constructor(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """The composed system prompt is bound at agent construction (Mode 1)."""
        novel = make_novel()
        chapters = [make_chapter(novel_id=novel.id) for _ in range(3)]

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[attr-defined]

        with patch_mode1(system="GOVERNED-AUTHOR-VOICE-TEMPLATE") as (
            MockAgent,
            _MockDeps,
            _mc,
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        # The agent constructor received the resolved system_prompt kwarg.
        MockAgent.assert_called_once()
        ctor_kwargs = MockAgent.call_args.kwargs
        assert ctor_kwargs.get("system_prompt") == "GOVERNED-AUTHOR-VOICE-TEMPLATE"


class TestResolveAuthorVoicePromptHelper:
    """Direct unit tests for the resolve_author_voice_prompt helper."""

    @pytest.mark.asyncio
    async def test_uses_voice_intent_and_author_voice_mode(self) -> None:
        """The helper builds a PromptContext with mode=author_voice + VOICE intent."""
        from narrare.analysis.author_voice_service import AuthorVoiceService
        from tests.unit.api.analysis._author_voice_test_helpers import (
            FakeAuthorVoiceRepository,
            FakeModelRegistry,
        )

        # Wire a real service so the FakeComposer is exercised via a real
        # PromptComposer-typed slot (not a bare cast). Use AsyncMock(spec=...)
        # for the repositories the helper does not touch (RULE-TEST-01:
        # spec'd mocks, not bare MagicMock).
        novel = make_novel()
        service = AuthorVoiceService(
            novel_repo=AsyncMock(spec=["get_by_id"]),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(spec=["list_by_novel"]),  # type: ignore[arg-type]
            repository=FakeAuthorVoiceRepository(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=ResolvedModelConfig(provider_name="test", model_id="m"),
            composer=FakeComposer(),  # type: ignore[arg-type]
        )
        # Drive the helper directly via the service's composer slot.
        composer = service._composer  # pyright: ignore[reportPrivateUsage]
        assert composer is not None

        with patch_mode1() as (_A, _D, mock_compose):
            await resolve_author_voice_prompt(
                composer,  # type: ignore[arg-type]
                invocation_pipeline=None,
                novel=novel,
                language="en",
                novel_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )

        mock_compose.assert_awaited_once()
        assert mock_compose.call_args.kwargs.get("intent") == LLMIntent.VOICE
        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        assert ctx.mode == "author_voice"
        assert ctx.project_title == "Test Novel"
