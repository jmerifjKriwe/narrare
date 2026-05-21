"""Tests für ReviewAgent — Instantiation, Output Function, Basic Behavior.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Output Function wird direkt via ``_process_review`` getestet
- Keine echten LLM-Calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.review_agent import ReviewAgent, ReviewDeps
from narrare_core.agents.review_types import ReviewOutput

# ---------------------------------------------------------------------------
# A. ReviewDeps
# ---------------------------------------------------------------------------


class TestReviewDeps:
    """ReviewDeps erzeugt und konfiguriert korrekt."""

    def test_defaults(self) -> None:
        deps = ReviewDeps()
        assert deps.word_target is None

    def test_custom_values(self) -> None:
        deps = ReviewDeps(word_target=2000)
        assert deps.word_target == 2000


# ---------------------------------------------------------------------------
# B. ReviewOutput
# ---------------------------------------------------------------------------


class TestReviewOutput:
    """ReviewOutput validiert korrekt."""

    def test_defaults(self) -> None:
        output = ReviewOutput()
        assert output.approved is False
        assert output.quality_score == 5
        assert output.feedback == ""

    def test_approved(self) -> None:
        output = ReviewOutput(
            approved=True,
            feedback="Great work!",
            quality_score=8,
            suggestions=["Add more dialogue"],
            issues=["Pacing is slow"],
        )
        assert output.approved is True
        assert output.quality_score == 8
        assert len(output.suggestions) == 1
        assert len(output.issues) == 1


# ---------------------------------------------------------------------------
# C. ReviewAgent — Instantiation
# ---------------------------------------------------------------------------


class TestReviewAgent:
    """ReviewAgent instantiiert und executed korrekt."""

    def test_can_be_instantiated(self) -> None:
        model = TestModel()
        agent = ReviewAgent(model=model)
        assert isinstance(agent, ReviewAgent)
        assert agent._agent is not None

    def test_can_be_instantiated_with_test_model(self) -> None:
        """Mit TestModel (kein echter LLM-Call)."""
        model = TestModel()
        agent = ReviewAgent(model=model)
        assert isinstance(agent, ReviewAgent)
        assert agent._agent is not None


# ---------------------------------------------------------------------------
# D. Output Function — _process_review
# ---------------------------------------------------------------------------


class TestProcessReview:
    """Output Function wird korrekt ausgeführt."""

    @pytest.fixture()
    def run_context(self) -> RunContext[ReviewDeps]:
        return RunContext[ReviewDeps](
            deps=ReviewDeps(),
            model=TestModel(),
            usage=RunUsage(),
        )

    @pytest.mark.asyncio
    async def test_process_review_approved(
        self,
        run_context: RunContext[ReviewDeps],
    ) -> None:
        """Approved review → korrektes ReviewOutput."""
        result = await ReviewAgent(model=TestModel())._process_review(
            run_context,
            approved=True,
            feedback="Great draft!",
            suggestions=["Add more description"],
            quality_score=8,
            issues=["Pacing slightly slow"],
        )
        assert result.approved is True
        assert result.feedback == "Great draft!"
        assert len(result.suggestions) == 1
        assert result.quality_score == 8
        assert len(result.issues) == 1

    @pytest.mark.asyncio
    async def test_process_review_needs_revision(
        self,
        run_context: RunContext[ReviewDeps],
    ) -> None:
        """Rejected review → korrekte Felder."""
        result = await ReviewAgent(model=TestModel())._process_review(
            run_context,
            approved=False,
            feedback="Needs work",
            suggestions=["Rewrite intro", "Fix pacing"],
            quality_score=3,
            issues=["Plot hole in chapter 2"],
        )
        assert result.approved is False
        assert result.quality_score == 3
        assert len(result.suggestions) == 2
        assert len(result.issues) == 1

    @pytest.mark.asyncio
    async def test_process_review_partial_streaming(
        self,
        run_context: RunContext[ReviewDeps],
    ) -> None:
        """partial_output → leeres ReviewOutput."""
        run_context.partial_output = True
        result = await ReviewAgent(model=TestModel())._process_review(
            run_context,
            approved=True,
            feedback="Streaming feedback",
            quality_score=9,
        )
        assert result.approved is False  # no processing during streaming
        assert result.feedback == ""
        assert result.quality_score == 5

    @pytest.mark.asyncio
    async def test_process_review_defaults(
        self,
        run_context: RunContext[ReviewDeps],
    ) -> None:
        """Keine args → Standardwerte."""
        result = await ReviewAgent(model=TestModel())._process_review(
            run_context,
        )
        assert result.approved is False
        assert result.feedback == ""
        assert result.suggestions == []
        assert result.quality_score == 5
        assert result.issues == []
