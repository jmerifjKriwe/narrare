"""Unit tests for context/_provenance_annotation.py — provenance brackets.

Covers the annotation predicate, suppression rules, bracket wire format,
humanised source labels, and RULE-22 field-rendering accounting
(ADR-050 P1-A opt-in ``RenderOptions.annotate_provenance``).

Annotation predicate (annotate when NOT suppressed AND any trigger fires):
  triggers:
    1. confidence < 0.7
    2. review_status == "pending"
    3. freshness stale
    4. source != "manual" AND confidence < 0.9
  suppress: source == "manual" | (confidence >= 0.9 AND review_status == "endorsed")

Trigger #4 (Reading A) ensures every non-manual entry below 0.9 confidence
is visibly marked so the LLM can distinguish it from curated manual facts.
The original "0.70 → not annotated" boundary was source-unaware; the
boundaries here are source-aware (manual always suppresses).
"""

from __future__ import annotations

from narrare_core.context._provenance_annotation import (
    ProvenanceAnnotation,
    compute_provenance_annotation,
    humanise_source,
)


def _ann(
    *,
    source: str = "auto_extraction",
    confidence: float = 0.95,
    review_status: str = "endorsed",
    freshness: str = "fresh",
) -> ProvenanceAnnotation:
    return compute_provenance_annotation(
        source=source, confidence=confidence, review_status=review_status, freshness=freshness
    )


# ---------------------------------------------------------------------------
# humanise_source
# ---------------------------------------------------------------------------


class TestHumaniseSource:
    def test_auto_extraction_humanised(self) -> None:
        assert humanise_source("auto_extraction") == "auto-extracted"

    def test_imported_humanised(self) -> None:
        assert humanise_source("imported") == "imported"

    def test_wiki_generated_humanised(self) -> None:
        assert humanise_source("wiki_generated") == "wiki-generated"

    def test_manual_humanised(self) -> None:
        assert humanise_source("manual") == "manual"

    def test_unknown_source_passes_through(self) -> None:
        assert humanise_source("curated") == "curated"


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


class TestSuppression:
    """No annotation when suppressed."""

    def test_manual_suppressed_even_at_low_confidence(self) -> None:
        result = _ann(source="manual", confidence=0.42, review_status="pending", freshness="stale")
        assert result.bracket is None
        assert result.rendered_fields == frozenset()

    def test_high_confidence_endorsed_suppressed(self) -> None:
        result = _ann(confidence=0.9, review_status="endorsed")
        assert result.bracket is None

    def test_clean_non_manual_not_annotated(self) -> None:
        """Non-manual, >=0.9, endorsed, fresh → no trigger → not annotated."""
        result = _ann(confidence=0.9, review_status="endorsed", freshness="fresh")
        assert result.bracket is None


# ---------------------------------------------------------------------------
# Source-aware threshold boundaries
# ---------------------------------------------------------------------------


