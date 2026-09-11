"""Tests für SeriesConsistencyAgent — Instantiation.

SeriesConsistencyAgent detects contradictions between a novel's chapter text
and the series Canon KB (SERIES-004 / Spec 4 Task 1). It compares chapter
prose against provided Canon entries and returns a list of conflicts (empty
list = no contradictions found).

Type/data-contract tests (CanonConflict, SeriesConsistencyOutput, Deps) live
in ``test_series_consistency_types.py``.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Validator + end-to-end run tests live in ``test_series_consistency_validator.py``
  (ADR-035, RULE-04 file-size split)
- Keine echten LLM-Calls (RULE-01b)

See SERIES-004 / Spec 4 Task 1.
"""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from narrare_core.agents.series_consistency_agent import SeriesConsistencyAgent

# ---------------------------------------------------------------------------
# C. SeriesConsistencyAgent — Instantiation
# ---------------------------------------------------------------------------


class TestSeriesConsistencyAgent:
    """SeriesConsistencyAgent instantiiert und executed korrekt."""

    def test_can_be_instantiated(self) -> None:
        agent = SeriesConsistencyAgent(model=TestModel())
        assert isinstance(agent, SeriesConsistencyAgent)


# Validator (ADR-035) + end-to-end run tests live in
# test_series_consistency_validator.py (RULE-04 file-size split).
