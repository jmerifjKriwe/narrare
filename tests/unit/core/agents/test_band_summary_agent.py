"""Tests für BandSummaryAgent — Instantiation, Validation.

BandSummaryAgent aggregiert Kapitel-Zusammenfassungen (ChapterSummaryAgent
Output) in eine novel-level Band-Zusammenfassung mit zwei Feldern:
``full_summary`` (Mehrere Absätze, injiziert für Bände im recency window) und
``short_summary`` (ein Satz, injiziert für ältere Bände).

Type/data-contract tests (BandSummaryOutput, BandSummaryDeps) live in
``test_band_summary_types.py``.

Test-Strategie:
- TestModel für deterministische Agent-Tests
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
