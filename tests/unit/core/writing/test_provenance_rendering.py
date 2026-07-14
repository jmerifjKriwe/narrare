"""Provenance-annotation integration tests for writing renderers (CR-AUFG-04-01).

Verifies the opt-in ``RenderOptions.annotate_provenance`` path for:
  * ``format_entities`` (writing/_helpers.py)
  * ``format_entities_with_wiki`` (writing/context_wiki.py)
  * ``apply_tier3`` / ``apply_tier3_rendered`` (writing/_tier3_processor.py)

Backward compatibility (``options=None`` default) is a hard acceptance
criterion: output MUST be byte-identical to today.
"""

from __future__ import annotations

from narrare_core.context._render_options import RenderOptions
from narrare_core.writing._helpers import format_entities
from narrare_core.writing._tier3_processor import apply_tier3
from narrare_core.writing.context_models import KBEntity
from narrare_core.writing.context_wiki import format_entities_with_wiki

_ANNOTATE = RenderOptions(annotate_provenance=True)


def _kb(
    *,
    name: str = "Aria Thorne",
    entity_type: str = "character",
    source: str = "auto_extraction",
    confidence: float = 0.72,
    review_status: str = "pending",
    wiki_status: str | None = "fresh",
    content: str = "A reluctant hero.",
    entity_id: str = "char-1",
) -> KBEntity:
    return KBEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        content=content,
        source=source,
        confidence=confidence,
        review_status=review_status,
        wiki_status=wiki_status,
    )


# ---------------------------------------------------------------------------
# format_entities — backward compatibility (REGRESSION)
# ---------------------------------------------------------------------------


class TestFormatEntitiesBackwardCompat:
    """options=None (default) → byte-identical to pre-annotation output."""

    def test_default_text_unchanged(self) -> None:
        entity = _kb(source="auto_extraction", confidence=0.42, review_status="pending")
        rendered = format_entities([entity])
        assert rendered.text == "### Character: Aria Thorne\nA reluctant hero."

    def test_explicit_none_text_unchanged(self) -> None:
        entity = _kb(source="auto_extraction", confidence=0.42, review_status="pending")
        rendered = format_entities([entity], options=None)
        assert rendered.text == "### Character: Aria Thorne\nA reluctant hero."

    def test_default_accounting_unchanged(self) -> None:
        entity = _kb(source="auto_extraction", confidence=0.42, review_status="pending")
        rendered = format_entities([entity])
        assert rendered.preserved_fields == frozenset()
        omitted = {f for f, _ in rendered.omitted_fields}
        assert {"priority", "provenance", "review_state", "freshness", "kb_lifecycle"}.issubset(
            omitted
        )


# ---------------------------------------------------------------------------
# format_entities — annotate_provenance=True
# ---------------------------------------------------------------------------


