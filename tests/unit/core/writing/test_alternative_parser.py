"""Tests for writing/alternative_parser.py — structured alternative parsing.

Covers:
1. Well-formed multi-alternative (3 alternatives with labels)
2. Single alternative
3. No tags (fallback to entire text as single alternative)
4. Tag-like content within alternatives (not at line boundary)
5. Fewer alternatives than count
6. Labels with special characters (commas, quotes)
7. Empty content between tags
8. Empty input string
9. Malformed tags (missing closing tag)
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from narrare_core.writing.alternative_parser import Alternative, parse_alternatives

# ---------------------------------------------------------------------------
# Well-formed multi-alternative
# ---------------------------------------------------------------------------


class TestWellFormedMultiple:
    def test_three_alternatives_with_labels(self) -> None:
        text = (
            "<scratchpad>Analysis here</scratchpad>\n"
            '<alternative label="Dramatic rewrite">\n'
            "The storm crashed over the harbor.\n"
            "</alternative>\n"
            '<alternative label="Quiet rewrite">\n'
            "The rain fell softly on the harbor.\n"
            "</alternative>\n"
            '<alternative label="Poetic rewrite">\n'
            "The harbor drank the rain like a dying man drinks water.\n"
            "</alternative>"
        )
        result = parse_alternatives(text)
        assert len(result) == 3
        assert result[0].label == "Dramatic rewrite"
        assert "storm crashed" in result[0].text
        assert result[1].label == "Quiet rewrite"
        assert "rain fell softly" in result[1].text
        assert result[2].label == "Poetic rewrite"
        assert "harbor drank" in result[2].text

    def test_preserves_multiline_content(self) -> None:
        text = (
            '<alternative label="Full scene">\n'
            "The door opened. Light spilled in.\n"
            "A figure stood in the doorway.\n"
            "</alternative>"
        )
        result = parse_alternatives(text)
        assert len(result) == 1
        assert "door opened" in result[0].text
        assert "figure stood" in result[0].text


# ---------------------------------------------------------------------------
# Single alternative
# ---------------------------------------------------------------------------


class TestSingleAlternative:
    def test_single_well_formed(self) -> None:
        text = '<alternative label="Rewritten text">\nThe rewritten passage.\n</alternative>'
        result = parse_alternatives(text)
        assert len(result) == 1
        assert result[0].label == "Rewritten text"
        assert "rewritten passage" in result[0].text

    def test_single_with_scratchpad_before(self) -> None:
        text = (
            "<scratchpad>Analyzing the original text...</scratchpad>\n"
            '<alternative label="Improved version">\n'
            "Better text.\n"
            "</alternative>"
        )
        result = parse_alternatives(text)
        assert len(result) == 1
        assert result[0].label == "Improved version"
        assert "Better text" in result[0].text


# ---------------------------------------------------------------------------
# No tags — fallback
# ---------------------------------------------------------------------------


class TestFallback:
    def test_no_tags_returns_entire_text(self) -> None:
        text = "This is just plain text without any alternative tags."
        result = parse_alternatives(text)
        assert len(result) == 1
        assert result[0].label == "Rewritten text"
        assert result[0].text == text

    def test_empty_string_returns_empty_list(self) -> None:
        result = parse_alternatives("")
        assert result == []


# ---------------------------------------------------------------------------
# Tag-like content within alternatives (not at line boundary)
# ---------------------------------------------------------------------------


class TestTagLikeContent:
    def test_inline_alternative_text_not_recognized(self) -> None:
        """The word <alternative in prose (not at line start) is not a tag."""
        text = (
            "The author wrote <alternative label='fake'> within the prose "
            "but this should not be parsed as a tag because it's inline."
        )
        result = parse_alternatives(text)
        # Falls back to entire text as single alternative
        assert len(result) == 1
        assert result[0].label == "Rewritten text"

    def test_malicious_tag_within_content(self) -> None:
        """Content that looks like an alternative tag but is mid-line."""
        text = (
            '<alternative label="Real rewrite">\n'
            'He said <alternative label="nested"> is not a tag here.\n'
            "</alternative>"
        )
        result = parse_alternatives(text)
        assert len(result) == 1
        assert "nested" in result[0].text

    def test_angle_brackets_in_prose_preserved(self) -> None:
        """Prose using angle brackets for comparison (e.g., < 3) is fine."""
        text = (
            '<alternative label="Version">\n'
            'She counted: x <alternative label="not this"> y. No, wait: x < 3.\n'
            "</alternative>"
        )
        result = parse_alternatives(text)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Labels with special characters
# ---------------------------------------------------------------------------


class TestLabelSpecialCharacters:
    def test_label_with_comma(self) -> None:
        text = '<alternative label="Darker, more dramatic">\nDark text.\n</alternative>'
        result = parse_alternatives(text)
        assert result[0].label == "Darker, more dramatic"

    def test_label_with_quotes_escaped(self) -> None:
        """Labels use double quotes — single quotes inside are fine."""
        text = "<alternative label=\"The 'dramatic' version\">\nDramatic text.\n</alternative>"
        result = parse_alternatives(text)
        assert result[0].label == "The 'dramatic' version"

    def test_label_with_dash_and_parens(self) -> None:
        text = '<alternative label="Show-don\'t-tell (improved)">\nShown text.\n</alternative>'
        result = parse_alternatives(text)
        assert result[0].label == "Show-don't-tell (improved)"


# ---------------------------------------------------------------------------
# Empty content between tags
# ---------------------------------------------------------------------------


class TestEmptyContent:
    def test_empty_content_between_tags(self) -> None:
        text = (
            '<alternative label="Empty">\n'
            "</alternative>\n"
            '<alternative label="Not empty">\n'
            "Some content.\n"
            "</alternative>"
        )
        result = parse_alternatives(text)
        assert len(result) == 2
        assert result[0].text == ""
        assert result[1].text == "Some content."

    def test_whitespace_only_content(self) -> None:
        text = '<alternative label="Whitespace">\n   \n\n</alternative>'
        result = parse_alternatives(text)
        assert len(result) == 1
        assert result[0].text == ""  # stripped


# ---------------------------------------------------------------------------
# Malformed tags
# ---------------------------------------------------------------------------


class TestMalformedTags:
    def test_missing_closing_tag(self) -> None:
        """If opening tag found but no closing tag, rest is the content."""
        text = '<alternative label="No close">\nThis text continues without a closing tag.'
        result = parse_alternatives(text)
        assert len(result) == 1
        assert result[0].label == "No close"
        assert "continues without a closing tag" in result[0].text

    def test_closing_tag_without_opening(self) -> None:
        """Stray closing tag without matching opening → fallback."""
        text = "Some text</alternative>more text"
        result = parse_alternatives(text)
        assert len(result) == 1
        assert result[0].label == "Rewritten text"

    def test_missing_label_attribute(self) -> None:
        """Opening tag without label attribute is not matched."""
        text = "<alternative>\nContent here.\n</alternative>"
        result = parse_alternatives(text)
        # Fallback — label-less tag not matched by our regex
        assert len(result) == 1
        assert result[0].label == "Rewritten text"

    def test_second_alternative_missing_closing(self) -> None:
        """First closes normally, second is malformed."""
        text = (
            '<alternative label="First">\n'
            "First content.\n"
            "</alternative>\n"
            '<alternative label="Second">\n'
            "Second content runs on..."
        )
        result = parse_alternatives(text)
        assert len(result) == 2
        assert result[0].label == "First"
        assert result[0].text == "First content."
        assert result[1].label == "Second"
        assert "runs on" in result[1].text


# ---------------------------------------------------------------------------
# Alternative dataclass
# ---------------------------------------------------------------------------


class TestAlternativeDataclass:
    def test_frozen(self) -> None:
        alt = Alternative(label="test", text="content")
        with pytest.raises(AttributeError):
            cast("Any", alt).label = "changed"

    def test_equality(self) -> None:
        a1 = Alternative(label="test", text="content")
        a2 = Alternative(label="test", text="content")
        assert a1 == a2
