"""Tests for CR-AUFG-04: KB context metadata fields and validation.

Covers:
1. KBContextEntry new fields (source, evidence, confidence, review_status, freshness)
2. validate_world_context() with valid, empty, and malformed inputs
"""

from __future__ import annotations

from narrare_core.prompts.context import KBContextEntry, validate_world_context

# ---------------------------------------------------------------------------
# KBContextEntry — new metadata fields
# ---------------------------------------------------------------------------


class TestKBContextEntryMetadataDefaults:
    """KBContextEntry metadata fields have correct defaults."""

    def test_source_defaults_to_manual(self) -> None:
        entry = KBContextEntry(entity_type="character", name="Alice", content="A warrior.")
        assert entry.source == "manual"

    def test_evidence_defaults_to_empty(self) -> None:
        entry = KBContextEntry(entity_type="character", name="Alice", content="A warrior.")
        assert entry.evidence == ""

    def test_confidence_defaults_to_one(self) -> None:
        entry = KBContextEntry(entity_type="character", name="Alice", content="A warrior.")
        assert entry.confidence == 1.0

    def test_review_status_defaults_to_endorsed(self) -> None:
        entry = KBContextEntry(entity_type="character", name="Alice", content="A warrior.")
        assert entry.review_status == "endorsed"

    def test_freshness_defaults_to_fresh(self) -> None:
        entry = KBContextEntry(entity_type="character", name="Alice", content="A warrior.")
        assert entry.freshness == "fresh"


class TestKBContextEntryMetadataCustom:
    """KBContextEntry metadata fields can be set to non-default values."""

    def test_auto_extraction_source(self) -> None:
        entry = KBContextEntry(
            entity_type="character",
            name="Bob",
            content="A wizard.",
            source="auto_extraction",
            confidence=0.75,
            review_status="pending",
        )
        assert entry.source == "auto_extraction"
        assert entry.confidence == 0.75
        assert entry.review_status == "pending"

    def test_imported_source(self) -> None:
        entry = KBContextEntry(
            entity_type="location",
            name="Castle",
            content="An old castle.",
            source="imported",
        )
        assert entry.source == "imported"

    def test_wiki_generated_source(self) -> None:
        entry = KBContextEntry(
            entity_type="faction",
            name="The Guild",
            content="A trading guild.",
            source="wiki_generated",
            freshness="stale",
        )
        assert entry.source == "wiki_generated"
        assert entry.freshness == "stale"

    def test_with_evidence(self) -> None:
        entry = KBContextEntry(
            entity_type="character",
            name="Eve",
            content="A rogue.",
            evidence="Mentioned in chapter 3 dialogue",
        )
        assert entry.evidence == "Mentioned in chapter 3 dialogue"

    def test_rejected_review_status(self) -> None:
        entry = KBContextEntry(
            entity_type="character",
            name="Mallory",
            content="An antagonist.",
            review_status="rejected",
        )
        assert entry.review_status == "rejected"


# ---------------------------------------------------------------------------
# validate_world_context
# ---------------------------------------------------------------------------


class TestValidateWorldContext:
    """validate_world_context returns warnings for poorly structured context."""

    def test_valid_structured_context_returns_empty(self) -> None:
        ctx = (
            "### Characters\n"
            "- Alice: A brave warrior from the northern tribes\n"
            "- Bob: A cunning rogue\n\n"
            "### Locations\n"
            "- The Dark Forest: A mysterious woodland"
        )
        warnings = validate_world_context(ctx)
        assert warnings == []

    def test_valid_with_entity_keyword(self) -> None:
        ctx = "The main character is Alice, who lives in the castle."
        warnings = validate_world_context(ctx)
        assert warnings == []

    def test_valid_with_colon_structure(self) -> None:
        ctx = "Name: Alice\nRole: Warrior\nLocation: Castle"
        warnings = validate_world_context(ctx)
        assert warnings == []

    def test_empty_string_returns_warning(self) -> None:
        warnings = validate_world_context("")
        assert len(warnings) == 1
        assert "empty" in warnings[0]

    def test_whitespace_only_returns_warning(self) -> None:
        warnings = validate_world_context("   \n\t  ")
        assert len(warnings) == 1
        assert "empty" in warnings[0]

    def test_unstructured_text_returns_warning(self) -> None:
        ctx = "The quick brown fox jumps over the lazy dog without any structure."
        warnings = validate_world_context(ctx)
        assert len(warnings) == 1
        assert "unstructured" in warnings[0].lower()

    def test_heading_based_structure_is_valid(self) -> None:
        ctx = "## World Overview\nSome description of the world."
        warnings = validate_world_context(ctx)
        assert warnings == []

    def test_bullet_list_structure_is_valid(self) -> None:
        ctx = "- Item one\n- Item two\n- Item three"
        warnings = validate_world_context(ctx)
        assert warnings == []

    def test_entity_keyword_makes_unstructured_valid(self) -> None:
        ctx = "This is a story about a character named Alice."
        warnings = validate_world_context(ctx)
        assert warnings == []

    def test_location_keyword_makes_unstructured_valid(self) -> None:
        ctx = "The story takes place in a location called the Dark Tower."
        warnings = validate_world_context(ctx)
        assert warnings == []

    def test_newline_paragraph_structure_is_valid(self) -> None:
        ctx = "First paragraph about the world.\n\nSecond paragraph about the people."
        warnings = validate_world_context(ctx)
        assert warnings == []
