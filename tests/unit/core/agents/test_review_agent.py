"""Tests für ReviewAgent — Instantiation, Output-Schema, Basic Behavior.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from narrare_core.agents.review_agent import ReviewAgent, ReviewDeps
from narrare_core.agents.review_types import ReviewOutput
from narrare_core.writing.models import WritingContext

# ---------------------------------------------------------------------------
# A. ReviewDeps
# ---------------------------------------------------------------------------


class TestReviewDeps:
    """ReviewDeps erzeugt und konfiguriert korrekt."""

    def test_defaults(self) -> None:
        deps = ReviewDeps()
        assert deps.word_target is None
        assert deps.writing_context is None

    def test_custom_values(self) -> None:
        deps = ReviewDeps(word_target=2000)
        assert deps.word_target == 2000

    def test_accepts_writing_context(self) -> None:
        """ReviewDeps accepts optional WritingContext for enriched review."""
        ctx = WritingContext(
            kb_characters="Elena, Marcus",
            kb_locations="Dark Forest",
            recent_chapters="Chapter 1: The Beginning",
        )
        deps = ReviewDeps(word_target=2000, writing_context=ctx)
        assert deps.word_target == 2000
        assert deps.writing_context is not None
        assert deps.writing_context.kb_characters == "Elena, Marcus"
        assert deps.writing_context.kb_locations == "Dark Forest"

    def test_without_writing_context_backward_compat(self) -> None:
        """ReviewDeps works without WritingContext — backward compatible."""
        deps = ReviewDeps(word_target=1500)
        assert deps.writing_context is None
        # All existing code that only uses word_target still works
        assert deps.word_target == 1500


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
