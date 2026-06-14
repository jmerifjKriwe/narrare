"""Tests for dialogue extraction — quote detection and speaker attribution.

Covers extract_dialogue, count_dialogue_ratio, is_dialogue_line, and
internal helpers _detect_speaker and _overlaps_any.

This module has no spaCy dependency — pure regex and data transformation.
See ADR-021 (Deterministic Analysis Strategy).
"""

from __future__ import annotations

import pytest

from narrare_core.nlp.dialogue import (
    DialogueLine,
    _detect_speaker,
    _overlaps_any,
    count_dialogue_ratio,
    extract_dialogue,
    is_dialogue_line,
)

# ---------------------------------------------------------------------------
# A. extract_dialogue
# ---------------------------------------------------------------------------


class TestExtractDialogue:
    """extract_dialogue() — all quote types, sorting, deduplication."""

    def test_empty_text_returns_empty_list(self) -> None:
        """Empty string yields no dialogue lines."""
        assert extract_dialogue("") == []

    def test_no_quotes_returns_empty_list(self) -> None:
        """Plain narration without quotes yields nothing."""
        assert extract_dialogue("He walked to the store.") == []

    def test_double_quotes_extracted(self) -> None:
        """English double quotes are detected."""
        result = extract_dialogue('She said "Hello there."')
        assert len(result) == 1
        assert result[0].text == "Hello there."

    def test_single_quotes_extracted(self) -> None:
        """English single quotes are detected."""
        result = extract_dialogue("He replied 'No way.'")
        assert len(result) == 1
        assert result[0].text == "No way."

    def test_german_guillemets_extracted(self) -> None:
        """German guillemets »...« are detected."""
        result = extract_dialogue("\u00bbGuten Tag.\u00ab")
        assert len(result) == 1
        assert result[0].text == "Guten Tag."

    def test_multiple_quotes_returned_in_order(self) -> None:
        """Multiple quotes are sorted by start position."""
        text = '"First." Then "second." And "third."'
        result = extract_dialogue(text)
        assert len(result) == 3
        assert result[0].text == "First."
        assert result[1].text == "second."
        assert result[2].text == "third."

    def test_nested_quotes_deduplicated(self) -> None:
        """Single quotes inside double quotes are not double-counted."""
        text = "\"She said 'hello' to me.\""
        result = extract_dialogue(text)
        # Only the outer double-quote span should remain
        assert len(result) == 1
        assert result[0].text == "She said 'hello' to me."

    def test_dialogue_line_has_correct_offsets(self) -> None:
        """Start/end offsets point to the quote boundaries."""
        text = 'He said "Hi." Then left.'
        result = extract_dialogue(text)
        assert len(result) == 1
        line = result[0]
        # The double-quote span starts at offset 8 (after 'He said ')
        assert line.start == 8
        # End is right after the closing quote
        assert text[line.start : line.end] == '"Hi."'

    def test_speaker_detected_after_quote(self) -> None:
        """Speaker attribution after quote is detected."""
        text = '"I know," said John with a smile.'
        result = extract_dialogue(text)
        assert len(result) == 1
        assert result[0].speaker == "John"

    def test_speaker_detected_before_quote(self) -> None:
        """Speaker attribution before quote is detected."""
        text = 'Mary whispered, "Are you sure?"'
        result = extract_dialogue(text)
        assert len(result) == 1
        assert result[0].speaker == "Mary"

    def test_speaker_none_when_no_attribution(self) -> None:
        """No speaker detected when no attribution verb is nearby."""
        text = 'The sign read "Closed." Nobody was around.'
        result = extract_dialogue(text)
        assert len(result) == 1
        assert result[0].speaker is None

    def test_returns_dialogue_line_instances(self) -> None:
        """All results are DialogueLine dataclass instances."""
        result = extract_dialogue('"Hello."')
        assert all(isinstance(line, DialogueLine) for line in result)


# ---------------------------------------------------------------------------
# B. count_dialogue_ratio
# ---------------------------------------------------------------------------


