"""Unit tests for the beta-reader eval Layer-1 scorer (spec 2026-09-14 §9 Slice 2).

Scope per spec §5 Layer 1: P1 category/severity enums + count bounds
(3-7 / 5-12 / 2-5) + non-empty fields + score ranges + soft grounding;
P2 enums + count bounds (5-10 / 3-6) + non-empty + category_score + soft
grounding. Violations are measurements, never crashes; soft checks are
reported, never fail anything.

Synthetic outputs only (no LLM). Out-of-range scores are built via
``model_construct`` — the post-validator output models pin those fields, so
the scorer's own range check is defense in depth against validator
regressions (spec: "model-enforced; recorded for artifact completeness").
"""

from __future__ import annotations

from typing import Any

import pytest
from scripts.evals.beta_reader_scoring import (
    P1_COUNT_BOUNDS,
    P2_FEEDBACK_BOUNDS,
    P2_SUGGESTION_BOUNDS,
    check_phase1,
    check_phase2,
)

from narrare_core.agents.beta_reader_types import (
    AgentDeepDiveFeedback,
    AgentFeedbackItem,
    AgentOverallAssessment,
    AgentReaderQuestion,
    AgentStrength,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)

CHAPTER_TEXT = (
    "# Kapitel Eins\n\n"
    "Der Wald lag still im ersten Licht. Sie ging den Pfad entlang.\n"
    "Ein Reh trabte uber die Lichtung und verschwand im Gestrupp.\n"
)

GROUNDED_EXCERPT = "Der Wald lag still im ersten Licht."
UNGROUNDED_EXCERPT = "Dieser Satz kommt im Kapitel nicht vor."


# ---------------------------------------------------------------------------
# Synthetic output builders
# ---------------------------------------------------------------------------


def _strength(category: str = "prose", excerpt: str | None = GROUNDED_EXCERPT) -> dict[str, Any]:
    return {
        "category": category,
        "title": "Controlled cadence",
        "description": "The sentences carry the scene.",
        "text_excerpt": excerpt,
    }


def _feedback(
    category: str = "pacing",
    severity: str = "moderate",
    excerpt: str | None = GROUNDED_EXCERPT,
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "title": "Dragging middle section",
        "description": "The middle repeats its beats.",
        "text_excerpt": excerpt,
    }


def _question(category: str = "plot") -> dict[str, Any]:
    return {"category": category, "question": "Why does she leave now?"}


def _overall(**overrides: int) -> dict[str, Any]:
    scores: dict[str, int] = {
        "reader_engagement": 7,
        "emotional_impact": 6,
        "pacing_score": 8,
        "prose_quality": 7,
        "plot_progression": 6,
        "character_development": 5,
    }
    scores.update(overrides)
    return {"summary": "A solid chapter.", **scores}


