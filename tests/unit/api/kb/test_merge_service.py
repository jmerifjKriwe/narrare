"""Mode 1 behavioural tests for KBMergeService (ADR-054 D3).

Verifies the RULE-02/02a/02b contract for KB entity-merge analysis after
the ADR-054 migration from inline f-string (Mode 2) to PromptComposer Mode 1:

- ``compose_invocation`` is called in Mode 1 (``composer=`` +
  ``prompt_context=`` + ``intent=``), with NO ``manual_injection=`` kwarg.
- The composed system prompt reaches the ``KBMergeAgent`` CONSTRUCTOR
  (``system_prompt=``).
- The agent run prompt does NOT contain the old inline feature framing
  ("Analyze merge candidates...").
- ``candidate_pairs`` and ``world_context`` are supplied as
  ``PromptContext`` variables (system channel), per the
  ``MODE_REQUIRED_VARS["kb"]["merge"]`` gate — not inlined as the run prompt.

Source-level regression (no ``_MERGE_MANUAL_INJECTION``, no
``ManualInjectionDeclaration`` import, RULE-11 propagation) lives in
``test_merge_service_compliance.py`` (RULE-04 split).

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
from tests.unit.api.kb._merge_test_helpers import (
    FakeComposedInvocation,
    FakeComposer,
    make_merge_output,
    make_novel,
    make_request,
    make_service,
)

# ---------------------------------------------------------------------------
# Local helper
# ---------------------------------------------------------------------------


def _make_mock_agent() -> MagicMock:
    """Build a mock KBMergeAgent instance with an async ``run``."""
    mock_agent = MagicMock(spec=["run"])
    mock_agent.run = AsyncMock(return_value=make_merge_output())
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
    """ADR-054 D3: the service must route through ``compose_invocation`` in
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
            patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
            patch("narrare_core.agents.merge_agent.KBMergeDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = _make_mock_agent()
            MockAgent.return_value = mock_agent

            await service.analyze_merge_candidates(uuid.uuid4(), uuid.uuid4(), make_request())

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
        assert kwargs.get("intent") == LLMIntent.KB_CONSISTENCY, (
            f"Expected intent=LLMIntent.KB_CONSISTENCY, got {kwargs.get('intent')!r}."
        )
        # Mode 2 contract must NOT be used
        assert "manual_injection" not in kwargs, (
            "manual_injection= kwarg must not be passed — the service is Mode 1 (ADR-054 D7)."
        )

    @pytest.mark.asyncio
    async def test_prompt_context_uses_merge_mode(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel(  # type: ignore[attr-defined]
            title="My Epic", genre="Fantasy", writing_language="en"
        )

        with (
            patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
            patch("narrare_core.agents.merge_agent.KBMergeDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = _make_mock_agent()
            MockAgent.return_value = mock_agent

            await service.analyze_merge_candidates(uuid.uuid4(), uuid.uuid4(), make_request())

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        assert getattr(ctx, "mode", None) == "merge", (
            f"Expected prompt_context.mode='merge', got {getattr(ctx, 'mode', None)!r}."
        )
        # Required variables must be present on the context
        assert getattr(ctx, "project_title", None) == "My Epic"
        assert getattr(ctx, "genre", None) == "Fantasy"
        assert getattr(ctx, "writing_language", None) == "en"
        assert getattr(ctx, "entity_type", None) == "character"

    @pytest.mark.asyncio
    async def test_candidate_pairs_and_world_context_in_prompt_context(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """ADR-054 D3: ``candidate_pairs`` and ``world_context`` are supplied
        as ``PromptContext`` variables (system channel), per the
        ``MODE_REQUIRED_VARS["kb"]["merge"]`` gate — not inlined as the run
        prompt."""
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
            patch("narrare_core.agents.merge_agent.KBMergeDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = _make_mock_agent()
            MockAgent.return_value = mock_agent

            await service.analyze_merge_candidates(uuid.uuid4(), uuid.uuid4(), make_request())

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        extra = getattr(ctx, "extra", {}) or {}
        assert "candidate_pairs" in extra, (
            "candidate_pairs must be present in prompt_context.extra (system "
            "channel) per MODE_REQUIRED_VARS['kb']['merge'] (ADR-054 D3)."
        )
        assert "world_context" in extra, (
            "world_context must be present in prompt_context.extra (system "
            "channel) per MODE_REQUIRED_VARS['kb']['merge'] (ADR-054 D3)."
        )
        # The candidate_pairs text must be formatted as the service does it
        pairs_text = extra["candidate_pairs"]
        assert "Pair 1:" in pairs_text, "candidate_pairs must be formatted as 'Pair N: ...' lines."


# ---------------------------------------------------------------------------
# Channel separation: composed system → agent constructor; data → run prompt
# ---------------------------------------------------------------------------


class TestComposedPromptReachesAgent:
    """ADR-054 D3: the composed system prompt must reach the
    ``KBMergeAgent`` constructor (``system_prompt=``)."""

    @pytest.mark.asyncio
    async def test_composed_system_prompt_reaches_agent_constructor(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
            patch("narrare_core.agents.merge_agent.KBMergeDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation(system="COMPOSED-MERGE-SYSTEM")),
            ),
        ):
            mock_agent = _make_mock_agent()
            MockAgent.return_value = mock_agent

            await service.analyze_merge_candidates(uuid.uuid4(), uuid.uuid4(), make_request())

        construct_kwargs = MockAgent.call_args.kwargs
        assert construct_kwargs.get("system_prompt") == "COMPOSED-MERGE-SYSTEM", (
            "KBMergeAgent must be constructed with composed.system as its "
            "system_prompt (pydantic-ai binds system_prompt at construction)."
        )

    @pytest.mark.asyncio
    async def test_run_prompt_does_not_contain_inline_feature_framing(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """The agent run prompt must NOT contain the old inline feature
        framing ("Analyze merge candidates..."). Feature framing flows
        through the governed template via PromptComposer (RULE-02a)."""
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel(  # type: ignore[attr-defined]
            title="My Epic"
        )

        captured: list[str] = []

        with (
            patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
            patch("narrare_core.agents.merge_agent.KBMergeDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation(user="")),
            ),
        ):
            mock_agent = _make_mock_agent()

            async def capture_run(prompt: str, **_kwargs: object) -> object:
                captured.append(prompt)
                return make_merge_output()

            mock_agent.run = capture_run
            MockAgent.return_value = mock_agent

            await service.analyze_merge_candidates(uuid.uuid4(), uuid.uuid4(), make_request())

        assert captured, "agent.run was never called"
        for run_prompt in captured:
            assert "Analyze merge candidates" not in run_prompt, (
                "Inline feature-task framing ('Analyze merge candidates...') "
                "must not appear in the run prompt — feature framing flows "
                "through the governed template via PromptComposer (ADR-054 D3)."
            )
