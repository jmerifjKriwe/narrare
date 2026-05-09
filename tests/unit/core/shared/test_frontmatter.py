"""Tests for shared/frontmatter.py"""

from __future__ import annotations

import pytest

from narrare_core.shared.frontmatter import (
    extract_section,
    parse_frontmatter,
    strip_frontmatter,
)


class TestParseFrontmatter:
    def test_parses_yaml_metadata(self) -> None:
        text = "---\ntitle: My Novel\nstatus: draft\n---\n\nContent here."
        result = parse_frontmatter(text)
        assert result.metadata["title"] == "My Novel"
        assert result.metadata["status"] == "draft"
        assert result.content == "Content here."
        assert result.has_frontmatter is True

    def test_no_frontmatter_returns_empty_metadata(self) -> None:
        text = "Just plain content."
        result = parse_frontmatter(text)
        assert result.metadata == {}
        assert result.content == "Just plain content."
        assert result.has_frontmatter is False

    def test_get_returns_default_for_missing_key(self) -> None:
        result = parse_frontmatter("---\nkey: val\n---\n")
        assert result.get("missing", "default") == "default"

    def test_require_raises_for_missing_key(self) -> None:
        result = parse_frontmatter("---\nkey: val\n---\n")
        with pytest.raises(KeyError, match="required_key"):
            result.require("required_key")

    def test_invalid_yaml_returns_empty_metadata(self) -> None:
        text = "---\n: invalid: yaml: {\n---\n\nContent."
        result = parse_frontmatter(text)
        assert result.metadata == {}
        assert result.has_frontmatter is True


class TestStripFrontmatter:
    def test_strips_frontmatter(self) -> None:
        text = "---\ntitle: Test\n---\n\nContent."
        assert strip_frontmatter(text) == "Content."

    def test_no_frontmatter_unchanged(self) -> None:
        text = "Plain content."
        assert strip_frontmatter(text) == "Plain content."


class TestExtractSection:
    def test_extracts_named_section(self) -> None:
        text = "## System Prompt\n\nYou are helpful.\n\n## First Message\n\nHello!"
        result = extract_section(text, "System Prompt")
        assert result == "You are helpful."

    def test_extracts_second_section(self) -> None:
        text = "## System Prompt\n\nSystem.\n\n## First Message\n\nHello!"
        result = extract_section(text, "First Message")
        assert result == "Hello!"

    def test_returns_none_for_missing_section(self) -> None:
        text = "## System Prompt\n\nContent."
        assert extract_section(text, "Nonexistent") is None

    def test_case_insensitive(self) -> None:
        text = "## SYSTEM PROMPT\n\nContent."
        result = extract_section(text, "system prompt")
        assert result == "Content."
