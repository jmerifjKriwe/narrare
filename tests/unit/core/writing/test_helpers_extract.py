"""Tests for _helpers.py — frontmatter reference extraction.

Covers:
1. Empty frontmatter returns empty set (line 43)
2. No frontmatter parsed returns empty set (line 48)
3. References with list values
4. References with single values
5. format_entities with empty list
"""

from __future__ import annotations

from narrare_core.writing._helpers import (
    extract_frontmatter_references,
    format_entities,
)
from narrare_core.writing.context_models import KBEntity


class TestExtractFrontmatterReferences:
    """extract_frontmatter_references coverage."""

    def test_empty_frontmatter_returns_empty_set(self) -> None:
        result = extract_frontmatter_references("")
        assert result == set()

    def test_no_frontmatter_parsed_returns_empty_set(self) -> None:
        """Plain text without frontmatter delimiters (line 48)."""
        result = extract_frontmatter_references("just plain text")
        assert result == set()

    def test_single_reference_extracted(self) -> None:
        frontmatter = "---\npov_character: char-123\n---"
        result = extract_frontmatter_references(frontmatter)
        assert result == {"char-123"}

    def test_list_references_extracted(self) -> None:
        frontmatter = "---\ncharacters:\n  - char-1\n  - char-2\n---"
        result = extract_frontmatter_references(frontmatter)
        assert result == {"char-1", "char-2"}


class TestFormatEntities:
    """format_entities coverage."""

    def test_empty_list_returns_empty_string(self) -> None:
        result = format_entities([])
        assert result == ""

    def test_single_entity_formatted(self) -> None:
        entity = KBEntity(
            entity_id="e1",
            name="Anna",
            entity_type="character",
            content="Description of Anna.",
        )
        result = format_entities([entity])
        assert "Character: Anna" in result
        assert "Description of Anna." in result
