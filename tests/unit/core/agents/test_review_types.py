"""Tests for agents/review_types.py — ReviewOutput model validation.

Covers:
1. Default values
2. Custom values
3. Serialization roundtrip
4. Edge cases
"""

from __future__ import annotations

from narrare_core.agents.review_types import ReviewOutput


class TestReviewOutputDefaults:
    """ReviewOutput has correct defaults."""

    def test_default_approved(self) -> None:
        output = ReviewOutput()
        assert output.approved is False

    def test_default_feedback(self) -> None:
        output = ReviewOutput()
        assert output.feedback == ""

    def test_default_suggestions(self) -> None:
        output = ReviewOutput()
        assert output.suggestions == []

    def test_default_quality_score(self) -> None:
        output = ReviewOutput()
        assert output.quality_score == 5

    def test_default_issues(self) -> None:
        output = ReviewOutput()
        assert output.issues == []


class TestReviewOutputWithValues:
    """ReviewOutput with all fields populated."""

    def test_approved_review(self) -> None:
        output = ReviewOutput(
            approved=True,
            feedback="Well-written chapter.",
            suggestions=["Consider expanding the dialogue."],
            quality_score=8,
            issues=[],
        )
        assert output.approved is True
        assert "Well-written" in output.feedback
        assert len(output.suggestions) == 1
        assert output.quality_score == 8

    def test_rejected_review_with_issues(self) -> None:
        output = ReviewOutput(
            approved=False,
            feedback="Major pacing issues.",
            suggestions=["Rewrite opening", "Add more tension"],
            quality_score=3,
            issues=["Slow pacing", "Plot hole in act 2"],
        )
        assert output.approved is False
        assert len(output.issues) == 2
        assert output.quality_score == 3


class TestReviewOutputSerialization:
    """ReviewOutput serializes correctly."""

    def test_model_dump(self) -> None:
        output = ReviewOutput(
            approved=True,
            feedback="Good.",
            quality_score=7,
        )
        data = output.model_dump()
        assert data["approved"] is True
        assert data["quality_score"] == 7

    def test_roundtrip(self) -> None:
        original = ReviewOutput(
            approved=False,
            feedback="Needs work.",
            suggestions=["Add description"],
            quality_score=4,
            issues=["Flat characters"],
        )
        data = original.model_dump()
        restored = ReviewOutput.model_validate(data)
        assert restored.approved == original.approved
        assert restored.feedback == original.feedback
        assert restored.suggestions == original.suggestions
        assert restored.quality_score == original.quality_score
        assert restored.issues == original.issues

    def test_quality_score_boundary_values(self) -> None:
        """Quality score accepts any int value."""
        output = ReviewOutput(quality_score=1)
        assert output.quality_score == 1
        output = ReviewOutput(quality_score=10)
        assert output.quality_score == 10
