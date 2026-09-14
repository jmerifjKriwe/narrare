"""Unit tests for AIRemapService — coverage, confidence, and chapter role analysis.

Test-Strategie:
- Coverage und Confidence sind reine Mathematik (keine Mocks nötig)
- analyze_chapter_role testet mit/ohne Agent, empty summary
- FO-9: the service prompt is composed via the governed EXTRACT/remap
  route (real PromptRegistry + PromptComposer), pinned route-exact
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.agents.summary_types import SummaryOutput
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm.intents import LLMIntent
from narrare_core.planning import remap as remap_module
from narrare_core.planning.remap import AIRemapService
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry

if TYPE_CHECKING:
    from collections.abc import Callable


class _FakeAgent:
    """Fake ChapterSummaryAgent — records the runtime prompt per run."""

    def __init__(self, output: SummaryOutput) -> None:
        self.prompts: list[str] = []
        self.runs: list[dict[str, object]] = []
        self._output = output

    async def run(
        self,
        *,
        prompt: str,
        deps: object,
        model_settings: object = None,
        usage_limits: object = None,
    ) -> SummaryOutput:
        self.prompts.append(prompt)
        self.runs.append(
            {
                "prompt": prompt,
                "deps": deps,
                "model_settings": model_settings,
                "usage_limits": usage_limits,
            }
        )
        return self._output


@pytest.fixture()
def composer() -> PromptComposer:
    return PromptComposer(PromptRegistry())


@pytest.fixture()
def remap(composer: PromptComposer) -> AIRemapService:
    return AIRemapService(composer=composer)


def _route_context(structure_type: str, summary: str) -> PromptContext:
    """The governed EXTRACT/remap route context (route-exact supply)."""
    return PromptContext(
        language="en",
        mode="remap",
        extra={"structure_type": structure_type, "summary": summary},
    )


# =====================================================================
# Coverage Threshold
# =====================================================================


class TestMeetsCoverageThreshold:
    def test_above_threshold(self, remap: AIRemapService) -> None:
        assert remap.meets_coverage_threshold(total_chapters=10, chapters_with_summaries=8) is True

    def test_at_threshold(self, remap: AIRemapService) -> None:
        assert remap.meets_coverage_threshold(total_chapters=10, chapters_with_summaries=5) is True

    def test_below_threshold(self, remap: AIRemapService) -> None:
        assert remap.meets_coverage_threshold(total_chapters=10, chapters_with_summaries=4) is False

    def test_zero_chapters(self, remap: AIRemapService) -> None:
        assert remap.meets_coverage_threshold(total_chapters=0, chapters_with_summaries=0) is False

    def test_custom_threshold(self, remap: AIRemapService) -> None:
        assert (
            remap.meets_coverage_threshold(
                total_chapters=10, chapters_with_summaries=3, threshold=0.3
            )
            is True
        )

    def test_custom_threshold_below(self, remap: AIRemapService) -> None:
        assert (
            remap.meets_coverage_threshold(
                total_chapters=10, chapters_with_summaries=2, threshold=0.3
            )
            is False
        )

    def test_default_constant(self) -> None:
        assert AIRemapService.DEFAULT_COVERAGE_THRESHOLD == 0.5


# =====================================================================
# Confidence Calculation
# =====================================================================


class TestCalculateConfidence:
    def test_full_coverage(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=10) == 1.0

    def test_partial_coverage(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=6) == 0.5

    def test_partial_at_threshold(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=5) == 0.5

    def test_low_coverage(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=4) == 0.0

    def test_no_summaries(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=10, chapters_with_summaries=0) == 0.0

    def test_zero_chapters(self, remap: AIRemapService) -> None:
        assert remap.calculate_confidence(total_chapters=0, chapters_with_summaries=0) == 0.0


# =====================================================================
# Chapter Role Analysis
# =====================================================================


class TestAnalyzeChapterRole:
    @pytest.mark.asyncio
    async def test_empty_summary_returns_empty_string(self, remap: AIRemapService) -> None:
        result = await remap.analyze_chapter_role(summary="", structure_type="three_act")
        assert result == ""

    @pytest.mark.asyncio
    async def test_whitespace_summary_returns_empty_string(self, remap: AIRemapService) -> None:
        result = await remap.analyze_chapter_role(summary="   ", structure_type="five_act")
        assert result == ""

    @pytest.mark.asyncio
    async def test_without_agent_returns_empty_string(self, remap: AIRemapService) -> None:
        result = await remap.analyze_chapter_role(
            summary="The hero enters the forest.",
            structure_type="three_act",
            agent=None,
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_with_agent_returns_stage(self, remap: AIRemapService) -> None:
        """Mit gemocktem Agent der ein SummaryOutput zurückgibt."""
        agent = _FakeAgent(SummaryOutput(summary="act-1"))
        result = await remap.analyze_chapter_role(
            summary="The hero begins their journey.",
            structure_type="three_act",
            agent=agent,
        )
        assert result == "act-1"

    @pytest.mark.asyncio
    async def test_with_agent_whitespace_stage(self, remap: AIRemapService) -> None:
        """Wenn der Agent leeren Text zurückgibt, wird "" retourniert."""
        agent = _FakeAgent(SummaryOutput(summary="  "))
        result = await remap.analyze_chapter_role(
            summary="The hero begins.",
            structure_type="three_act",
            agent=agent,
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_with_agent_error_returns_empty_string(self, remap: AIRemapService) -> None:
        """Bei Agent-Fehler wird "" retourniert (Graceful Degradation)."""

        class _FailingAgent(_FakeAgent):
            async def run(
                self,
                *,
                prompt: str,
                deps: object,
                model_settings: object = None,
                usage_limits: object = None,
            ) -> SummaryOutput:
                self.prompts.append(prompt)
                raise RuntimeError("LLM unavailable")

        agent = _FailingAgent(SummaryOutput(summary="act-1"))
        result = await remap.analyze_chapter_role(
            summary="The hero begins.",
            structure_type="three_act",
            agent=agent,
        )
        assert result == ""


# =====================================================================
# Prepared triple pass-through (model_settings + usage_limits)
# =====================================================================


class TestPreparedTriplePassThrough:
    """analyze_chapter_role forwards the prepared-triple halves to agent.run.

    Mirrors the 19009e17 boundary tests (wiki/beta-reader/worldbuilding):
    the settings/limits kwargs cross the core service boundary instead
    of stopping at it.
    """

    @pytest.mark.asyncio
    async def test_forwards_settings_and_limits_to_agent_run(self, remap: AIRemapService) -> None:
        agent = _FakeAgent(SummaryOutput(summary="act-1"))
        sentinel_settings = ModelSettings(max_tokens=12_345)
        sentinel_limits = UsageLimits(request_limit=7)

        result = await remap.analyze_chapter_role(
            summary="The hero begins their journey.",
            structure_type="three_act",
            agent=agent,
            model_settings=sentinel_settings,
            usage_limits=sentinel_limits,
        )

        assert result == "act-1"
        assert len(agent.runs) == 1
        assert agent.runs[0]["model_settings"] is sentinel_settings
        assert agent.runs[0]["usage_limits"] is sentinel_limits

    @pytest.mark.asyncio
    async def test_defaults_to_none_settings_and_limits(self, remap: AIRemapService) -> None:
        """Backward compat: without the kwargs the agent run receives None."""
        agent = _FakeAgent(SummaryOutput(summary="act-2"))

        await remap.analyze_chapter_role(
            summary="The hero begins.",
            structure_type="three_act",
            agent=agent,
        )

        assert agent.runs[0]["model_settings"] is None
        assert agent.runs[0]["usage_limits"] is None


class TestChapterSummaryAgentSeam:
    """The production agent seam carries the kwargs to the pydantic-ai run.

    ``ChapterSummaryAgent.run`` inherits the NarrareAgent ``**kwargs``
    pass-through (the 19009e17 convention for ``run()`` overrides) — this
    pins that the agent the remap path really wires accepts and forwards
    the prepared-triple kwargs to the internal pydantic-ai run.
    """

    @pytest.mark.asyncio
    async def test_run_forwards_settings_and_limits_to_inner_run(self) -> None:
        agent = ChapterSummaryAgent(model=TestModel())
        expected = SummaryOutput(summary="act-1")
        stub_agent = AsyncMock(name="inner_agent")
        stub_agent.run = AsyncMock(return_value=SimpleNamespace(output=expected))
        cast("Any", agent)._agent = stub_agent
        sentinel_settings = ModelSettings(max_tokens=12_345)
        sentinel_limits = UsageLimits(request_limit=7)

        result = await agent.run(
            "Stage the chapter.",
            SummaryDeps(language="en"),
            model_settings=sentinel_settings,
            usage_limits=sentinel_limits,
        )

        assert result is expected
        kwargs = stub_agent.run.call_args.kwargs
        assert kwargs["model_settings"] is sentinel_settings
        assert kwargs["usage_limits"] is sentinel_limits


# =====================================================================
# FO-9: Governed prompt composition (EXTRACT/remap route)
# =====================================================================


class TestGovernedPromptComposition:
    """The service must build its prompt via the composer, not raw loads."""

    def test_constructor_requires_composer(self) -> None:
        ctor = cast("Callable[[], AIRemapService]", AIRemapService)
        with pytest.raises(TypeError):
            ctor()

    @pytest.mark.asyncio
    async def test_prompt_matches_governed_route_exactly(
        self, remap: AIRemapService, composer: PromptComposer
    ) -> None:
        """Route-exact pin: the runtime prompt equals the real composer's
        EXTRACT/remap system prompt, byte for byte."""
        agent = _FakeAgent(SummaryOutput(summary="act-1"))
        await remap.analyze_chapter_role(
            summary="The hero begins their journey.",
            structure_type="three_act",
            agent=agent,
        )
        expected_ctx = _route_context("three_act", "The hero begins their journey.")
        expected = (await composer.build(LLMIntent.EXTRACT, expected_ctx)).system
        assert agent.prompts == [expected]

    @pytest.mark.asyncio
    async def test_prompt_with_pipeline_matches_governed_route(
        self, remap: AIRemapService, composer: PromptComposer
    ) -> None:
        """Mode 1 (pipeline wired): compose_invocation composes the same
        governed prompt as the direct composer.build route."""
        agent = _FakeAgent(SummaryOutput(summary="act-2"))
        await remap.analyze_chapter_role(
            summary="The midpoint reversal strikes.",
            structure_type="five_act",
            agent=agent,
            invocation_pipeline=InvocationPipeline(),
        )
        expected_ctx = _route_context("five_act", "The midpoint reversal strikes.")
        expected = (await composer.build(LLMIntent.EXTRACT, expected_ctx)).system
        assert agent.prompts == [expected]

    @pytest.mark.asyncio
    async def test_prompt_has_no_raw_load_artifacts(self, remap: AIRemapService) -> None:
        """The composed prompt carries no frontmatter, no section header,
        and no unsubstituted placeholders (the raw-load defects)."""
        agent = _FakeAgent(SummaryOutput(summary="act-1"))
        await remap.analyze_chapter_role(
            summary="The hidden map is discovered.",
            structure_type="hero_journey",
            agent=agent,
        )
        prompt = agent.prompts[0]
        assert not prompt.startswith("---"), "frontmatter leaked into runtime prompt"
        assert "## System Prompt" not in prompt, "section header leaked into runtime prompt"
        assert "{{" not in prompt, "unsubstituted placeholder in runtime prompt"
        assert "hero_journey" in prompt
        assert "The hidden map is discovered." in prompt
        assert "### Do NOT" in prompt, "Batch-D full-body render regressed"

    @pytest.mark.asyncio
    async def test_compose_failure_degrades_to_empty_and_skips_agent(self) -> None:
        """Total composition failure degrades to '' (caller falls back to
        the position heuristic) — the agent is never run (RULE-11)."""

        class _FailingComposer(PromptComposer):
            async def build(
                self,
                intent: LLMIntent,
                context: PromptContext,
                *,
                db_content: str | None = None,
                user_prompt: str = "",
            ) -> ComposedPrompt:
                raise RuntimeError("compose boom")

        agent = _FakeAgent(SummaryOutput(summary="act-1"))
        service = AIRemapService(composer=_FailingComposer(PromptRegistry()))
        result = await service.analyze_chapter_role(
            summary="The hero begins.",
            structure_type="three_act",
            agent=agent,
        )
        assert result == ""
        assert agent.prompts == []

    def test_raw_load_path_removed(self) -> None:
        """FO-9 ratchet: the raw template-load path no longer exists."""
        assert not hasattr(remap_module, "_get_remap_prompt")
        assert not hasattr(remap_module, "_remap_prompt_template")
        assert not hasattr(remap_module, "_REMAP_MANUAL_INJECTION")
