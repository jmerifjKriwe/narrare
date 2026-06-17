"""Prompt-Path-Compliance tests for WorldbuildingAnalyzer Phase 2 (CR-AUFG-02-05).

Regression tests enforcing ADR-046: Phase 2 must resolve its prompt through
``PromptComposer.build()`` (governed cascade + variable substitution), NOT
through ``PromptRegistry.resolve()`` directly, and must fail fast on a missing
route instead of falling back to an inline string.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from narrare_core.agents.worldbuilding_types import WorldbuildingDeps
from narrare_core.llm.intents import LLMIntent
from narrare_core.shared.errors import PromptError, PromptRouteNotConfiguredError

from ._wb_compliance_helpers import (
    FakeKBEntry,
    _make_analyzer,
    _phase2_output,
)


class TestPhase2PromptPathCompliance:
    """ADR-046: Phase 2 must use PromptComposer.build(), not PromptRegistry.resolve()."""

    @pytest.mark.asyncio
    async def test_phase2_uses_prompt_composer_not_registry(self) -> None:
        """REGRESSION: Phase2 must call composer.build(), never registry.resolve().

        Before ADR-046: phase2 called ``PromptRegistry.resolve("kb",
        "worldbuilding/phase2")`` directly, bypassing the cascade.
        After ADR-046: phase2 uses ``PromptComposer.build()`` like phase1.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, spy = _make_analyzer([e1, e2])
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        # Composer.build MUST have been called exactly once for phase2.
        assert len(spy.build_calls) == 1, "Phase2 must resolve its prompt via composer.build()"
        intent, _ctx, _kwargs = spy.build_calls[0]
        assert intent == LLMIntent.KB_WORLDBUILD

    @pytest.mark.asyncio
    async def test_phase2_composer_called_with_phase2_mode(self) -> None:
        """Phase2 must request the governed 'worldbuilding/phase2' route.

        The route table allows {'worldbuilding/phase1', 'worldbuilding/phase2'}
        for KB_WORLDBUILD. Phase2 must select the phase2 template explicitly.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, spy = _make_analyzer([e1, e2])
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        assert len(spy.build_calls) == 1
        _intent, ctx, _kwargs = spy.build_calls[0]
        assert ctx.mode == "worldbuilding/phase2"

    @pytest.mark.asyncio
    async def test_phase2_context_carries_entity_data(self) -> None:
        """Template variables must be provisioned via PromptContext.extra.

        The phase2 template requires {{candidate_pairs}}, {{entity_details}},
        and {{existing_relationships}}. These must flow through the governed
        variable engine, not be assembled ad-hoc.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, spy = _make_analyzer([e1, e2])
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en", existing_relationships=[])

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        assert len(spy.build_calls) == 1
        _intent, ctx, _kwargs = spy.build_calls[0]
        # Required template variables present in extra (substituted by engine).
        assert "candidate_pairs" in ctx.extra
        assert "entity_details" in ctx.extra
        assert "existing_relationships" in ctx.extra
        # Provisioned values must be non-empty readable strings.
        assert ctx.extra["candidate_pairs"]
        assert ctx.extra["entity_details"]
        # Entity names must surface in the formatted details.
        assert "Alice" in ctx.extra["entity_details"]
        assert "Bob" in ctx.extra["entity_details"]

    @pytest.mark.asyncio
    async def test_phase2_composed_prompt_passed_to_agent(self) -> None:
        """The agent must receive the composed system prompt, not a fallback string."""
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, _spy = _make_analyzer([e1, e2])
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        run_phase2_kwargs = MockAgent.return_value.run_phase2.call_args.kwargs
        assert run_phase2_kwargs["system_prompt"] == "spy phase2 system prompt"

    @pytest.mark.asyncio
    async def test_phase2_no_inline_fallback(self) -> None:
        """REGRESSION: Missing prompt route must fail fast, not return inline fallback.

        Before ADR-046: ``except Exception: system_prompt = "Check entity pairs
        for worldbuilding contradictions."`` masked configuration failures.
        After ADR-046: a missing route raises a typed ``PromptError``.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        route_error = PromptRouteNotConfiguredError(
            LLMIntent.KB_WORLDBUILD.value,
            "Context mode 'worldbuilding/phase2' is not a governed route.",
        )
        analyzer, _spy = _make_analyzer([e1, e2], composer_raise=route_error)
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with (
            patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent,
            pytest.raises(PromptError),
        ):
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        # The agent must never run when prompt resolution fails.
        MockAgent.return_value.run_phase2.assert_not_called()

    @pytest.mark.asyncio
    async def test_phase2_no_prompt_registry_dependency(self) -> None:
        """The analyzer must not require a PromptRegistry to run phase2.

        After the retrofit, PromptRegistry is no longer injected; all prompt
        resolution flows through PromptComposer. Constructing the analyzer
        without a prompt_registry and running phase2 must succeed.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, _spy = _make_analyzer([e1, e2])
        # No prompt_registry attribute should exist on the instance.
        assert not hasattr(analyzer, "_prompt_registry")
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            result = await analyzer._run_phase2(deps, pairs, uuid4())

        assert len(result) == 1
        assert result[0].category.value == "timeline"
