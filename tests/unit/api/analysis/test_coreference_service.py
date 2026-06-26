"""Mode 1 behavioural tests for CoreferenceService (ANAL-005).

Verifies the RULE-02/02a/02b contract for coreference analysis:

- ``compose_invocation`` is called in Mode 1 (``composer=`` +
  ``prompt_context=`` + ``intent=``), with NO ``manual_injection=`` kwarg.
- The composed system prompt reaches the ``CoreferenceAgent`` CONSTRUCTOR
  (``system_prompt=``), not a run-time kwarg (pydantic-ai binds
  ``system_prompt`` at construction).
- The chapter text flows as runtime data in the agent run prompt (user
  channel, RULE-02a category 3) — not inline feature framing.
- SSE events are yielded correctly: a ``"result"`` event followed by a
  terminal ``"done"`` event.

Error-handling / RULE-11 tests live in ``test_coreference_service_errors.py``
(RULE-04 split).

See:
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    ADR-048 — Mode 1/Mode 2 invocation contract.
    CONSTRAINTS.md RULE-02/02a/02b, RULE-11.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._coreference_test_helpers import (
    FakeComposer,
    consume,
    make_agent_output,
    make_chapter,
    make_novel,
    make_service,
    patch_mode1,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


# ---------------------------------------------------------------------------
# Mode 1: compose_invocation called with composer=, prompt_context=, intent=
# ---------------------------------------------------------------------------


class TestComposeInvocationMode1:
    """ADR-054 D1: the service must route through ``compose_invocation``
    in Mode 1 (composer-driven), not Mode 2 (``manual_injection=``)."""

    @pytest.mark.asyncio
    async def test_compose_invocation_called_in_mode1(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

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
        assert kwargs.get("intent") == LLMIntent.ANALYSE, (
            f"Expected intent=LLMIntent.ANALYSE, got {kwargs.get('intent')!r}."
        )
        # Mode 2 contract must NOT be used
        assert "manual_injection" not in kwargs, (
            "manual_injection= kwarg must not be passed — the service is Mode 1 (ADR-054 D7)."
        )

    @pytest.mark.asyncio
    async def test_prompt_context_uses_coreference_mode(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._chapter_repo.get.return_value = make_chapter(  # type: ignore[attr-defined]
            title="The Arrival", content="Alice looked at Bob. She smiled."
        )
        service._novel_repo.get_by_id.return_value = make_novel(  # type: ignore[attr-defined]
            title="My Epic", genre="Fantasy", writing_language="en"
        )

        with patch_mode1() as (MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        assert getattr(ctx, "mode", None) == "coreference", (
            f"Expected prompt_context.mode='coreference', got {getattr(ctx, 'mode', None)!r}."
        )
        # Chapter title flows into the governed template (RULE-02a).
        assert getattr(ctx, "chapter_title", "") == "The Arrival"


# ---------------------------------------------------------------------------
# Channel separation: composed system → agent constructor; text → run prompt
# ---------------------------------------------------------------------------


class TestComposedPromptReachesAgent:
    """ADR-054 D1: the composed system prompt must reach the
    ``CoreferenceAgent`` constructor (``system_prompt=``)."""

    @pytest.mark.asyncio
    async def test_composed_system_prompt_reaches_agent_constructor(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1(system="COMPOSED-COREFERENCE-SYSTEM") as (
            MockAgent,
            _MockDeps,
            _mc,
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        construct_kwargs = MockAgent.call_args.kwargs
        assert construct_kwargs.get("system_prompt") == "COMPOSED-COREFERENCE-SYSTEM", (
            "CoreferenceAgent must be constructed with composed.system as its "
            "system_prompt (pydantic-ai binds system_prompt at construction, "
            "not at run-time)."
        )

    @pytest.mark.asyncio
    async def test_run_prompt_is_chapter_text_not_feature_framing(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """The chapter text flows as runtime data in the run prompt
        (RULE-02a category 3) — not inline feature-task framing."""
        service = make_service(composer, config)
        chapter_text = "Alice looked at Bob. She smiled warmly."
        service._chapter_repo.get.return_value = make_chapter(  # type: ignore[attr-defined]
            content=chapter_text
        )
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        captured: dict[str, str] = {}

        with patch_mode1(user="") as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])

            async def capture_run(prompt: str, **_kwargs: object) -> object:
                captured["prompt"] = prompt
                return make_agent_output()

            mock_agent.run = capture_run
            MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        run_prompt = captured.get("prompt", "")
        assert chapter_text in run_prompt, (
            "The chapter text must flow as runtime data in the agent run prompt "
            "(user channel, RULE-02a category 3)."
        )


# ---------------------------------------------------------------------------
# SSE events: result + done
# ---------------------------------------------------------------------------


class TestSSEEvents:
    """The service yields a ``"result"`` event then a ``"done"`` event."""

    @pytest.mark.asyncio
    async def test_yields_result_then_done(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        assert len(events) == 2
        assert events[0].event == "result"
        assert events[0].result is not None
        assert events[0].result.clarity_score == 82.0
        assert events[0].is_final is False
        assert events[1].event == "done"
        assert events[1].is_final is True
