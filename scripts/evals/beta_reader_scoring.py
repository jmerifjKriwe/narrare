"""Layer-1 automatic contract checks for the beta-reader eval instrument.

Spec: ``docs/superpowers/specs/2026-09-14-beta-reader-eval-design.md`` — §5
Layer 1. Deterministic Output-Format contract checks on the REAL chain's
post-validator structured output (ADR-035 validators silently drop empty
items before we see the result — a violation here is a *shipped* contract
breach, which is the correct measurement).

Semantics (spec §5): violations are *measurements*, not crashes — a run with
13 feedback items completes and lists the violation. Soft checks
(``L1-*-grounding``) are reported in :attr:`Layer1Report.grounding` and never
fail anything. No gate consumes these numbers (manual instrument).

Field mapping for the non-empty check: strengths/feedback carry
``title``/``description``; the reader question's content field is
``question`` (its title/description analog — ``context`` is optional).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from narrare.analysis.contracts import FeedbackSeverity
from narrare_core.agents.beta_reader_validators import VALID_CATEGORIES

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare_core.agents.beta_reader_types import (
        BetaReaderPhase1Output,
        BetaReaderPhase2Output,
    )

__all__ = [
    "CATEGORIES",
    "P1_COUNT_BOUNDS",
    "P2_FEEDBACK_BOUNDS",
    "P2_SUGGESTION_BOUNDS",
    "SEVERITIES",
    "GroundingResult",
    "Layer1Report",
    "Layer1Violation",
    "check_phase1",
    "check_phase2",
]

#: Feedback categories (single source: the ADR-035 validator's frozenset).
CATEGORIES: frozenset[str] = VALID_CATEGORIES

#: Feedback severities (single source: the analysis contract enum).
SEVERITIES: frozenset[str] = frozenset(item.value for item in FeedbackSeverity)

#: Phase 1 count bounds per collection (spec §5: 3-7 / 5-12 / 2-5).
P1_COUNT_BOUNDS: dict[str, tuple[int, int]] = {
    "strengths": (3, 7),
    "feedback": (5, 12),
    "questions": (2, 5),
}

#: Phase 2 count bounds (spec §5: feedback 5-10, suggestions 3-6).
P2_FEEDBACK_BOUNDS: tuple[int, int] = (5, 10)
P2_SUGGESTION_BOUNDS: tuple[int, int] = (3, 6)

_SCORE_BOUNDS: tuple[int, int] = (1, 10)


class Layer1Violation(BaseModel):
    """One hard contract violation — a measurement, not an error."""

    model_config = ConfigDict(frozen=True)

    check_id: str
    detail: str


class GroundingResult(BaseModel):
    """Soft grounding check result (reported, never fails).

    Fraction of non-null ``text_excerpt`` values found verbatim
    (whitespace-normalized) in the chapter text. ``fraction`` is ``None``
    when there are no non-null excerpts (nothing to ground).
    """

    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    grounded: int = Field(ge=0)
    fraction: float | None = Field(default=None, ge=0.0, le=1.0)


class Layer1Report(BaseModel):
    """Layer-1 check report for one chapter-x-mode case."""

    model_config = ConfigDict(frozen=True)

    phase: Literal["phase1", "phase2"]
    violations: list[Layer1Violation] = Field(default_factory=list[Layer1Violation])
    grounding: GroundingResult | None = None

    @property
    def passed(self) -> bool:
        """True when no hard contract violation was measured."""
        return not self.violations


def check_phase1(output: BetaReaderPhase1Output, chapter_text: str) -> Layer1Report:
    """Run the Phase 1 (beta_reader) Layer-1 checks (spec §5 table)."""
    violations: list[Layer1Violation] = []

    offenders = (
        _enum_offenders("strengths", [item.category for item in output.strengths], CATEGORIES)
        + _enum_offenders("feedback", [item.category for item in output.feedback], CATEGORIES)
        + _enum_offenders("questions", [item.category for item in output.questions], CATEGORIES)
    )
    _append(violations, "L1-P1-enum-category", offenders, CATEGORIES)
    _append(
        violations,
        "L1-P1-enum-severity",
        _enum_offenders("feedback", [item.severity for item in output.feedback], SEVERITIES),
        SEVERITIES,
    )

    for name, items in (
        ("strengths", output.strengths),
        ("feedback", output.feedback),
        ("questions", output.questions),
    ):
        low, high = P1_COUNT_BOUNDS[name]
        if not low <= len(items) <= high:
            violations.append(
                Layer1Violation(
                    check_id=f"L1-P1-count-{name}",
                    detail=f"{name} count {len(items)} outside [{low}, {high}]",
                )
            )

    blank = (
        _blank_rows("strengths", output.strengths, ("title", "description"))
        + _blank_rows("feedback", output.feedback, ("title", "description"))
        + _blank_rows("questions", output.questions, ("question",))
    )
    if blank:
        violations.append(Layer1Violation(check_id="L1-P1-nonempty", detail="; ".join(blank)))

    scores: dict[str, int] = {
        "reader_engagement": output.overall.reader_engagement,
        "emotional_impact": output.overall.emotional_impact,
        "pacing_score": output.overall.pacing_score,
        "prose_quality": output.overall.prose_quality,
        "plot_progression": output.overall.plot_progression,
        "character_development": output.overall.character_development,
    }
    out_of_range = [
        f"{name}={value}" for name, value in scores.items() if not _in_score_range(value)
    ]
    if out_of_range:
        violations.append(
            Layer1Violation(
                check_id="L1-P1-scores",
                detail=f"scores outside [{_SCORE_BOUNDS[0]}, {_SCORE_BOUNDS[1]}]: "
                + ", ".join(out_of_range),
            )
        )

    excerpts = [item.text_excerpt for item in output.strengths]
    excerpts += [item.text_excerpt for item in output.feedback]
    return Layer1Report(
        phase="phase1",
        violations=violations,
        grounding=_grounding(excerpts, chapter_text),
    )


def check_phase2(output: BetaReaderPhase2Output, chapter_text: str) -> Layer1Report:
    """Run the Phase 2 (beta_reader_deepdive) Layer-1 checks (spec §5)."""
    violations: list[Layer1Violation] = []

    _append(
        violations,
        "L1-P2-enum-category",
        _enum_offenders(
            "detailed_feedback", [item.category for item in output.detailed_feedback], CATEGORIES
        ),
        CATEGORIES,
    )
    _append(
        violations,
        "L1-P2-enum-severity",
        _enum_offenders(
            "detailed_feedback", [item.severity for item in output.detailed_feedback], SEVERITIES
        ),
        SEVERITIES,
    )

    low, high = P2_FEEDBACK_BOUNDS
    if not low <= len(output.detailed_feedback) <= high:
        violations.append(
            Layer1Violation(
                check_id="L1-P2-count-feedback",
                detail=f"detailed_feedback count {len(output.detailed_feedback)} "
                f"outside [{low}, {high}]",
            )
        )
    low, high = P2_SUGGESTION_BOUNDS
    if not low <= len(output.revision_suggestions) <= high:
        violations.append(
            Layer1Violation(
                check_id="L1-P2-count-suggestions",
                detail=f"revision_suggestions count {len(output.revision_suggestions)} "
                f"outside [{low}, {high}]",
            )
        )

    blank = _blank_rows("detailed_feedback", output.detailed_feedback, ("title", "description"))
    blank += _blank_strings("revision_suggestions", output.revision_suggestions)
    if blank:
        violations.append(Layer1Violation(check_id="L1-P2-nonempty", detail="; ".join(blank)))

    if not _in_score_range(output.category_score):
        violations.append(
            Layer1Violation(
                check_id="L1-P2-score",
                detail=f"category_score={output.category_score} outside "
                f"[{_SCORE_BOUNDS[0]}, {_SCORE_BOUNDS[1]}]",
            )
        )

    excerpts = [item.text_excerpt for item in output.detailed_feedback]
    return Layer1Report(
        phase="phase2",
        violations=violations,
        grounding=_grounding(excerpts, chapter_text),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _append(
    violations: list[Layer1Violation],
    check_id: str,
    offenders: list[str],
    allowed: frozenset[str],
) -> None:
    """Append an enum violation when ``offenders`` is non-empty."""
    if not offenders:
        return
    violations.append(
        Layer1Violation(
            check_id=check_id,
            detail=f"invalid values (allowed: {sorted(allowed)}): {', '.join(offenders)}",
        )
    )


def _enum_offenders(name: str, values: list[str], allowed: frozenset[str]) -> list[str]:
    """Return ``name[i]='value'`` fragments whose value is not allowed."""
    return [f"{name}[{i}]={value!r}" for i, value in enumerate(values) if value not in allowed]


def _blank_rows(
    name: str,
    rows: Sequence[BaseModel],
    fields: tuple[str, ...],
) -> list[str]:
    """Return ``name[i] blank: <fields>`` fragments for rows with blank fields."""
    offenders: list[str] = []
    for index, row in enumerate(rows):
        blank = [field for field in fields if not str(getattr(row, field)).strip()]
        if blank:
            offenders.append(f"{name}[{index}] blank: {', '.join(blank)}")
    return offenders


def _blank_strings(name: str, values: list[str]) -> list[str]:
    """Return ``name[i] blank`` fragments for blank strings."""
    return [f"{name}[{index}] blank" for index, value in enumerate(values) if not value.strip()]


def _in_score_range(value: int) -> bool:
    low, high = _SCORE_BOUNDS
    return low <= value <= high


def _grounding(excerpts: list[str | None], chapter_text: str) -> GroundingResult:
    """Whitespace-normalized verbatim grounding over non-null excerpts."""
    non_null = [excerpt for excerpt in excerpts if excerpt is not None]
    if not non_null:
        return GroundingResult(total=0, grounded=0, fraction=None)
    normalized_chapter = _ws_normalized(chapter_text)
    grounded = sum(1 for excerpt in non_null if _ws_normalized(excerpt) in normalized_chapter)
    return GroundingResult(
        total=len(non_null),
        grounded=grounded,
        fraction=grounded / len(non_null),
    )


def _ws_normalized(text: str) -> str:
    """Collapse all whitespace runs to single spaces (spec: 'whitespace-normalized')."""
    return " ".join(text.split())