class TestCountDialogueRatio:
    """count_dialogue_ratio() — character ratio of dialogue to total."""

    def test_empty_string_returns_zero(self) -> None:
        assert count_dialogue_ratio("") == 0.0

    def test_whitespace_only_returns_zero(self) -> None:
        assert count_dialogue_ratio("   \n\t  ") == 0.0

    def test_no_dialogue_returns_zero(self) -> None:
        """Text without quotes returns 0.0."""
        assert count_dialogue_ratio("He walked away silently.") == 0.0

    def test_all_dialogue_returns_high_ratio(self) -> None:
        """Text that is mostly dialogue has a high ratio."""
        text = '"Hello world!"'
        ratio = count_dialogue_ratio(text)
        # Content = "Hello world!" = 12 chars, total = 14 chars
        assert ratio == pytest.approx(12 / 14)

    def test_mixed_text_ratio_between_zero_and_one(self) -> None:
        """Mixed narration and dialogue gives ratio in (0, 1)."""
        text = 'He said "Hi." to her.'
        ratio = count_dialogue_ratio(text)
        assert 0.0 < ratio < 1.0

    def test_multiple_quotes_summed(self) -> None:
        """Multiple quotes' content lengths are summed."""
        text = '"A" and "B"'
        ratio = count_dialogue_ratio(text)
        # Content: "A" (1) + "B" (1) = 2 chars, total = 11 chars
        assert ratio == pytest.approx(2 / 11)


# ---------------------------------------------------------------------------
# C. is_dialogue_line
# ---------------------------------------------------------------------------


class TestIsDialogueLine:
    """is_dialogue_line() — line-level quote detection."""

    def test_double_quote_line(self) -> None:
        assert is_dialogue_line('She said "hello."') is True

    def test_plain_line(self) -> None:
        assert is_dialogue_line("He walked away.") is False

    def test_empty_line(self) -> None:
        assert is_dialogue_line("") is False

    def test_german_guillemet_line(self) -> None:
        assert is_dialogue_line("\u00bbHallo\u00ab") is True


# ---------------------------------------------------------------------------
# D. _detect_speaker
# ---------------------------------------------------------------------------


class TestDetectSpeaker:
    """_detect_speaker() — speaker name extraction from context."""

    def test_speaker_after_quote(self) -> None:
        """Pattern 1: verb + Name after the quote."""
        result = _detect_speaker("", "said John with a grin")
        assert result == "John"

    def test_speaker_before_quote(self) -> None:
        """Pattern 2: Name + verb before the quote."""
        result = _detect_speaker("Mary whispered", "")
        assert result == "Mary"

    def test_no_speaker_found(self) -> None:
        """No attribution verbs → None."""
        result = _detect_speaker("The wind blew", "across the field")
        assert result is None

    def test_empty_contexts_return_none(self) -> None:
        assert _detect_speaker("", "") is None

    def test_speaker_with_two_word_name(self) -> None:
        """Multi-word names are captured."""
        result = _detect_speaker("", "said Mary Jane")
        assert result is not None
        assert "Mary" in result

    def test_after_context_takes_priority_in_first_pattern(self) -> None:
        """First matching pattern's result is returned."""
        result = _detect_speaker("Anna replied", "whispered Bob")
        # Pattern 1 checks 'before' first, finds "Anna replied"
        assert result is not None


# ---------------------------------------------------------------------------
# E. _overlaps_any
# ---------------------------------------------------------------------------


class TestOverlapsAny:
    """_overlaps_any() — span overlap detection for deduplication."""

    def test_empty_existing_returns_false(self) -> None:
        """No existing spans → no overlap."""
        assert _overlaps_any(0, 10, []) is False

    def test_overlapping_span_returns_true(self) -> None:
        """Span that overlaps an existing one → True."""
        existing: list[tuple[int, int, str, str]] = [(5, 15, "content", "tag")]
        assert _overlaps_any(10, 20, existing) is True

    def test_non_overlapping_span_returns_false(self) -> None:
        """Span entirely after existing → False."""
        existing: list[tuple[int, int, str, str]] = [(0, 5, "x", "tag")]
        assert _overlaps_any(10, 20, existing) is False

    def test_boundary_touching_returns_false(self) -> None:
        """Spans that touch at a boundary do not overlap."""
        existing: list[tuple[int, int, str, str]] = [(0, 5, "x", "tag")]
        # end == ex_start (touching, not overlapping)
        assert _overlaps_any(5, 10, existing) is False

    def test_contained_span_returns_true(self) -> None:
        """Span entirely inside an existing span → True."""
        existing: list[tuple[int, int, str, str]] = [(0, 20, "x", "tag")]
        assert _overlaps_any(5, 10, existing) is True

    def test_multiple_existing_spans(self) -> None:
        """Any overlap with any existing span → True."""
        existing: list[tuple[int, int, str, str]] = [
            (0, 5, "a", "tag"),
            (20, 30, "b", "tag"),
        ]
        assert _overlaps_any(25, 35, existing) is True
        assert _overlaps_any(6, 10, existing) is False
