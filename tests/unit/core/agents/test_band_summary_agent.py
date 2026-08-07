"""Tests für BandSummaryAgent — Instantiation, Output Function, Validation.

BandSummaryAgent aggregiert Kapitel-Zusammenfassungen (ChapterSummaryAgent
Output) in eine novel-level Band-Zusammenfassung mit zwei Feldern:
``full_summary`` (Mehrere Absätze, injiziert für Bände im recency window) und
``short_summary`` (ein Satz, injiziert für ältere Bände).

Type/data-contract tests (BandSummaryOutput, BandSummaryDeps) live in
``test_band_summary_types.py``.

Test-Strategie (mirror ``test_summary_agent.py``):
- TestModel für deterministische Agent-Tests
- Output Function wird direkt via ``_process_output`` getestet
- Validator wird direkt via ``_validate_output`` getestet (ADR-035)
- Keine echten LLM-Calls (RULE-01b)

See SERIES-002 / Spec 2 Task 2.
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.band_summary_agent import BandSummaryAgent
from narrare_core.agents.band_summary_types import BandSummaryDeps, BandSummaryOutput

# ---------------------------------------------------------------------------
# C. BandSummaryAgent — Instantiation
# ---------------------------------------------------------------------------


class TestBandSummaryAgent:
    """BandSummaryAgent instantiiert und executed korrekt."""

    def test_can_be_instantiated(self) -> None:
        agent = BandSummaryAgent(model=TestModel())
        assert isinstance(agent, BandSummaryAgent)

    @pytest.mark.asyncio
    async def test_process_output_with_values(self) -> None:
        """Output function works correctly with valid input.

        Note: TestModel produces empty output which the ADR-035 validator
        rejects. The validator is tested separately below. Here we test the
        output function directly (mirrors test_summary_agent.py).
        """
        agent = BandSummaryAgent(model=TestModel())
        ctx = RunContext[BandSummaryDeps](
            deps=BandSummaryDeps(), model=TestModel(), usage=RunUsage()
        )
        result = await agent._process_output(
            ctx,
            full_summary="The hero journeys across the realm and defeats the shadow.",
            short_summary="A hero defeats the shadow.",
        )
        assert isinstance(result, BandSummaryOutput)
        assert result.full_summary == "The hero journeys across the realm and defeats the shadow."
        assert result.short_summary == "A hero defeats the shadow."

    @pytest.mark.asyncio
    async def test_process_output_with_custom_deps(self) -> None:
        """Output function produces correct output with custom deps."""
        agent = BandSummaryAgent(model=TestModel())
        ctx = RunContext[BandSummaryDeps](
            deps=BandSummaryDeps(
                novel_title="Crown of Thorns",
                genre="Epic Fantasy",
                chapter_summaries=["Ch 1 summary.", "Ch 2 summary."],
            ),
            model=TestModel(),
            usage=RunUsage(),
        )
        result = await agent._process_output(
            ctx,
            full_summary="Crown of Thorns follows the rebellion against an empire.",
            short_summary="A rebellion topples an empire.",
        )
        assert isinstance(result, BandSummaryOutput)
        assert "rebellion" in result.full_summary


# ---------------------------------------------------------------------------
# D. Output Function — _process_output
# ---------------------------------------------------------------------------


class TestProcessOutput:
    """Output Function wird korrekt ausgeführt."""

    @pytest.fixture()
    def run_context(self) -> RunContext[BandSummaryDeps]:
        return RunContext[BandSummaryDeps](
            deps=BandSummaryDeps(), model=TestModel(), usage=RunUsage()
        )

    @pytest.mark.asyncio
    async def test_process_output_defaults(self, run_context: RunContext[BandSummaryDeps]) -> None:
        result = await BandSummaryAgent(model=TestModel())._process_output(run_context)
        assert result.full_summary == ""
        assert result.short_summary == ""

    @pytest.mark.asyncio
    async def test_process_output_partial_streaming(
        self, run_context: RunContext[BandSummaryDeps]
    ) -> None:
        run_context.partial_output = True
        result = await BandSummaryAgent(model=TestModel())._process_output(
            run_context,
            full_summary="Partial summary.",
            short_summary="Partial short.",
        )
        # During streaming a minimal empty result is returned.
        assert result.full_summary == ""
        assert result.short_summary == ""


# ---------------------------------------------------------------------------
# E. Validator — _validate_output (ADR-035)
# ---------------------------------------------------------------------------


class TestValidateOutput:
    """Validator erzwingt deterministische Invarianten (ADR-035)."""

    @pytest.fixture()
    def run_context(self) -> RunContext[BandSummaryDeps]:
        return RunContext[BandSummaryDeps](
            deps=BandSummaryDeps(), model=TestModel(), usage=RunUsage()
        )

    @pytest.mark.asyncio
    async def test_valid_output_passes(self, run_context: RunContext[BandSummaryDeps]) -> None:
        output = BandSummaryOutput(
            full_summary="A complete novel-level summary.",
            short_summary="A one-sentence summary.",
        )
        agent = BandSummaryAgent(model=TestModel())
        result = await agent._validate_output(run_context, output)
        assert result.full_summary == "A complete novel-level summary."

    @pytest.mark.asyncio
    async def test_empty_full_summary_raises_retry(
        self, run_context: RunContext[BandSummaryDeps]
    ) -> None:
        output = BandSummaryOutput(
            full_summary="   ",
            short_summary="A one-sentence summary.",
        )
        agent = BandSummaryAgent(model=TestModel())
        with pytest.raises(ModelRetry):
            await agent._validate_output(run_context, output)

    @pytest.mark.asyncio
    async def test_empty_short_summary_raises_retry(
        self, run_context: RunContext[BandSummaryDeps]
    ) -> None:
        output = BandSummaryOutput(
            full_summary="A complete novel-level summary.",
            short_summary="",
        )
        agent = BandSummaryAgent(model=TestModel())
        with pytest.raises(ModelRetry):
            await agent._validate_output(run_context, output)
