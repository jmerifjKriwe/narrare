"""Tests for context/name_matching.py — Entity name matching."""

from __future__ import annotations

from narrare_core.context.name_matching import match_entity_names

# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestMatchEntityNamesBasic:
    """Basic name matching scenarios."""

    def test_exact_match(self) -> None:
        text = "Aria walked through the forest."
        result = match_entity_names(text, ["Aria"])
        assert result == {"Aria"}

    def test_case_insensitive_match(self) -> None:
        text = "aria walked through the forest."
        result = match_entity_names(text, ["Aria"])
        assert result == {"Aria"}

    def test_case_insensitive_upper(self) -> None:
        text = "ARIA walked through the forest."
        result = match_entity_names(text, ["Aria"])
        assert result == {"Aria"}

    def test_multiple_matches(self) -> None:
        text = "Aria and Bran travelled to the Castle."
        result = match_entity_names(text, ["Aria", "Bran", "Castle", "Guild"])
        assert result == {"Aria", "Bran", "Castle"}

    def test_no_matches(self) -> None:
        text = "The wind howled through the valley."
        result = match_entity_names(text, ["Aria", "Bran"])
        assert result == set()


# ---------------------------------------------------------------------------
# Word boundary
# ---------------------------------------------------------------------------


class TestMatchEntityNamesWordBoundary:
    """Word boundary prevents partial matches."""

    def test_no_partial_match_prefix(self) -> None:
        """'Arianne' should not match 'Aria'."""
        text = "Arianne walked through the forest."
        result = match_entity_names(text, ["Aria"])
        assert result == set()

    def test_no_partial_match_suffix(self) -> None:
        """'Valaria' should not match 'Aria'."""
        text = "Valaria walked through the forest."
        result = match_entity_names(text, ["Aria"])
        assert result == set()

    def test_match_with_punctuation(self) -> None:
        """Name followed by punctuation should still match."""
        text = "Aria, Bran, and the Guild."
        result = match_entity_names(text, ["Aria", "Bran", "Guild"])
        assert result == {"Aria", "Bran", "Guild"}

    def test_match_at_end_of_sentence(self) -> None:
        text = "The hero was Aria."
        result = match_entity_names(text, ["Aria"])
        assert result == {"Aria"}

    def test_match_in_parentheses(self) -> None:
        text = "She saw (Aria) in the crowd."
        result = match_entity_names(text, ["Aria"])
        assert result == {"Aria"}


# ---------------------------------------------------------------------------
# Minimum name length
# ---------------------------------------------------------------------------


class TestMatchEntityNamesMinLength:
    """Short names are skipped to avoid false positives."""

    def test_short_name_skipped_default(self) -> None:
        """Names shorter than 3 chars are skipped by default."""
        text = "Al went to the castle."
        result = match_entity_names(text, ["Al"])
        assert result == set()

    def test_min_name_length_override(self) -> None:
        """Override min_name_length to allow shorter names."""
        text = "Al went to the castle."
        result = match_entity_names(text, ["Al"], min_name_length=2)
        assert result == {"Al"}

    def test_exactly_at_min_length(self) -> None:
        """Name exactly at min_name_length is included."""
        text = "Bob went to the castle."
        result = match_entity_names(text, ["Bob"], min_name_length=3)
        assert result == {"Bob"}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestMatchEntityNamesEdgeCases:
    """Empty inputs and special characters."""

    def test_empty_content_returns_empty(self) -> None:
        result = match_entity_names("", ["Aria"])
        assert result == set()

    def test_none_equivalent_empty_names(self) -> None:
        result = match_entity_names("Aria walked.", [])
        assert result == set()

    def test_special_regex_characters_in_name(self) -> None:
        """Names with regex special chars like 'Dr. Smith' are escaped."""
        text = "Dr. Smith arrived at the castle."
        result = match_entity_names(text, ["Dr. Smith"])
        assert result == {"Dr. Smith"}

    def test_name_with_parentheses(self) -> None:
        """Names with parentheses are escaped."""
        text = "The Order (dark) attacked."
        result = match_entity_names(text, ["The Order (dark)"])
        assert result == {"The Order (dark)"}

    def test_name_with_hyphen(self) -> None:
        text = "Jean-Luc commanded the ship."
        result = match_entity_names(text, ["Jean-Luc"])
        assert result == {"Jean-Luc"}

    def test_repeated_name_returns_single(self) -> None:
        """Same name appearing multiple times returns a single entry."""
        text = "Aria saw Aria and told Aria."
        result = match_entity_names(text, ["Aria"])
        assert result == {"Aria"}

    def test_unicode_name(self) -> None:
        text = "München was beautiful in winter."
        result = match_entity_names(text, ["München"])
        assert result == {"München"}
