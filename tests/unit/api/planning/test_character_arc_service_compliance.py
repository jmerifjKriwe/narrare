"""Source-level compliance + RULE-11 tests for CharacterArcService (ADR-054).

Verifies the regression half of the ADR-054 migration (D7/D8):

- The false ADR-048 Mode 2 ``_CHARACTER_ARC_INJECTION`` declaration and the
  ``ManualInjectionDeclaration`` import are absent (D7).
- No ``manual_injection=`` kwarg and no inline feature-prompt f-string in the
  service source (D7/D1).
- Invocation-composition failures propagate (RULE-11 / D8) instead of being
  silently swallowed by ``except Exception: logger.warning``.
- The service fails loudly when ``composer`` is missing (RULE-11 defensive
  guard).

Behavioural Mode 1 tests live in ``test_character_arc_service.py``
(RULE-04 split).

See:
    ADR-054 — Inline Feature-Prompt Debt Migration (D7/D8)
    CONSTRAINTS.md RULE-02/02a/02b, RULE-11
"""

from __future__ import annotations

import inspect
import uuid
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, patch

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.planning._character_arc_test_helpers import (
    FakeComposer,
    FakeModelRegistry,
    make_novel,
    make_request,
    make_service,
)

if TYPE_CHECKING:
    from narrare.novels.repository import NovelRepository
    from narrare.planning.schemas import CharacterArcRequest
    from narrare_core.llm.gateway import ModelRegistry

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
# Regression (ADR-054 D7): no false Mode 2 declaration / import
# ---------------------------------------------------------------------------


class TestNoManualInjectionDeclaration:
    """ADR-054 D7: ``_CHARACTER_ARC_INJECTION`` and the
    ``ManualInjectionDeclaration`` import must be removed."""

    def test_no_manual_injection_declaration_in_service(self) -> None:
        from narrare.planning import character_arc_service as module

        assert not hasattr(module, "_CHARACTER_ARC_INJECTION"), (
            "_CHARACTER_ARC_INJECTION must not be defined (ADR-054 D7)."
        )
        assert "ManualInjectionDeclaration" not in dir(module), (
            "ManualInjectionDeclaration must not be imported — the service is "
            "now Mode 1 (composer-driven), not Mode 2 (ADR-054 D7)."
        )
        source = inspect.getsource(module)
        assert "manual_injection=" not in source, (
            "manual_injection= kwarg must not be passed (ADR-054 D7)."
        )

    def test_no_inline_feature_fstring_in_service(self) -> None:
        from narrare.planning import character_arc_service as module

        source = inspect.getsource(module)
        # The removed inline f-string interpolated request/novel fields:
        #   f"Generate a character arc for {request.character_name} in {novel.title}"
        # Assert that interpolated form is absent. (The method docstring
        # legitimately says "Generate a character arc for the given character."
        # — that is documentation, not prompt assembly, so it is permitted.)
        assert "Generate a character arc for {request.character_name}" not in source, (
            "The inline feature-prompt f-string must be removed — feature "
            "framing flows through PromptComposer (ADR-054 D1)."
        )
        assert 'in {novel.title}"' not in source, (
            "The inline novel-title interpolation must be removed from the run prompt (ADR-054 D1)."
        )


# ---------------------------------------------------------------------------
# RULE-11 (ADR-054 D8): composition failures propagate, not swallowed
# ---------------------------------------------------------------------------


class TestCompositionFailurePropagates:
    """ADR-054 D8 / RULE-11: invocation-composition errors must propagate.

    The previous ``except Exception: logger.warning`` around
    ``compose_invocation`` silently degraded to the inline f-string. Mode 1
    produces the prompt, so swallowing the failure would leave no prompt —
    the error must now raise.
    """

    @pytest.mark.asyncio
    async def test_compose_invocation_failure_propagates(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: CharacterArcRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.character_arc_agent.CharacterArcAgent"),
            patch("narrare_core.agents.character_arc_agent.CharacterArcDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(side_effect=RuntimeError("pipeline offline")),
            ),
            pytest.raises(RuntimeError, match="pipeline offline"),
        ):
            await service.generate_character_arc(  # type: ignore[arg-type]
                uuid.uuid4(), uuid.uuid4(), request_body
            )


# ---------------------------------------------------------------------------
# Defensive guards: missing composer fails loudly (RULE-11)
# ---------------------------------------------------------------------------


class TestDefensiveGuards:
    """The service must fail loudly (RULE-11) when the composer is missing,
    rather than silently falling back to inline assembly."""

    @pytest.mark.asyncio
    async def test_missing_composer_raises_configuration_error(
        self,
        config: ResolvedModelConfig,
        request_body: CharacterArcRequest,
    ) -> None:
        from narrare._app.dependencies_services import StaticModelResolution
        from narrare.planning.character_arc_service import CharacterArcService
        from narrare_core.llm.model_routing import ResolvedModel
        from narrare_core.shared.errors import ConfigurationError

        service = CharacterArcService(
            novel_repo=cast("NovelRepository", AsyncMock()),
            model_registry=cast("ModelRegistry", FakeModelRegistry()),
            model_resolution=StaticModelResolution(ResolvedModel(config=config)),
            composer=None,
        )
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with pytest.raises(ConfigurationError, match="PromptComposer"):
            await service.generate_character_arc(  # type: ignore[arg-type]
                uuid.uuid4(), uuid.uuid4(), request_body
            )