def make_phase1_args(
    *,
    strengths: list[dict[str, Any]] | None = None,
    feedback: list[dict[str, Any]] | None = None,
    questions: list[dict[str, Any]] | None = None,
    overall: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """In-bounds Phase 1 tool args (3 strengths / 5 feedback / 2 questions)."""
    return {
        "strengths": strengths if strengths is not None else _strength_list(3),
        "feedback": feedback if feedback is not None else _feedback_list(5),
        "questions": questions if questions is not None else _question_list(2),
        "overall": overall or _overall(),
    }


def make_phase2_args(
    *,
    feedback: list[dict[str, Any]] | None = None,
    suggestions: list[str] | None = None,
    category_score: int = 7,
) -> dict[str, Any]:
    """In-bounds Phase 2 tool args (5 feedback / 3 suggestions / score 7)."""
    return {
        "detailed_feedback": feedback if feedback is not None else _feedback_list(5),
        "revision_suggestions": suggestions
        if suggestions is not None
        else [f"Revision step {i}" for i in range(3)],
        "category_score": category_score,
    }


def build_phase1(args: dict[str, Any], *, raw: bool = False) -> BetaReaderPhase1Output:
    """Build the Phase 1 output model; ``raw`` bypasses pydantic validation."""
    if not raw:
        return BetaReaderPhase1Output.model_validate(args)
    return BetaReaderPhase1Output.model_construct(
        strengths=[AgentStrength.model_construct(**item) for item in args["strengths"]],
        feedback=[AgentFeedbackItem.model_construct(**item) for item in args["feedback"]],
        questions=[AgentReaderQuestion.model_construct(**item) for item in args["questions"]],
        overall=AgentOverallAssessment.model_construct(**args["overall"]),
    )


def build_phase2(args: dict[str, Any], *, raw: bool = False) -> BetaReaderPhase2Output:
    """Build the Phase 2 output model; ``raw`` bypasses pydantic validation."""
    if not raw:
        return BetaReaderPhase2Output.model_validate(args)
    return BetaReaderPhase2Output.model_construct(
        detailed_feedback=[
            AgentDeepDiveFeedback.model_construct(**item) for item in args["detailed_feedback"]
        ],
        revision_suggestions=args["revision_suggestions"],
        category_score=args["category_score"],
    )


def _strength_list(n: int) -> list[dict[str, Any]]:
    return [_strength() for _ in range(n)]


def _strength_list_with_excerpts(excerpt: str | None, n: int) -> list[dict[str, Any]]:
    return [_strength(excerpt=excerpt) for _ in range(n)]


def _feedback_list(n: int) -> list[dict[str, Any]]:
    return [_feedback() for _ in range(n)]


def _feedback_list_with_excerpts(excerpt: str | None, n: int) -> list[dict[str, Any]]:
    return [_feedback(excerpt=excerpt) for _ in range(n)]


def _question_list(n: int) -> list[dict[str, Any]]:
    return [_question() for _ in range(n)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCountBoundConstants:
    """The declared bound constants mirror spec §5 (documentation by pin)."""

    def test_p1_bounds_match_spec(self) -> None:
        assert P1_COUNT_BOUNDS == {
            "strengths": (3, 7),
            "feedback": (5, 12),
            "questions": (2, 5),
        }

    def test_p2_bounds_match_spec(self) -> None:
        assert P2_FEEDBACK_BOUNDS == (5, 10)
        assert P2_SUGGESTION_BOUNDS == (3, 6)


class TestCheckPhase1:
    def test_in_bounds_output_passes(self) -> None:
        report = check_phase1(build_phase1(make_phase1_args()), CHAPTER_TEXT)

        assert report.phase == "phase1"
        assert report.violations == []
        assert report.passed is True

    def test_invalid_category_flagged_for_every_collection(self) -> None:
        """Validator-enforced for feedback only — strengths/questions are
        additive measurements (spec §5 check table)."""
        args = make_phase1_args(
            strengths=[_strength(category="style"), *_strength_list(2)],
            feedback=[_feedback(category="tone"), *_feedback_list(4)],
            questions=[_question(category="world"), _question()],
        )

        report = check_phase1(build_phase1(args), CHAPTER_TEXT)

        violation = next(v for v in report.violations if v.check_id == "L1-P1-enum-category")
        assert "strengths[0]='style'" in violation.detail
        assert "feedback[0]='tone'" in violation.detail
        assert "questions[0]='world'" in violation.detail

    def test_invalid_severity_flagged(self) -> None:
        args = make_phase1_args(feedback=[_feedback(severity="huge"), *_feedback_list(4)])

        report = check_phase1(build_phase1(args), CHAPTER_TEXT)

        violation = next(v for v in report.violations if v.check_id == "L1-P1-enum-severity")
        assert "huge" in violation.detail

    def test_count_violations_flagged_per_check(self) -> None:
        under = check_phase1(
            build_phase1(make_phase1_args(strengths=_strength_list(2))),
            CHAPTER_TEXT,
        )
        assert any(v.check_id == "L1-P1-count-strengths" for v in under.violations)

        over = check_phase1(
            build_phase1(make_phase1_args(feedback=_feedback_list(13))),
            CHAPTER_TEXT,
        )
        assert any(v.check_id == "L1-P1-count-feedback" for v in over.violations)

        questions = check_phase1(
            build_phase1(make_phase1_args(questions=_question_list(6))),
            CHAPTER_TEXT,
        )
        assert any(v.check_id == "L1-P1-count-questions" for v in questions.violations)

    def test_blank_item_fields_flagged(self) -> None:
        args = make_phase1_args(
            strengths=[_strength(), {"category": "prose", "title": "  ", "description": "x"}],
            feedback=[
                _feedback(),
                {"category": "plot", "severity": "minor", "title": "t", "description": ""},
            ],
            questions=[{"category": "plot", "question": " "}, _question()],
        )

        report = check_phase1(build_phase1(args), CHAPTER_TEXT)

        violation = next(v for v in report.violations if v.check_id == "L1-P1-nonempty")
        assert "strengths[1]" in violation.detail
        assert "feedback[1]" in violation.detail
        assert "questions[0]" in violation.detail

    def test_out_of_range_scores_flagged_despite_model_constraints(self) -> None:
        """model_construct bypasses the pydantic range pins — the scorer must
        still catch the violation (defense in depth)."""
        args = make_phase1_args(overall=_overall(prose_quality=11))

        report = check_phase1(build_phase1(args, raw=True), CHAPTER_TEXT)

        violation = next(v for v in report.violations if v.check_id == "L1-P1-scores")
        assert "prose_quality=11" in violation.detail
        assert report.passed is False

    def test_grounding_fraction_and_none_when_no_excerpts(self) -> None:
        report = check_phase1(build_phase1(make_phase1_args()), CHAPTER_TEXT)
        assert report.grounding is not None
        assert report.grounding.fraction == 1.0

        bare = make_phase1_args(
            strengths=[_strength(excerpt=None) for _ in range(3)],
            feedback=[_feedback(excerpt=None) for _ in range(5)],
        )
        report = check_phase1(build_phase1(bare), CHAPTER_TEXT)
        assert report.grounding is not None
        assert report.grounding.total == 0
        assert report.grounding.fraction is None

    def test_grounding_is_soft_and_never_fails(self) -> None:
        args = make_phase1_args(
            strengths=[_strength(excerpt=UNGROUNDED_EXCERPT), *_strength_list(2)],
            feedback=_feedback_list_with_excerpts(None, 5),
        )

        report = check_phase1(build_phase1(args), CHAPTER_TEXT)

        assert report.grounding is not None
        assert report.grounding.total == 3
        assert report.grounding.grounded == 2
        assert report.grounding.fraction == pytest.approx(2 / 3)
        assert report.passed is True  # soft check never fails anything

    def test_grounding_normalizes_whitespace(self) -> None:
        wrapped = "Der   Wald\tlag\nstill im ersten Licht."
        args = make_phase1_args(
            strengths=_strength_list_with_excerpts(None, 3),
            feedback=[_feedback(excerpt=wrapped), *_feedback_list(4)],
        )

        report = check_phase1(build_phase1(args), CHAPTER_TEXT)

        assert report.grounding is not None
        assert report.grounding.grounded == 5
        assert report.grounding.fraction == 1.0


class TestCheckPhase2:
    def test_in_bounds_output_passes(self) -> None:
        report = check_phase2(build_phase2(make_phase2_args()), CHAPTER_TEXT)

        assert report.phase == "phase2"
        assert report.violations == []
        assert report.passed is True

    def test_invalid_category_and_severity_flagged(self) -> None:
        args = make_phase2_args(
            feedback=[_feedback(category="tone", severity="huge"), *_feedback_list(4)]
        )

        report = check_phase2(build_phase2(args), CHAPTER_TEXT)

        assert any(v.check_id == "L1-P2-enum-category" for v in report.violations)
        assert any(v.check_id == "L1-P2-enum-severity" for v in report.violations)

    def test_count_violations_flagged(self) -> None:
        under = check_phase2(
            build_phase2(make_phase2_args(feedback=_feedback_list(4))),
            CHAPTER_TEXT,
        )
        assert any(v.check_id == "L1-P2-count-feedback" for v in under.violations)

        over = check_phase2(
            build_phase2(make_phase2_args(suggestions=["only one"])),
            CHAPTER_TEXT,
        )
        assert any(v.check_id == "L1-P2-count-suggestions" for v in over.violations)

    def test_blank_items_and_suggestions_flagged(self) -> None:
        args = make_phase2_args(
            feedback=[
                _feedback(),
                {"category": "plot", "severity": "minor", "title": "", "description": "d"},
            ],
            suggestions=["Keep the pace.", "   "],
        )

        report = check_phase2(build_phase2(args), CHAPTER_TEXT)

        violation = next(v for v in report.violations if v.check_id == "L1-P2-nonempty")
        assert "detailed_feedback[1]" in violation.detail
        assert "revision_suggestions[1]" in violation.detail

    def test_out_of_range_category_score_flagged_despite_model_constraints(self) -> None:
        args = make_phase2_args(category_score=0)

        report = check_phase2(build_phase2(args, raw=True), CHAPTER_TEXT)

        violation = next(v for v in report.violations if v.check_id == "L1-P2-score")
        assert "category_score=0" in violation.detail

    def test_grounding_covers_detailed_feedback(self) -> None:
        args = make_phase2_args(
            feedback=[_feedback(excerpt=UNGROUNDED_EXCERPT), *_feedback_list(4)],
        )

        report = check_phase2(build_phase2(args), CHAPTER_TEXT)

        assert report.grounding is not None
        assert report.grounding.total == 5
        assert report.grounding.grounded == 4
        assert report.grounding.fraction == 0.8
