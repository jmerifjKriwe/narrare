"""Prompt-Path-Compliance tests for WorldbuildingAnalyzer Phase 1.

Regression tests for the latent bug where Phase 1 was passing
``LLMIntent.KB_WORLDBUILD.value`` (``"kb_worldbuild"``) as the context mode,
but ``resolve_prompt_route()`` only allows ``{"worldbuilding/phase1",
"worldbuilding/phase2"}`` for ``KB_WORLDBUILD``.

Phase 1 must use ``mode="worldbuilding/phase1"`` — matching the governed route
in ``route_table.py`` that maps ``KB_WORLDBUILD`` to ``"worldbuilding/phase1"``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from narrare_core.agents.worldbuilding_types import WorldbuildingDeps
from narrare_core.llm.intents import LLMIntent

from ._wb_compliance_helpers import (
    _make_analyzer,
    _phase1_output,
)


class TestPhase1PromptPathCompliance:
    """Phase 1 must use PromptComposer.build() with mode='worldbuilding/phase1'.

    Regression against latent bug: Phase1 was passing
    ``LLMIntent.KB_WORLDBUILD.value`` (``"kb_worldbuild"``) as the context mode,
    but ``resolve_prompt_route()`` only allows ``{"worldbuilding/phase1",
    "worldbuilding/phase2"}`` for ``KB_WORLDBUILD``. This means Phase1 would
    raise ``PromptRouteNotConfiguredError`` whenever the real PromptComposer
    was used (latent since commit 5e31f611).

    Phase2 already correctly uses ``mode="worldbuilding/phase2"`` — Phase1 must
    match with ``mode="worldbuilding/phase1"``.
    """

    @pytest.mark.asyncio
    async def test_phase1_uses_prompt_composer(self) -> None:
        """Phase1 must call composer.build() to resolve its prompt."""
        analyzer, spy = _make_analyzer([])
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase1 = AsyncMock(return_value=_phase1_output())
            await analyzer._run_phase1(deps, uuid4())

        assert len(spy.build_calls) == 1, "Phase1 must resolve its prompt via composer.build()"
        intent, _ctx, _kwargs = spy.build_calls[0]
        assert intent == LLMIntent.KB_WORLDBUILD

    @pytest.mark.asyncio
    async def test_phase1_mode_is_worldbuilding_phase1(self) -> None:
        """REGRESSION: Phase1 must use mode='worldbuilding/phase1', not the raw intent value.

        ``LLMIntent.KB_WORLDBUILD.value`` resolves to ``"kb_worldbuild"``,
        which is NOT in ``allowed_context_modes`` for ``KB_WORLDBUILD``
        (``route_table.py`` line 128). This test verifies the fix.
        """
        analyzer, spy = _make_analyzer([])
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase1 = AsyncMock(return_value=_phase1_output())
            await analyzer._run_phase1(deps, uuid4())

        assert len(spy.build_calls) == 1
        _intent, ctx, _kwargs = spy.build_calls[0]
        assert ctx.mode == "worldbuilding/phase1", (
            f"Expected 'worldbuilding/phase1' but got '{ctx.mode}'. "
            "Using LLMIntent.KB_WORLDBUILD.value ('kb_worldbuild') is wrong — "
            "it will be rejected by resolve_prompt_route() which only allows "
            "{'worldbuilding/phase1', 'worldbuilding/phase2'} for KB_WORLDBUILD."
        )

    @pytest.mark.asyncio
    async def test_phase1_context_carries_entity_data(self) -> None:
        """Phase1 PromptContext must carry entity_count and entity_types in extra."""
        from narrare_core.agents.worldbuilding_types import Phase1EntitySummary

        deps = WorldbuildingDeps(
            language="en",
            entity_summaries=[
                Phase1EntitySummary(
                    entry_id="e1",
                    name="Alice",
                    entity_type="character",
                    field_fill_rate=0.8,
                    relationship_count=2,
                    has_body=True,
                    chapter_references=3,
                ),
                Phase1EntitySummary(
                    entry_id="e2",
                    name="Bob",
                    entity_type="character",
                    field_fill_rate=0.5,
                    relationship_count=1,
                    has_body=False,
                    chapter_references=1,
                ),
            ],
            template_structures={
                "character": {"name": "string", "age": "number"},
            },
        )
        analyzer, spy = _make_analyzer([])

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase1 = AsyncMock(return_value=_phase1_output())
            await analyzer._run_phase1(deps, uuid4())

        assert len(spy.build_calls) == 1
        _intent, ctx, _kwargs = spy.build_calls[0]
        assert "entity_count" in ctx.extra
        assert "entity_types" in ctx.extra
        assert ctx.extra["entity_count"] == "2"
        assert "character" in ctx.extra["entity_types"]
