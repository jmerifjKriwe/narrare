"""Renderer accounting tests for ADR-050 P1-A."""

from __future__ import annotations

from narrare_core.context.contracts import RenderedKBContext
from narrare_core.writing._helpers import format_entities
from narrare_core.writing._relationship_format import format_relationships
from narrare_core.writing.context_models import KBEntity


def _entity() -> KBEntity:
    return KBEntity(
        entity_id="char-1",
        entity_type="character",
        name="Alice",
        content="A warrior.",
        source="auto_extraction",
        review_status="pending",
        confidence=0.42,
        status="reviewed",
    )


def test_format_entities_returns_rendered_context_with_same_text() -> None:
    rendered = format_entities([_entity()])

    assert isinstance(rendered, RenderedKBContext)
    assert rendered.text == "### Character: Alice\nA warrior."
    assert rendered.entry_count == 1


def test_format_entities_accounts_for_omitted_provenance_fields() -> None:
    rendered = format_entities([_entity()])

    omitted_fields = {field for field, _reason in rendered.omitted_fields}
    assert {"priority", "provenance", "review_state", "freshness", "kb_lifecycle"}.issubset(
        omitted_fields
    )


def test_format_relationships_returns_rendered_context_with_same_text() -> None:
    rendered = format_relationships([("Alice", "ally", "ally of", "Bob", "mutual")])

    assert isinstance(rendered, RenderedKBContext)
    assert rendered.text == "Alice → [ally of] → Bob"
    assert rendered.entry_count == 1
    assert ("provenance", "tier_does_not_require") in rendered.omitted_fields
