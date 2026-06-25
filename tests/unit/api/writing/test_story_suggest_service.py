"""Mode 1 behavioural + SSE + RULE-11 tests for StorySuggestService (ADR-054 D1).

Verifies the RULE-02/02a/02b contract for story-suggest generation (WRITE-009
Writer's Unblock):

- ``compose_invocation`` is called in Mode 1 (``composer=`` +
  ``prompt_context=`` + ``intent=SUGGEST``), with NO ``manual_injection=`` kwarg.
- The composed system prompt reaches the ``StorySuggestAgent`` CONSTRUCTOR
  (``system_prompt=``), not a run-time kwarg (pydantic-ai binds
  ``system_prompt`` at construction).
- SSE events are yielded correctly: a ``"suggestions"`` event followed by a
  ``"done"`` event with ``is_final=True``.
- Error handling (RULE-11): composition failures propagate, missing composer
  raises ConfigurationError, missing novel raises NotFoundError.

See:
    ADR-054 — Inline Feature-Prompt Debt Migration (FIND-011 clones)
    ADR-049 — Precedent (FIND-011 timeline migration)
    ADR-048 — Mode 1/Mode 2 invocation contract
    CONSTRAINTS.md RULE-02/02a/02b, RULE-11
    WRITE-009 — Writer's Unblock Tools
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.writing._story_suggest_test_helpers import (
    FakeComposedInvocation,
    FakeComposer,
    make_agent_output,
    make_novel,
    make_request,
    make_service,
)

if TYPE_CHECKING:
    from narrare.writing.schemas_story_suggest import StorySuggestRequest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


@pytest.fixture
def request_body() -> StorySuggestRequest:
    return make_request()


# ---------------------------------------------------------------------------
# Mode 1: compose_invocation called with composer=, prompt_context=, intent=
# ---------------------------------------------------------------------------


class TestComposeInvocationMode1:
    """ADR-054 D1: the service must route through ``compose_invocation`` in
    Mode 1 (composer-driven), not Mode 2 (``manual_injection=``)."""

    @pytest.mark.asyncio
    async def test_compose_invocation_called_in_mode1(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: StorySuggestRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.story_suggest_agent.StorySuggestAgent") as MockAgent,
            patch("narrare_core.agents.story_suggest_types.StorySuggestDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = [
                e
                async for e in service.suggest(uuid.uuid4(), uuid.uuid4(), request_body)  # type: ignore[arg-type]
            ]

        # Service should yield events (sanity)
        assert len(events) >= 1
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
        assert kwargs.get("intent") == LLMIntent.SUGGEST, (
            f"Expected intent=LLMIntent.SUGGEST, got {kwargs.get('intent')!r}."
        )
        # Mode 2 contract must NOT be used
        assert "manual_injection" not in kwargs, (
            "manual_injection= kwarg must not be passed — the service is Mode 1 (ADR-054 D7)."
        )

    @pytest.mark.asyncio
    async def test_prompt_context_uses_story_suggest_mode(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: StorySuggestRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel(  # type: ignore[attr-defined]
            title="My Epic", genre="Fantasy", writing_language="en"
        )

        with (
            patch("narrare_core.agents.story_suggest_agent.StorySuggestAgent") as MockAgent,
            patch("narrare_core.agents.story_suggest_types.StorySuggestDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            async for _ in service.suggest(uuid.uuid4(), uuid.uuid4(), request_body):  # type: ignore[arg-type]
                pass

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        assert getattr(ctx, "mode", None) == "story_suggest", (
            f"Expected prompt_context.mode='story_suggest', got {getattr(ctx, 'mode', None)!r}."
        )


# ---------------------------------------------------------------------------
# Channel separation: composed system → agent constructor; data → run prompt
# ---------------------------------------------------------------------------


class TestComposedPromptReachesAgent:
    """ADR-054 D1: the composed system prompt must reach the
    ``StorySuggestAgent`` constructor (``system_prompt=``)."""

    @pytest.mark.asyncio
    async def test_composed_system_prompt_reaches_agent_constructor(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: StorySuggestRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.story_suggest_agent.StorySuggestAgent") as MockAgent,
            patch("narrare_core.agents.story_suggest_types.StorySuggestDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(
                    return_value=FakeComposedInvocation(system="COMPOSED-STORY-SUGGEST-SYSTEM")
                ),
            ),
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            async for _ in service.suggest(uuid.uuid4(), uuid.uuid4(), request_body):  # type: ignore[arg-type]
                pass

        construct_kwargs = MockAgent.call_args.kwargs
        assert construct_kwargs.get("system_prompt") == "COMPOSED-STORY-SUGGEST-SYSTEM", (
            "StorySuggestAgent must be constructed with composed.system as its "
            "system_prompt (pydantic-ai binds system_prompt at construction, "
            "not at run-time)."
        )


# ---------------------------------------------------------------------------
# SSE events yielded correctly
# ---------------------------------------------------------------------------


class TestSSEEvents:
    """The service must yield a ``"suggestions"`` event followed by a
    ``"done"`` event with ``is_final=True``."""

    @pytest.mark.asyncio
    async def test_yields_suggestions_then_done(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: StorySuggestRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.story_suggest_agent.StorySuggestAgent") as MockAgent,
            patch("narrare_core.agents.story_suggest_types.StorySuggestDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ),
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = [
                e
                async for e in service.suggest(uuid.uuid4(), uuid.uuid4(), request_body)  # type: ignore[arg-type]
            ]

        assert len(events) == 2, f"Expected 2 events, got {len(events)}."
        assert events[0].event == "suggestions"
        assert events[0].suggestions is not None
        assert len(events[0].suggestions) == 2
        assert events[0].is_final is False
        assert events[1].event == "done"
        assert events[1].is_final is True

    @pytest.mark.asyncio
    async def test_suggestion_fields_mapped_correctly(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: StorySuggestRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.story_suggest_agent.StorySuggestAgent") as MockAgent,
            patch("narrare_core.agents.story_suggest_types.StorySuggestDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ),
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = [
                e
                async for e in service.suggest(uuid.uuid4(), uuid.uuid4(), request_body)  # type: ignore[arg-type]
            ]

        first = events[0].suggestions[0]
        assert first.type == "plot_development"
        assert first.title == "The Hidden Heir"
        assert first.description == "A long-lost heir emerges from the shadows."
        assert first.connection == "Ties to the prophecy thread from chapter 3."


# RULE-11 error-handling tests live in test_story_suggest_service_compliance.py
# (RULE-04 split — this file stays under the 300-line limit).