class TestSourceAwareBoundaries:
    """Annotation boundaries are source-aware (Reading A).

    The original ``0.70 → not annotated`` boundary ignored ``source`` and
    therefore contradicted trigger #4 (``source != "manual" AND
    confidence < 0.9``). Manual sources always suppress; non-manual sources
    annotate below 0.9 even when >= 0.7. See the predicate table in the
    module docstring.
    """

    # --- trigger 1: confidence < 0.7 ---
    def test_069_auto_extraction_annotated(self) -> None:
        result = _ann(
            source="auto_extraction", confidence=0.69, review_status="endorsed", freshness="fresh"
        )
        assert result.bracket is not None
        assert "confidence: 0.69" in result.bracket

    # --- manual suppression overrides every trigger ---
    def test_070_manual_not_annotated(self) -> None:
        result = _ann(source="manual", confidence=0.70, review_status="endorsed", freshness="fresh")
        assert result.bracket is None

    def test_069_manual_not_annotated(self) -> None:
        """Manual suppresses even when a trigger fires (here trigger 1)."""
        result = _ann(source="manual", confidence=0.69, review_status="endorsed", freshness="fresh")
        assert result.bracket is None

    def test_085_manual_pending_not_annotated(self) -> None:
        """Manual suppresses even when a trigger fires (here triggers 2 & 4)."""
        result = _ann(source="manual", confidence=0.85, review_status="pending", freshness="fresh")
        assert result.bracket is None

    # --- trigger 4: source != "manual" AND confidence < 0.9 ---
    def test_070_auto_extraction_annotated(self) -> None:
        """0.70 is not below 0.7, but trigger 4 fires (0.70 < 0.9, non-manual)."""
        result = _ann(
            source="auto_extraction", confidence=0.70, review_status="endorsed", freshness="fresh"
        )
        assert result.bracket is not None
        assert "confidence: 0.70" in result.bracket

    def test_085_auto_extraction_annotated(self) -> None:
        """0.85 is well below 0.9 → trigger 4 fires."""
        result = _ann(
            source="auto_extraction", confidence=0.85, review_status="endorsed", freshness="fresh"
        )
        assert result.bracket is not None
        assert "confidence: 0.85" in result.bracket

    # --- suppression band: confidence >= 0.9 AND endorsed ---
    def test_090_auto_extraction_endorsed_not_annotated(self) -> None:
        """Exactly 0.9, endorsed → suppressed (>= 0.9 AND endorsed)."""
        result = _ann(
            source="auto_extraction", confidence=0.90, review_status="endorsed", freshness="fresh"
        )
        assert result.bracket is None

    def test_095_auto_extraction_endorsed_not_annotated(self) -> None:
        result = _ann(
            source="auto_extraction", confidence=0.95, review_status="endorsed", freshness="fresh"
        )
        assert result.bracket is None

    # --- suppression needs endorsed: pending overrides the >=0.9 band ---
    def test_095_auto_extraction_pending_annotated(self) -> None:
        """0.95, pending: trigger 2 fires; suppression requires endorsed."""
        result = _ann(
            source="auto_extraction", confidence=0.95, review_status="pending", freshness="fresh"
        )
        assert result.bracket is not None
        assert "pending review" in result.bracket

    # --- multiple triggers + bracket content ---
    def test_050_auto_extraction_endorsed_stale_annotated(self) -> None:
        """Triggers 1, 3 and 4 all fire; bracket surfaces 'stale'."""
        result = _ann(
            source="auto_extraction", confidence=0.50, review_status="endorsed", freshness="stale"
        )
        assert result.bracket is not None
        assert "stale" in result.bracket


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------


class TestReviewStatusTrigger:
    def test_pending_shows_pending_review(self) -> None:
        result = _ann(confidence=0.95, review_status="pending", freshness="fresh")
        assert result.bracket is not None
        assert "pending review" in result.bracket

    def test_rejected_shown_when_annotated_for_other_reason(self) -> None:
        """rejected alone does not trigger annotation; but when annotated
        for another reason (e.g. low confidence), 'review rejected' shows."""
        result = _ann(confidence=0.5, review_status="rejected", freshness="fresh")
        assert result.bracket is not None
        assert "review rejected" in result.bracket

    def test_rejected_high_confidence_not_annotated(self) -> None:
        """rejected + high confidence + not stale → not annotated (no trigger)."""
        result = _ann(confidence=0.95, review_status="rejected", freshness="fresh")
        assert result.bracket is None


class TestFreshnessTrigger:
    def test_stale_shows_stale(self) -> None:
        # Use confidence below the high-confidence/endorsed suppression band
        # so the stale trigger is the sole annotation cause.
        result = _ann(confidence=0.8, review_status="endorsed", freshness="stale")
        assert result.bracket is not None
        assert "stale" in result.bracket

    def test_fresh_not_annotated_for_freshness(self) -> None:
        result = _ann(confidence=0.95, review_status="endorsed", freshness="fresh")
        assert result.bracket is None

    def test_stale_suppressed_when_high_confidence_endorsed(self) -> None:
        """Suppression (>=0.9 AND endorsed) takes precedence over the stale
        trigger — trusted entries do not surface wiki-summary staleness."""
        result = _ann(confidence=0.95, review_status="endorsed", freshness="stale")
        assert result.bracket is None


# ---------------------------------------------------------------------------
# Bracket wire format: field order + formatting
# ---------------------------------------------------------------------------


