"""Tests für SeriesConsistencyAgent — Validator + Agent run.

Validator (ADR-035) and end-to-end run tests for SeriesConsistencyAgent
(SERIES-004 / Spec 4 Task 1). Instantiation and Output Function tests live
in ``test_series_consistency_agent.py``; type/data-contract tests live in
``test_series_consistency_types.py``.

Test-Strategie (mirror ``test_band_summary_agent.py``):
- TestModel für deterministische Agent-Tests
- Validator wird direkt via ``_validate_output`` getestet (ADR-035)
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.series_consistency_agent import SeriesConsistencyAgent
from narrare_core.agents.series_consistency_types import (
    CanonConflict,
    SeriesConsistencyDeps,
    SeriesConsistencyOutput,
)

# ---------------------------------------------------------------------------
# Validator — _validate_output (ADR-035)
# ---------------------------------------------------------------------------


class TestValidateOutput:
    """Validator erzwingt deterministische Invarianten (ADR-035)."""

    @pytest.fixture()
    def run_context(self) -> RunContext[SeriesConsistencyDeps]:
        return RunContext[SeriesConsistencyDeps](
            deps=SeriesConsistencyDeps(), model=TestModel(), usage=RunUsage()
        )

    def _make_conflict(self, **overrides: object) -> CanonConflict:
        defaults: dict[str, object] = {
            "canon_entry_slug": "character-elara-eye-color",
            "canon_entry_name": "Elara — Eye Color",
            "chapter_text_excerpt": "Elara's green eyes scanned the horizon.",
            "canon_statement": "Elara has blue eyes.",
            "explanation": "Chapter says green; Canon says blue.",
            "severity": "error",
        }
        defaults.update(overrides)
        return CanonConflict.model_validate(defaults)

    @pytest.mark.asyncio
    async def test_empty_conflict_list_passes(
        self, run_context: RunContext[SeriesConsistencyDeps]
    ) -> None:
        """No contradictions found is a valid, common result."""
        output = SeriesConsistencyOutput(conflicts=[], summary="No contradictions.")
        agent = SeriesConsistencyAgent(model=TestModel())
        result = await agent._validate_output(run_context, output)
        assert result.conflicts == []

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, run_context: RunContext[SeriesConsistencyDeps]
    ) -> None:
        conflict = self._make_conflict()
        output = SeriesConsistencyOutput(conflicts=[conflict], summary="One conflict.")
        agent = SeriesConsistencyAgent(model=TestModel())
        result = await agent._validate_output(run_context, output)
        assert len(result.conflicts) == 1

    @pytest.mark.asyncio
    async def test_conflict_with_empty_explanation_filtered(
        self, run_context: RunContext[SeriesConsistencyDeps]
    ) -> None:
        """Conflicts with empty explanation are silently dropped (not retried)."""
        output = SeriesConsistencyOutput(
            conflicts=[
                self._make_conflict(explanation="   "),
                self._make_conflict(explanation="Real explanation."),
            ],
            summary="Mixed.",
        )
        agent = SeriesConsistencyAgent(model=TestModel())
        result = await agent._validate_output(run_context, output)
        assert len(result.conflicts) == 1
        assert result.conflicts[0].explanation == "Real explanation."

    @pytest.mark.asyncio
    async def test_conflict_with_empty_chapter_excerpt_raises_retry(
        self, run_context: RunContext[SeriesConsistencyDeps]
    ) -> None:
        """A contradiction needs the contradicting passage."""
        output = SeriesConsistencyOutput(
            conflicts=[self._make_conflict(chapter_text_excerpt="   ")],
            summary="One conflict.",
        )
        agent = SeriesConsistencyAgent(model=TestModel())
        with pytest.raises(ModelRetry):
            await agent._validate_output(run_context, output)

    @pytest.mark.asyncio
    async def test_conflict_with_empty_canon_statement_raises_retry(
        self, run_context: RunContext[SeriesConsistencyDeps]
    ) -> None:
        """A contradiction needs what Canon says."""
        output = SeriesConsistencyOutput(
            conflicts=[self._make_conflict(canon_statement="")],
            summary="One conflict.",
        )
        agent = SeriesConsistencyAgent(model=TestModel())
        with pytest.raises(ModelRetry):
            await agent._validate_output(run_context, output)


# ---------------------------------------------------------------------------
# Agent run — integration with TestModel (verify output structure)
# ---------------------------------------------------------------------------


class TestAgentRun:
    """End-to-end agent run with TestModel verifies output structure."""

    @pytest.mark.asyncio
    async def test_run_returns_series_consistency_output(self) -> None:
        """A full agent.run() returns a SeriesConsistencyOutput (structure check)."""
        agent = SeriesConsistencyAgent(model=TestModel())
        deps = SeriesConsistencyDeps(
            novel_title="The Forbidden Vale",
            canon_entries=["Canon: Elara has blue eyes."],
            chapter_texts=["Elara's green eyes scanned the horizon."],
        )
        result = await agent.run(
            prompt="Check the chapter text against the Canon entries.", deps=deps
        )
        assert isinstance(result, SeriesConsistencyOutput)
        # TestModel yields empty output → empty conflicts list + empty summary
        # is a valid "no contradictions" result.
        assert isinstance(result.conflicts, list)
        assert isinstance(result.summary, str)
