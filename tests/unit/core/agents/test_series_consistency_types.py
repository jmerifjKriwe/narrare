"""Tests für SeriesConsistencyTypes — CanonConflict + SeriesConsistencyOutput + Deps.

Pure data-contract tests for the type layer of SeriesConsistencyAgent
(SERIES-004 / Spec 4 Task 1). Agent behaviour tests live in
``test_series_consistency_agent.py``.

SeriesConsistencyAgent detects contradictions between a novel's chapter text
and the series Canon KB. ``CanonConflict`` is a single contradiction;
``SeriesConsistencyOutput`` is the structured agent output (empty conflicts
list = no contradictions found).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.series_consistency_types import (
    CanonConflict,
    SeriesConsistencyDeps,
    SeriesConsistencyOutput,
)

# ---------------------------------------------------------------------------
# A. CanonConflict
# ---------------------------------------------------------------------------


class TestCanonConflict:
    """CanonConflict validates correctly."""

    def test_with_error_severity(self) -> None:
        conflict = CanonConflict(
            canon_entry_slug="character-elara-eye-color",
            canon_entry_name="Elara — Eye Color",
            chapter_text_excerpt="Elara's green eyes scanned the horizon.",
            canon_statement="Elara has blue eyes.",
            explanation="Chapter describes Elara's eyes as green; Canon records blue.",
            severity="error",
        )
        assert conflict.canon_entry_slug == "character-elara-eye-color"
        assert conflict.severity == "error"

    def test_with_warning_severity(self) -> None:
        conflict = CanonConflict(
            canon_entry_slug="world-kingdom-rulers",
            canon_entry_name="Kingdom — Rulers",
            chapter_text_excerpt="King Aldric sat on the throne.",
            canon_statement="The kingdom is ruled by Queen Branwen.",
            explanation="Chapter names a different ruler than Canon records.",
            severity="warning",
        )
        assert conflict.severity == "warning"

    def test_invalid_severity_rejected(self) -> None:
        """Only 'error' and 'warning' are valid severities (no 'info')."""
        with pytest.raises(ValidationError):
            CanonConflict(
                canon_entry_slug="slug",
                canon_entry_name="Name",
                chapter_text_excerpt="excerpt",
                canon_statement="statement",
                explanation="explanation",
                severity="info",  # type: ignore[arg-type]
            )

    def test_missing_required_field_rejected(self) -> None:
        """All fields are required — no defaults."""
        with pytest.raises(ValidationError):
            CanonConflict(  # type: ignore[call-arg]
                canon_entry_slug="slug",
                canon_entry_name="Name",
                chapter_text_excerpt="excerpt",
                canon_statement="statement",
                explanation="explanation",
                # severity missing
            )

    def test_serialization(self) -> None:
        conflict = CanonConflict(
            canon_entry_slug="slug",
            canon_entry_name="Name",
            chapter_text_excerpt="excerpt",
            canon_statement="statement",
            explanation="explanation",
            severity="error",
        )
        data = conflict.model_dump()
        assert data["severity"] == "error"
        assert data["canon_entry_slug"] == "slug"


# ---------------------------------------------------------------------------
# B. SeriesConsistencyOutput
# ---------------------------------------------------------------------------


class TestSeriesConsistencyOutput:
    """SeriesConsistencyOutput validates correctly."""

    def test_defaults(self) -> None:
        """Empty output = no contradictions found."""
        output = SeriesConsistencyOutput()
        assert output.conflicts == []
        assert output.summary == ""

    def test_with_conflicts(self) -> None:
        conflict = CanonConflict(
            canon_entry_slug="slug",
            canon_entry_name="Name",
            chapter_text_excerpt="excerpt",
            canon_statement="statement",
            explanation="explanation",
            severity="error",
        )
        output = SeriesConsistencyOutput(
            conflicts=[conflict],
            summary="One canon contradiction detected.",
        )
        assert len(output.conflicts) == 1
        assert output.conflicts[0].severity == "error"
        assert output.summary == "One canon contradiction detected."


# ---------------------------------------------------------------------------
# C. SeriesConsistencyDeps
# ---------------------------------------------------------------------------


class TestSeriesConsistencyDeps:
    """SeriesConsistencyDeps constructs and configures correctly."""

    def test_defaults(self) -> None:
        deps = SeriesConsistencyDeps()
        assert deps.canon_entries == []
        assert deps.chapter_texts == []
        assert deps.novel_title == ""

    def test_custom_values(self) -> None:
        deps = SeriesConsistencyDeps(
            canon_entries=["Canon: Elara has blue eyes.", "Canon: The kingdom is northern."],
            chapter_texts=["Chapter 1 text.", "Chapter 2 text."],
            novel_title="The Forbidden Vale",
        )
        assert deps.novel_title == "The Forbidden Vale"
        assert len(deps.canon_entries) == 2
        assert len(deps.chapter_texts) == 2

    def test_canon_entries_is_a_copy(self) -> None:
        """Deps must not retain a reference to the caller's list (defensive copy)."""
        source = ["Canon A", "Canon B"]
        deps = SeriesConsistencyDeps(canon_entries=source)
        source.append("Canon C")
        assert len(deps.canon_entries) == 2

    def test_chapter_texts_is_a_copy(self) -> None:
        """Deps must not retain a reference to the caller's list (defensive copy)."""
        source = ["Chapter 1", "Chapter 2"]
        deps = SeriesConsistencyDeps(chapter_texts=source)
        source.append("Chapter 3")
        assert len(deps.chapter_texts) == 2
