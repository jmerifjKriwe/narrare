"""Provenance-annotation integration tests for PromptContext._format_kb_entries.

CR-AUFG-04-01 — opt-in ``RenderOptions.annotate_provenance`` for the
``KBContextEntry`` render path. Backward compatibility is a hard acceptance
criterion: ``options=None`` (default) → byte-identical output.
"""

from __future__ import annotations

from narrare_core.context._render_options import RenderOptions
from narrare_core.prompts.context import KBContextEntry, PromptContext

_ANNOTATE = RenderOptions(annotate_provenance=True)


def _entry(
    *,
    name: str = "Aria Thorne",
    entity_type: str = "character",
    source: str = "auto_extraction",
    confidence: float = 0.72,
    review_status: str = "pending",
    freshness: str = "fresh",
    content: str = "A reluctant hero.",
) -> KBContextEntry:
    return KBContextEntry(
        entity_type=entity_type,
        name=name,
        content=content,
        source=source,
        confidence=confidence,
        review_status=review_status,
        freshness=freshness,
    )


class TestFormatKbEntriesBackwardCompat:
    """options=None (default) → byte-identical to pre-annotation output."""

    def test_default_text_unchanged(self) -> None:
        entry = _entry(source="auto_extraction", confidence=0.42, review_status="pending")
        result = PromptContext._format_kb_entries([entry])
        assert result.text == "### Character: Aria Thorne\nA reluctant hero."

    def test_explicit_none_text_unchanged(self) -> None:
        entry = _entry(source="auto_extraction", confidence=0.42, review_status="pending")
        result = PromptContext._format_kb_entries([entry], options=None)
        assert result.text == "### Character: Aria Thorne\nA reluctant hero."

    def test_default_accounting_unchanged(self) -> None:
        entry = _entry(source="auto_extraction", confidence=0.42, review_status="pending")
        result = PromptContext._format_kb_entries([entry])
        assert result.preserved_fields == frozenset()
        omitted = {f for f, _ in result.omitted_fields}
        assert {"provenance", "evidence", "review_state", "freshness"} == omitted


class TestFormatKbEntriesAnnotated:
    def test_bracket_appended_to_header(self) -> None:
        entry = _entry(confidence=0.72, review_status="pending", freshness="fresh")
        result = PromptContext._format_kb_entries([entry], options=_ANNOTATE)
        assert result.text == (
            "### Character: Aria Thorne [auto-extracted, confidence: 0.72, pending review]\n"
            "A reluctant hero."
        )

    def test_content_unchanged(self) -> None:
        entry = _entry(confidence=0.5, review_status="endorsed", freshness="stale")
        result = PromptContext._format_kb_entries([entry], options=_ANNOTATE)
        assert result.text.endswith("A reluctant hero.")

    def test_clean_entry_not_annotated(self) -> None:
        entry = _entry(confidence=0.95, review_status="endorsed", freshness="fresh")
        result = PromptContext._format_kb_entries([entry], options=_ANNOTATE)
        assert result.text == "### Character: Aria Thorne\nA reluctant hero."

    def test_stale_freshness_annotated(self) -> None:
        # Below the high-confidence/endorsed suppression band so stale fires.
        entry = _entry(confidence=0.8, review_status="endorsed", freshness="stale")
        result = PromptContext._format_kb_entries([entry], options=_ANNOTATE)
        assert "[auto-extracted, confidence: 0.80, stale]" in result.text

    def test_accounting_provenance_preserved(self) -> None:
        entry = _entry(confidence=0.5, review_status="endorsed", freshness="fresh")
        result = PromptContext._format_kb_entries([entry], options=_ANNOTATE)
        assert "provenance" in result.preserved_fields
        omitted = {f for f, _ in result.omitted_fields}
        assert "provenance" not in omitted

    def test_accounting_review_state_and_freshness_preserved(self) -> None:
        entry = _entry(confidence=0.5, review_status="pending", freshness="stale")
        result = PromptContext._format_kb_entries([entry], options=_ANNOTATE)
        assert {"provenance", "review_state", "freshness"}.issubset(result.preserved_fields)
        omitted = {f for f, _ in result.omitted_fields}
        assert omitted.isdisjoint({"provenance", "review_state", "freshness"})

    def test_evidence_stays_omitted(self) -> None:
        """evidence is not rendered by the bracket → stays omitted."""
        entry = _entry(confidence=0.5, review_status="pending", freshness="stale")
        result = PromptContext._format_kb_entries([entry], options=_ANNOTATE)
        omitted = {f for f, _ in result.omitted_fields}
        assert "evidence" in omitted

    def test_batch_union_accounting(self) -> None:
        entries = [
            _entry(name="A", confidence=0.8, review_status="pending", freshness="fresh"),
            _entry(name="B", confidence=0.8, review_status="endorsed", freshness="stale"),
            _entry(name="C", confidence=0.95, review_status="endorsed", freshness="fresh"),
        ]
        result = PromptContext._format_kb_entries(entries, options=_ANNOTATE)
        assert {"provenance", "review_state", "freshness"}.issubset(result.preserved_fields)
