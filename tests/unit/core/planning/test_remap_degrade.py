"""Dedicated tests for the remap Mode-1 None-degrade branch (13655041).

When ``compose_invocation`` (ADR-048 Mode 1) returns a result whose
``composed_prompt`` is ``None``, ``_compose_remap_system_prompt`` must log
``remap_invocation_compose_failed`` (RULE-11: logged, never silent) and fall
through to the direct ``composer.build`` fallback — the agent still runs with
the governed prompt (not skipped, not raised). This file pins that None path
as the distinct sibling of the exception-path compose-failure test in
``test_remap.py`` (same fake-agent and route-exact assertion shape).

Split from ``test_remap.py`` per RULE-04 (400-line file limit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from structlog.testing import capture_logs

from narrare_core.agents.summary_types import SummaryOutput
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm.intents import LLMIntent
from narrare_core.planning import remap as remap_module
from narrare_core.planning.remap import AIRemapService
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from tests.unit.core.planning.test_remap import _FakeAgent, _route_context

if TYPE_CHECKING:
    from narrare_core.prompts.composer import ComposedPrompt


class _NoneComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode-1 degrade result).

    The remap service only reads ``invocation.composed_prompt`` — a ``None``
    class attribute models the finished-but-promptless pipeline result
    without constructing the full ``prepared``/``finalized`` objects (same
    convention as the analysis ``FakeComposedInvocation`` helpers).
    """

    composed_prompt: ComposedPrompt | None = None


class TestInvocationComposeNoneDegrade:
    """``composed_prompt=None`` from the pipeline → warn + composer fallback."""

    @pytest.mark.asyncio
    async def test_none_composed_prompt_logs_warning_and_runs_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The None path logs ``remap_invocation_compose_failed`` and the
        agent still runs with the route-exact ``composer.build`` prompt."""

        async def _none_compose(**kwargs: object) -> _NoneComposedInvocation:
            return _NoneComposedInvocation()

        monkeypatch.setattr(remap_module, "compose_invocation", _none_compose)
        composer = PromptComposer(PromptRegistry())
        service = AIRemapService(composer=composer)
        agent = _FakeAgent(SummaryOutput(summary="act-1"))

        with capture_logs() as logs:
            result = await service.analyze_chapter_role(
                summary="The hero begins.",
                structure_type="three_act",
                agent=agent,
                invocation_pipeline=InvocationPipeline(),
            )

        # Not skipped, not raised: the agent ran and returned its stage.
        assert result == "act-1"
        # The fallback prompt is the governed direct-composer route (exact).
        expected_ctx = _route_context("three_act", "The hero begins.")
        expected = (await composer.build(LLMIntent.EXTRACT, expected_ctx)).system
        assert agent.prompts == [expected]
        # Exactly one degrade warning, bound with the remap feature_id.
        failures = [
            record for record in logs if record.get("event") == "remap_invocation_compose_failed"
        ]
        assert len(failures) == 1, f"expected one compose-failed warning, got {logs}"
        assert failures[0]["log_level"] == "warning"
        assert failures[0]["feature_id"] == "planning_remap"
