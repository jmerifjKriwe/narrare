"""Mode 1 behavioural tests for TimelineExtractionService (ADR-054 D2).

Verifies the RULE-02/02a/02b contract for temporal-expression extraction after
the ADR-054 migration from inline f-string (Mode 2) to PromptComposer Mode 1:

- ``compose_invocation`` is called in Mode 1 (``composer=`` +
  ``prompt_context=`` + ``intent=``), with NO ``manual_injection=`` kwarg.
- The composed system prompt is built ONCE before the per-chapter loop (not
  per-chapter) and reaches the ``TemporalExtractionAgent`` CONSTRUCTOR
  (``system_prompt=``).

Source-level regression (no ``_TIMELINE_EXTRACTION_INJECTION``, no
``ManualInjectionDeclaration`` import, RULE-11 propagation, run-prompt channel
separation) lives in ``test_timeline_extraction_service_compliance.py``
(RULE-04 split).

See:
    ADR-054 — Inline Feature-Prompt Debt Migration (FIND-011 clones)
    ADR-049 — Precedent (FIND-011 timeline migration)
    ADR-048 — Mode 1/Mode 2 invocation contract
    CONSTRAINTS.md RULE-02/02a/02b, RULE-11
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.planning._timeline_extraction_test_helpers import (
    FakeComposedInvocation,
    FakeComposer,
    make_agent_output,
    make_chapter,
    make_novel,
    make_service,
)

# ---------------------------------------------------------------------------
# Local helper
# ---------------------------------------------------------------------------


def _make_mock_agent() -> MagicMock:
    """Build a mock TemporalExtractionAgent instance with an async ``run``."""
    mock_agent = MagicMock(spec=["run"])
    mock_agent.run = AsyncMock(return_value=make_agent_output())
    return mock_agent


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
    """ADR-054 D2: the service must route through ``compose_invocation`` in
    Mode 1 (composer-driven), not Mode 2 (``manual_injection=``)."""

    @pytest.mark.asyncio
    async def test_compose_invocation_called_in_mode1(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch(
                "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent"
            ) as MockAgent,
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = _make_mock_agent()
            MockAgent.return_value = mock_agent

            results = []
            async for event in service.stream_extraction(uuid.uuid4(), uuid.uuid4(), None):  # type: ignore[arg-type]
                results.append(event)

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
        assert kwargs.get("intent") == LLMIntent.PLAN, (
            f"Expected intent=LLMIntent.PLAN, got {kwargs.get('intent')!r}."
        )
        # Mode 2 contract must NOT be used
        assert "manual_injection" not in kwargs, (
            "manual_injection= kwarg must not be passed — the service is Mode 1 (ADR-054 D7)."
        )

    @pytest.mark.asyncio
    async def test_prompt_context_uses_timeline_extraction_mode(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel(  # type: ignore[attr-defined]
            title="My Epic", genre="Fantasy", writing_language="en"
        )

        with (
            patch(
                "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent"
            ) as MockAgent,
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = _make_mock_agent()
            MockAgent.return_value = mock_agent

            async for _ in service.stream_extraction(uuid.uuid4(), uuid.uuid4(), None):  # type: ignore[arg-type]
                pass

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        assert getattr(ctx, "mode", None) == "timeline_extraction", (
            f"Expected prompt_context.mode='timeline_extraction', "
            f"got {getattr(ctx, 'mode', None)!r}."
        )
        # Required variables must be present on the context
        assert getattr(ctx, "project_title", None) == "My Epic"
        assert getattr(ctx, "genre", None) == "Fantasy"
        assert getattr(ctx, "writing_language", None) == "en"
        # existing_events flows through the extra dict
        extra = getattr(ctx, "extra", {}) or {}
        assert "existing_events" in extra, (
            "existing_events must be present in prompt_context.extra."
        )


# ---------------------------------------------------------------------------
# Compose ONCE before the loop (not per-chapter)
# ---------------------------------------------------------------------------


class TestComposeOnceBeforeLoop:
    """ADR-054 D2: the system prompt framing does not vary per chapter, so
    ``compose_invocation`` must be called exactly ONCE regardless of the
    number of chapters processed."""

    @pytest.mark.asyncio
    async def test_compose_called_once_for_multiple_chapters(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        chapters = [
            make_chapter(position=0, title="Chapter 1", summary="Three days later..."),
            make_chapter(position=1, title="Chapter 2", summary="The next morning..."),
            make_chapter(position=2, title="Chapter 3", summary="A week passed..."),
        ]
        service = make_service(composer, config, chapters=chapters)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch(
                "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent"
            ) as MockAgent,
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = _make_mock_agent()
            MockAgent.return_value = mock_agent

            async for _ in service.stream_extraction(uuid.uuid4(), uuid.uuid4(), None):  # type: ignore[arg-type]
                pass

        mock_compose.assert_awaited_once()
        assert mock_compose.await_count == 1, (
            "compose_invocation must be called exactly ONCE before the "
            "per-chapter loop — the framing does not vary per chapter (ADR-054 D2)."
        )


# ---------------------------------------------------------------------------
# Composed system prompt reaches the agent constructor
# ---------------------------------------------------------------------------


class TestComposedPromptReachesAgent:
    """ADR-054 D2: the composed system prompt must reach the
    ``TemporalExtractionAgent`` constructor (``system_prompt=``) and be reused
    for every chapter."""

    @pytest.mark.asyncio
    async def test_composed_system_prompt_reaches_agent_constructor(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch(
                "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent"
            ) as MockAgent,
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(
                    return_value=FakeComposedInvocation(
                        system="COMPOSED-TIMELINE-EXTRACTION-SYSTEM"
                    )
                ),
            ),
        ):
            mock_agent = _make_mock_agent()
            MockAgent.return_value = mock_agent

            async for _ in service.stream_extraction(uuid.uuid4(), uuid.uuid4(), None):  # type: ignore[arg-type]
                pass

        construct_kwargs = MockAgent.call_args.kwargs
        assert construct_kwargs.get("system_prompt") == "COMPOSED-TIMELINE-EXTRACTION-SYSTEM", (
            "TemporalExtractionAgent must be constructed with composed.system as "
            "its system_prompt (pydantic-ai binds system_prompt at construction)."
        )
