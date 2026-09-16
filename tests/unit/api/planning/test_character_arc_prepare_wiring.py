"""Task 6b-2 wiring test — CharacterArcService resolves via prepare(PLAN).

Character-arc site of the Task-6a/6b structural contract (RULE-04 split
from ``test_planning_prepare_wiring.py`` when the ADR-086 L20 slice's
ctor migration crossed the 400-line test limit): the service resolves
the model via the SINGLE assembly point (``ModelRegistry.prepare``,
Task 4) and forwards the coherent ``(model, model_settings,
usage_limits)`` triple to ``agent.run``.

ADR-086 L20 note: the resolved triple now arrives via
``StaticModelResolution`` (the test equivalent of the production lazy
``ModelResolution`` wiring) — the same config + credentials the eager
factory's ctor kwargs carried (WHAT unchanged, timing-only migration).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from narrare._app.dependencies_services import StaticModelResolution
from narrare.planning.schemas import CharacterArcRequest
from narrare_core.agents.character_arc_types import CharacterArcOutput
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel
from tests.unit.api.planning._prepare_wiring_helpers import (
    USER_BASE_URL,
    USER_KEY,
    ComposedInvocation,
    RecordingPrepareRegistry,
    as_model_registry,
    assert_prepare_wiring,
    composer,
    novel,
    novel_repo_with,
    user_config,
)


def _arc_request() -> CharacterArcRequest:
    return CharacterArcRequest(
        character_name="Lyra",
        character_current_state="A timid orphan",
        character_goal_state="A confident leader",
    )


def _arc_output() -> CharacterArcOutput:
    return CharacterArcOutput(
        character_name="Lyra",
        starting_state="timid",
        ending_state="confident",
        arc_type="growth",
        phases=[],
        key_relationships=[],
        internal_conflict="fear vs duty",
        resolution="embraces duty",
    )


class TestCharacterArcPrepareWiring:
    """CharacterArcAgent resolves via prepare(PLAN) with user credentials."""

    async def test_character_arc_resolves_via_prepare_with_plan_intent(self) -> None:
        from narrare.planning.character_arc_service import CharacterArcService

        config = user_config()
        registry = RecordingPrepareRegistry()
        service = CharacterArcService(
            novel_repo=novel_repo_with(novel()),
            model_registry=as_model_registry(registry),
            # ADR-086 L20: the eager ctor triple, pre-resolved (WHAT unchanged).
            model_resolution=StaticModelResolution(
                ResolvedModel(config=config, api_key=USER_KEY, base_url=USER_BASE_URL)
            ),
            composer=composer(),
        )
        agent = AsyncMock(run=AsyncMock(return_value=_arc_output()))

        with (
            patch(
                "narrare_core.agents.character_arc_agent.CharacterArcAgent",
                return_value=agent,
            ) as MockAgent,
            patch("narrare_core.agents.character_arc_agent.CharacterArcDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=ComposedInvocation()),
            ),
        ):
            await service.generate_character_arc(uuid4(), uuid4(), _arc_request())

        assert_prepare_wiring(
            registry,
            config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.PLAN,
            api_key=USER_KEY,
            base_url=USER_BASE_URL,
        )
