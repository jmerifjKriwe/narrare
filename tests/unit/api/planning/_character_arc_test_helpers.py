"""Shared test helpers for CharacterArcService tests (RULE-04 split).

Provides fakes and fixtures used by both
``test_character_arc_service.py`` (Mode 1 behavioural) and
``test_character_arc_service_compliance.py`` (source-level regression +
RULE-11).

Mirrors the ``_timeline_test_helpers.py`` pattern (ADR-049 precedent).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from narrare.planning.schemas import CharacterArcRequest
from narrare_core.agents.character_arc_types import CharacterArcOutput
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare.planning.character_arc_service import CharacterArcService
    from narrare_core.llm.model_config import ResolvedModelConfig

# ---------------------------------------------------------------------------
# Fakes (avoid bare MagicMock for domain contracts — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model.

    Task-6b-2 bridge: model resolution flows through the ``prepare()``
    single assembly point (which delegates to ``get_model``), so tests
    exercise the migrated service path.
    """

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))

    async def prepare(
        self,
        config: object,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        return SimpleNamespace(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


class FakeComposer:
    """Fake PromptComposer for DI wiring.

    The service routes through ``compose_invocation`` (which calls
    ``composer.build`` internally), so this fake only needs to exist for DI
    wiring — its ``build`` is never reached when ``compose_invocation`` is
    patched. Kept as a real object (not a bare MagicMock) so the service's
    ``composer is None`` guard is satisfied.
    """

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-CHARACTER-ARC-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The service only reads ``invocation.composed_prompt`` (Mode 1 invariant),
    so a lightweight class with that attribute is sufficient and avoids
    constructing the full ``prepared``/``finalized`` pipeline objects.
    """

    def __init__(self, system: str = "COMPOSED-CHARACTER-ARC-SYSTEM", user: str = "") -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(system=system, user=user)


def make_novel(**overrides: object) -> MagicMock:
    """Create a mock novel with the attributes the service reads."""
    from narrare.novels.models import Novel

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "Fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=Novel)
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def make_agent_output() -> CharacterArcOutput:
    """Build a fake CharacterArcAgent.run result."""
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


def make_request() -> CharacterArcRequest:
    return CharacterArcRequest(
        character_name="Lyra",
        character_current_state="A timid orphan",
        character_goal_state="A confident leader",
    )


def make_service(composer: FakeComposer, config: ResolvedModelConfig) -> CharacterArcService:
    """Build a CharacterArcService wired for Mode 1 prompt resolution."""
    from narrare.planning.character_arc_service import CharacterArcService

    novel_repo = AsyncMock()
    return CharacterArcService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_config=config,
        composer=composer,  # type: ignore[arg-type]
    )