class TestFormatEntitiesAnnotated:
    def test_bracket_appended_to_header(self) -> None:
        entity = _kb(confidence=0.72, review_status="pending")
        rendered = format_entities([entity], options=_ANNOTATE)
        assert rendered.text == (
            "### Character: Aria Thorne [auto-extracted, confidence: 0.72, pending review]\n"
            "A reluctant hero."
        )

    def test_content_unchanged(self) -> None:
        entity = _kb(confidence=0.5, review_status="endorsed", wiki_status="stale")
        rendered = format_entities([entity], options=_ANNOTATE)
        assert "A reluctant hero." in rendered.text
        # content is on its own line, untouched
        assert rendered.text.endswith("A reluctant hero.")

    def test_clean_entry_not_annotated(self) -> None:
        entity = _kb(confidence=0.95, review_status="endorsed", wiki_status="fresh")
        rendered = format_entities([entity], options=_ANNOTATE)
        assert rendered.text == "### Character: Aria Thorne\nA reluctant hero."

    def test_accounting_provenance_preserved(self) -> None:
        entity = _kb(confidence=0.5, review_status="endorsed", wiki_status="fresh")
        rendered = format_entities([entity], options=_ANNOTATE)
        assert "provenance" in rendered.preserved_fields
        # provenance moved OUT of omitted
        omitted = {f for f, _ in rendered.omitted_fields}
        assert "provenance" not in omitted

    def test_accounting_review_state_preserved_when_pending(self) -> None:
        entity = _kb(confidence=0.95, review_status="pending", wiki_status="fresh")
        rendered = format_entities([entity], options=_ANNOTATE)
        assert "review_state" in rendered.preserved_fields
        omitted = {f for f, _ in rendered.omitted_fields}
        assert "review_state" not in omitted

    def test_accounting_freshness_preserved_when_stale(self) -> None:
        # Below the high-confidence/endorsed suppression band so stale fires.
        entity = _kb(confidence=0.8, review_status="endorsed", wiki_status="stale")
        rendered = format_entities([entity], options=_ANNOTATE)
        assert "freshness" in rendered.preserved_fields
        omitted = {f for f, _ in rendered.omitted_fields}
        assert "freshness" not in omitted

    def test_accounting_batch_union(self) -> None:
        """Batch: one entry pending, one stale, one clean.
        preserved = union across batch (provenance, review_state, freshness)."""
        entries = [
            _kb(entity_id="a", confidence=0.8, review_status="pending", wiki_status="fresh"),
            _kb(entity_id="b", confidence=0.8, review_status="endorsed", wiki_status="stale"),
            _kb(entity_id="c", confidence=0.95, review_status="endorsed", wiki_status="fresh"),
        ]
        rendered = format_entities(entries, options=_ANNOTATE)
        assert {"provenance", "review_state", "freshness"}.issubset(rendered.preserved_fields)

    def test_fields_not_rendered_stay_omitted(self) -> None:
        """priority/kb_lifecycle still omitted (not rendered for any entry)."""
        entity = _kb(confidence=0.5, review_status="pending", wiki_status="stale")
        rendered = format_entities([entity], options=_ANNOTATE)
        omitted = {f for f, _ in rendered.omitted_fields}
        assert "priority" in omitted
        assert "kb_lifecycle" in omitted


# ---------------------------------------------------------------------------
# format_entities_with_wiki — annotate_provenance=True
# ---------------------------------------------------------------------------


class TestFormatEntitiesWithWikiAnnotated:
    def test_default_text_unchanged_regression(self) -> None:
        entity = _kb(confidence=0.42, review_status="pending")
        rendered, fresh, stale = format_entities_with_wiki([entity], None)
        assert rendered.text == "### Character: Aria Thorne\nA reluctant hero."
        assert fresh == 0
        assert stale == 0

    def test_explicit_none_options_unchanged(self) -> None:
        entity = _kb(confidence=0.42, review_status="pending")
        rendered, _f, _s = format_entities_with_wiki([entity], None, options=None)
        assert rendered.text == "### Character: Aria Thorne\nA reluctant hero."

    def test_bracket_appended_no_wiki(self) -> None:
        entity = _kb(confidence=0.6, review_status="endorsed", wiki_status="fresh")
        rendered, _f, _s = format_entities_with_wiki([entity], None, options=_ANNOTATE)
        assert "[auto-extracted, confidence: 0.60]" in rendered.text

    def test_return_tuple_shape_unchanged(self) -> None:
        """options gains a param but the (rendered, fresh, stale) shape is intact."""
        entity = _kb(confidence=0.6, review_status="endorsed", wiki_status="fresh")
        result = format_entities_with_wiki([entity], None, options=_ANNOTATE)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_accounting_review_state_preserved(self) -> None:
        entity = _kb(confidence=0.95, review_status="pending", wiki_status="fresh")
        rendered, _f, _s = format_entities_with_wiki([entity], None, options=_ANNOTATE)
        assert "review_state" in rendered.preserved_fields


# ---------------------------------------------------------------------------
# apply_tier3 — forwards options to format_entities_with_wiki
# ---------------------------------------------------------------------------


class TestApplyTier3ForwardsOptions:
    def _count(self, _s: str) -> int:
        return len(_s.split()) if _s else 0

    def test_default_text_unchanged_regression(self) -> None:
        entity = _kb(confidence=0.42, review_status="pending")
        result = apply_tier3([entity], limit=1000, count_tokens=self._count)
        chars_text = result[0]
        assert chars_text == "### Character: Aria Thorne\nA reluctant hero."

    def test_options_forwarded_to_rendered(self) -> None:
        """apply_tier3 forwards options so the annotation appears in output."""
        entity = _kb(confidence=0.6, review_status="endorsed", wiki_status="fresh")
        result = apply_tier3([entity], limit=1000, count_tokens=self._count, options=_ANNOTATE)
        chars_text = result[0]
        assert "[auto-extracted, confidence: 0.60]" in chars_text