class TestBracketFormat:
    def test_full_bracket_low_confidence_pending_stale(self) -> None:
        """Fixed order: source, confidence, review_status, freshness."""
        result = _ann(
            source="auto_extraction", confidence=0.5, review_status="pending", freshness="stale"
        )
        assert result.bracket == "[auto-extracted, confidence: 0.50, pending review, stale]"

    def test_confidence_two_decimals(self) -> None:
        # 0.6789 → "confidence: 0.68" (truncated to two decimals).
        low = _ann(confidence=0.6789, review_status="endorsed", freshness="fresh")
        assert low.bracket is not None
        assert "confidence: 0.68" in low.bracket
        # 0.723 is above 0.7 but below 0.9 → trigger 4 fires (non-manual).
        mid = _ann(confidence=0.723, review_status="endorsed", freshness="fresh")
        assert mid.bracket is not None
        assert "confidence: 0.72" in mid.bracket

    def test_imported_source_label(self) -> None:
        result = _ann(
            source="imported", confidence=0.5, review_status="endorsed", freshness="fresh"
        )
        assert result.bracket is not None
        assert result.bracket.startswith("[imported,")
        assert "pending" not in result.bracket
        assert "stale" not in result.bracket

    def test_wiki_generated_source_label(self) -> None:
        result = _ann(
            source="wiki_generated", confidence=0.5, review_status="endorsed", freshness="fresh"
        )
        assert result.bracket is not None
        assert result.bracket.startswith("[wiki-generated,")

    def test_source_always_shown_when_annotated(self) -> None:
        """Every annotated entry is non-manual (manual suppressed) so source
        is always rendered — provenance is always in rendered_fields."""
        result = _ann(confidence=0.5, review_status="endorsed", freshness="fresh")
        assert "provenance" in result.rendered_fields

    def test_pending_only_bracket(self) -> None:
        result = _ann(confidence=0.95, review_status="pending", freshness="fresh")
        # source + confidence + pending review
        assert result.bracket == "[auto-extracted, confidence: 0.95, pending review]"


# ---------------------------------------------------------------------------
# RULE-22 field-rendering accounting
# ---------------------------------------------------------------------------


class TestRenderedFieldsAccounting:
    """rendered_fields reports which ProvenanceField literals the bracket
    actually rendered — consumed by renderers to move fields from
    omitted_fields to preserved_fields (batch-level union)."""

    def test_low_confidence_renders_provenance_only(self) -> None:
        result = _ann(confidence=0.5, review_status="endorsed", freshness="fresh")
        assert result.rendered_fields == frozenset({"provenance"})

    def test_trigger4_renders_provenance_only(self) -> None:
        """Trigger #4 fires alone (0.85 < 0.9, non-manual, endorsed, fresh):
        source+confidence render, so ``provenance`` moves to
        ``preserved_fields`` (RULE-22 accounting recomputes with #4 active)."""
        result = _ann(
            source="auto_extraction", confidence=0.85, review_status="endorsed", freshness="fresh"
        )
        assert result.bracket is not None
        assert result.rendered_fields == frozenset({"provenance"})

    def test_pending_renders_provenance_and_review_state(self) -> None:
        result = _ann(confidence=0.95, review_status="pending", freshness="fresh")
        assert result.rendered_fields == frozenset({"provenance", "review_state"})

    def test_stale_renders_provenance_and_freshness(self) -> None:
        # Below the high-confidence/endorsed suppression band so stale fires.
        result = _ann(confidence=0.8, review_status="endorsed", freshness="stale")
        assert result.rendered_fields == frozenset({"provenance", "freshness"})

    def test_all_three_rendered(self) -> None:
        result = _ann(confidence=0.5, review_status="pending", freshness="stale")
        assert result.rendered_fields == frozenset({"provenance", "review_state", "freshness"})

    def test_not_annotated_renders_nothing(self) -> None:
        result = _ann(confidence=0.95, review_status="endorsed", freshness="fresh")
        assert result.rendered_fields == frozenset()

    def test_rendered_fields_type(self) -> None:
        result = _ann(confidence=0.5, review_status="endorsed", freshness="fresh")
        for f in result.rendered_fields:
            assert isinstance(f, str)
            assert f in {
                "provenance",
                "review_state",
                "freshness",
                "evidence",
                "priority",
                "kb_lifecycle",
            }
