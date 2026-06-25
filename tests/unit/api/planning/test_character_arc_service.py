"""Mode 1 behavioural tests for CharacterArcService (ADR-054 D1).

Verifies the RULE-02/02a/02b contract for character-arc generation after the
ADR-054 migration from inline f-string (Mode 2) to PromptComposer Mode 1:

- ``compose_invocation`` is called in Mode 1 (``composer=`` +
  ``prompt_context=`` + ``intent=``), with NO ``manual_injection=`` kwarg.
- The composed system prompt reaches the ``CharacterArcAgent`` CONSTRUCTOR
  (``system_prompt=``), not a run-time kwarg (pydantic-ai binds
  ``system_prompt`` at construction).
- The agent run prompt does NOT contain the old inline feature framing
  ("Generate a character arc ...").

Source-level regression (no ``_CHARACTER_ARC_INJECTION``, no
``ManualInjectionDeclaration`` import, RULE-11 propagation) lives in
``test_character_arc_service_compliance.py`` (RULE-04 split).

See:
    ADR-054 — Inline Feature-Prompt Debt Migration (FIND-011 clones)
    ADR-049 — Precedent (FIND-011 timeline migration)
    ADR-048 — Mode 1/Mode 2 invocation contract
    CONSTRAINTS.md RULE-02/02a/02b, RULE-11
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.planning._character_arc_test_helpers import (
    FakeComposedInvocation,
    FakeComposer,
    make_agent_output,
    make_novel,
    make_request,
    make_service,
)

if TYPE_CHECKING:
    from narrare.planning.schemas import CharacterArcRequest

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
def request_body() -> CharacterArcRequest:
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
        request_body: CharacterArcRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.character_arc_agent.CharacterArcAgent") as MockAgent,
            patch("narrare_core.agents.character_arc_agent.CharacterArcDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await service.generate_character_arc(uuid.uuid4(), uuid.uuid4(), request_body)  # type: ignore[arg-type]

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
    async def test_prompt_context_uses_character_arc_mode(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: CharacterArcRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel(  # type: ignore[attr-defined]
            title="My Epic", genre="Fantasy", writing_language="en"
        )

        with (
            patch("narrare_core.agents.character_arc_agent.CharacterArcAgent") as MockAgent,
            patch("narrare_core.agents.character_arc_agent.CharacterArcDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ) as mock_compose,
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await service.generate_character_arc(uuid.uuid4(), uuid.uuid4(), request_body)  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        assert getattr(ctx, "mode", None) == "character_arc", (
            f"Expected prompt_context.mode='character_arc', got {getattr(ctx, 'mode', None)!r}."
        )
        # Required character-arc variables must be present in the context extra
        extra = getattr(ctx, "extra", {}) or {}
        assert extra.get("character_name") == "Lyra"
        assert extra.get("character_current_state") == "A timid orphan"
        assert extra.get("character_goal_state") == "A confident leader"


# ---------------------------------------------------------------------------
# Channel separation: composed system → agent constructor; data → run prompt
# ---------------------------------------------------------------------------


class TestComposedPromptReachesAgent:
    """ADR-054 D1: the composed system prompt must reach the
    ``CharacterArcAgent`` constructor (``system_prompt=``)."""

    @pytest.mark.asyncio
    async def test_composed_system_prompt_reaches_agent_constructor(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: CharacterArcRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.character_arc_agent.CharacterArcAgent") as MockAgent,
            patch("narrare_core.agents.character_arc_agent.CharacterArcDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(
                    return_value=FakeComposedInvocation(system="COMPOSED-CHARACTER-ARC-SYSTEM")
                ),
            ),
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await service.generate_character_arc(uuid.uuid4(), uuid.uuid4(), request_body)  # type: ignore[arg-type]

        construct_kwargs = MockAgent.call_args.kwargs
        assert construct_kwargs.get("system_prompt") == "COMPOSED-CHARACTER-ARC-SYSTEM", (
            "CharacterArcAgent must be constructed with composed.system as its "
            "system_prompt (pydantic-ai binds system_prompt at construction, "
            "not at run-time)."
        )

    @pytest.mark.asyncio
    async def test_run_prompt_does_not_contain_inline_feature_framing(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: CharacterArcRequest,
    ) -> None:
        """The agent run prompt must NOT contain the old inline feature
        framing ("Generate a character arc ..."). Feature framing flows
        through the governed template via PromptComposer (RULE-02a)."""
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel(  # type: ignore[attr-defined]
            title="My Epic"
        )

        captured: dict[str, str] = {}

        with (
            patch("narrare_core.agents.character_arc_agent.CharacterArcAgent") as MockAgent,
            patch("narrare_core.agents.character_arc_agent.CharacterArcDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation(user="")),
            ),
        ):
            mock_agent = MagicMock(spec=["run"])

            async def capture_run(prompt: str, **_kwargs: object) -> object:
                captured["prompt"] = prompt
                return make_agent_output()

            mock_agent.run = capture_run
            MockAgent.return_value = mock_agent

            await service.generate_character_arc(uuid.uuid4(), uuid.uuid4(), request_body)  # type: ignore[arg-type]

        run_prompt = captured.get("prompt", "")
        assert "Generate a character arc" not in run_prompt, (
            "Inline feature-task framing ('Generate a character arc ...') must "
            "not appear in the run prompt — feature framing flows through the "
            "governed template via PromptComposer (ADR-054 D1)."
        )
