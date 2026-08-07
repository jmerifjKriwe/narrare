"""Tests für SeriesConsistencyAgent — Instantiation, Output Function, Validation.

SeriesConsistencyAgent detects contradictions between a novel's chapter text
and the series Canon KB (SERIES-004 / Spec 4 Task 1). It compares chapter
prose against provided Canon entries and returns a list of conflicts (empty
list = no contradictions found).

Type/data-contract tests (CanonConflict, SeriesConsistencyOutput, Deps) live
in ``test_series_consistency_types.py``.

Test-Strategie (mirror ``test_band_summary_agent.py`` / ``test_consistency_agent.py``):
- TestModel für deterministische Agent-Tests
- Output Function wird direkt via ``_process_output`` getestet
- Validator wird direkt via ``_validate_output`` getestet (ADR-035)
- Keine echten LLM-Calls (RULE-01b)

See SERIES-004 / Spec 4 Task 1.
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.series_consistency_agent import SeriesConsistencyAgent
from narrare_core.agents.series_consistency_types import (
    SeriesConsistencyDeps,
    SeriesConsistencyOutput,
)

# ---------------------------------------------------------------------------
# C. SeriesConsistencyAgent — Instantiation
# ---------------------------------------------------------------------------


class TestSeriesConsistencyAgent:
    """SeriesConsistencyAgent instantiiert und executed korrekt."""

    def test_can_be_instantiated(self) -> None:
        agent = SeriesConsistencyAgent(model=TestModel())
        assert isinstance(agent, SeriesConsistencyAgent)

    @pytest.mark.asyncio
    async def test_process_output_with_values(self) -> None:
        """Output function works correctly with valid input.

        Note: TestModel produces empty output which the ADR-035 validator
        accepts (empty conflicts list = no contradictions). The output
        function is tested directly here (mirrors test_band_summary_agent.py).
        """
        agent = SeriesConsistencyAgent(model=TestModel())
        ctx = RunContext[SeriesConsistencyDeps](
            deps=SeriesConsistencyDeps(), model=TestModel(), usage=RunUsage()
        )
        result = await agent._process_output(
            ctx,
            conflicts=[
                {
                    "canon_entry_slug": "character-elara-eye-color",
                    "canon_entry_name": "Elara — Eye Color",
                    "chapter_text_excerpt": "Elara's green eyes scanned the horizon.",
                    "canon_statement": "Elara has blue eyes.",
                    "explanation": "Chapter says green; Canon says blue.",
                    "severity": "error",
                }
            ],
            summary="One canon contradiction detected.",
        )
        assert isinstance(result, SeriesConsistencyOutput)
        assert len(result.conflicts) == 1
        assert result.conflicts[0].severity == "error"
        assert result.conflicts[0].canon_entry_slug == "character-elara-eye-color"
        assert result.summary == "One canon contradiction detected."

    @pytest.mark.asyncio
    async def test_process_output_with_custom_deps(self) -> None:
        """Output function produces correct output with custom deps."""
        agent = SeriesConsistencyAgent(model=TestModel())
        ctx = RunContext[SeriesConsistencyDeps](
            deps=SeriesConsistencyDeps(
                novel_title="Crown of Thorns",
                canon_entries=["Canon: the empire is eastern."],
                chapter_texts=["The western empire crumbled."],
            ),
            model=TestModel(),
            usage=RunUsage(),
        )
        result = await agent._process_output(
            ctx,
            conflicts=[
                {
                    "canon_entry_slug": "world-empire-location",
                    "canon_entry_name": "Empire — Location",
                    "chapter_text_excerpt": "The western empire crumbled.",
                    "canon_statement": "The empire is eastern.",
                    "explanation": "Chapter places the empire west; Canon places it east.",
                    "severity": "warning",
                }
            ],
            summary="One possible location contradiction.",
        )
        assert isinstance(result, SeriesConsistencyOutput)
        assert "location" in result.summary.lower() or len(result.conflicts) == 1


# ---------------------------------------------------------------------------
# D. Output Function — _process_output
# ---------------------------------------------------------------------------


class TestProcessOutput:
    """Output Function wird korrekt ausgeführt."""

    @pytest.fixture()
    def run_context(self) -> RunContext[SeriesConsistencyDeps]:
        return RunContext[SeriesConsistencyDeps](
            deps=SeriesConsistencyDeps(), model=TestModel(), usage=RunUsage()
        )

    @pytest.mark.asyncio
    async def test_process_output_defaults(
        self, run_context: RunContext[SeriesConsistencyDeps]
    ) -> None:
        """No conflicts supplied → empty conflicts list (no contradictions found)."""
        result = await SeriesConsistencyAgent(model=TestModel())._process_output(run_context)
        assert result.conflicts == []
        assert result.summary == ""

    @pytest.mark.asyncio
    async def test_process_output_empty_conflicts_list(
        self, run_context: RunContext[SeriesConsistencyDeps]
    ) -> None:
        """Explicit empty conflicts list is a valid 'no contradictions' result."""
        result = await SeriesConsistencyAgent(model=TestModel())._process_output(
            run_context, conflicts=[], summary="No contradictions found."
        )
        assert result.conflicts == []
        assert result.summary == "No contradictions found."

    @pytest.mark.asyncio
    async def test_process_output_partial_streaming(
        self, run_context: RunContext[SeriesConsistencyDeps]
    ) -> None:
        run_context.partial_output = True
        result = await SeriesConsistencyAgent(model=TestModel())._process_output(
            run_context,
            conflicts=[
                {
                    "canon_entry_slug": "slug",
                    "canon_entry_name": "Name",
                    "chapter_text_excerpt": "excerpt",
                    "canon_statement": "statement",
                    "explanation": "explanation",
                    "severity": "error",
                }
            ],
            summary="Partial.",
        )
        # During streaming a minimal empty result is returned.
        assert result.conflicts == []
        assert result.summary == ""


# Validator (ADR-035) + end-to-end run tests live in
# test_series_consistency_validator.py (RULE-04 file-size split).
