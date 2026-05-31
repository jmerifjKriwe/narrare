"""Tests for text_reconstructor.py — pure function, no I/O.

Tests the ``reconstruct_text()`` function that applies accepted
co-author changes to reconstruct chapter text.

See ADR-023 and ADR-023-Restimplementierung Phase 1 for context.
"""

from __future__ import annotations

from narrare_core.writing.text_reconstructor import reconstruct_text


class TestSingleWordReplacement:
    """Replace a single word in the original text."""

    def test_single_word_replacement(self) -> None:
        result = reconstruct_text(
            "The cat sat on the mat.",
            [{"original_text": "cat", "revised_text": "dog"}],
        )
        assert result == "The dog sat on the mat."

    def test_replace_first_word(self) -> None:
        result = reconstruct_text(
            "The quick brown fox.",
            [{"original_text": "The", "revised_text": "A"}],
        )
        assert result == "A quick brown fox."

    def test_replace_last_word(self) -> None:
        result = reconstruct_text(
            "The quick brown fox.",
            [{"original_text": "fox", "revised_text": "rabbit"}],
        )
        assert result == "The quick brown rabbit."

    def test_replace_with_empty_revision(self) -> None:
        """Replace a word with empty string (deletion)."""
        result = reconstruct_text(
            "The cat sat on the mat.",
            [{"original_text": " cat ", "revised_text": " "}],
        )
        assert result == "The sat on the mat."  # cat is removed

    def test_no_change_when_not_found(self) -> None:
        """Change text not present in original → skipped, text unchanged."""
        result = reconstruct_text(
            "The cat sat on the mat.",
            [{"original_text": "elephant", "revised_text": "dog"}],
        )
        assert result == "The cat sat on the mat."


class TestMultipleChanges:
    """Multiple changes applied sequentially."""

    def test_multiple_changes(self) -> None:
        result = reconstruct_text(
            "The big dog ran quickly across the field.",
            [
                {"original_text": "big", "revised_text": "enormous"},
                {"original_text": "ran quickly", "revised_text": "sprinted"},
                {"original_text": "field", "revised_text": "meadow"},
            ],
        )
        assert result == "The enormous dog sprinted across the meadow."

    def test_changes_apply_to_accumulated_state(self) -> None:
        """Each change applies to the result of the previous change."""
        result = reconstruct_text(
            "A is B.",
            [
                {"original_text": "A", "revised_text": "X"},
                {"original_text": "B", "revised_text": "Y"},
            ],
        )
        assert result == "X is Y."

    def test_change_not_found_skips(self) -> None:
        """A change whose text doesn't match the current state is skipped."""
        result = reconstruct_text(
            "The cat sat.",
            [
                {"original_text": "cat", "revised_text": "dog"},
                {"original_text": "bird", "revised_text": "hawk"},  # not found → skip
            ],
        )
        assert result == "The dog sat."

    def test_change_with_empty_original_text_skipped(self) -> None:
        result = reconstruct_text(
            "The cat sat.",
            [{"original_text": "", "revised_text": "dog"}],
        )
        assert result == "The cat sat."

    def test_change_missing_original_text_key_skipped(self) -> None:
        result = reconstruct_text(
            "The cat sat.",
            [{"revised_text": "dog"}],  # missing original_text key
        )
        assert result == "The cat sat."


class TestOverlappingChanges:
    """Overlapping changes — last wins (applied in order)."""

    def test_overlapping_changes_last_wins(self) -> None:
        """When two changes overlap the same text, the last one wins."""
        result = reconstruct_text(
            "The very big dog.",
            [
                {"original_text": "very big", "revised_text": "extremely large"},
                {"original_text": "big dog", "revised_text": "small puppy"},
            ],
        )
        # First change: "very big" → "extremely large" → "The extremely large dog."
        # Second change: "big dog" not found in "The extremely large dog." → skip
        assert result == "The extremely large dog."

    def test_sequential_non_overlapping(self) -> None:
        """Non-overlapping changes both apply correctly."""
        result = reconstruct_text(
            "First part. Second part.",
            [
                {"original_text": "First", "revised_text": "1st"},
                {"original_text": "Second", "revised_text": "2nd"},
            ],
        )
        assert result == "1st part. 2nd part."

    def test_change_in_middle(self) -> None:
        """Change a segment in the middle of the text."""
        result = reconstruct_text(
            "She walked slowly toward the door.",
            [{"original_text": "slowly toward", "revised_text": "briskly to"}],
        )
        assert result == "She walked briskly to the door."


class TestEdgeCases:
    """Edge cases — empty inputs, special characters, etc."""

    def test_empty_original(self) -> None:
        result = reconstruct_text("", [{"original_text": "cat", "revised_text": "dog"}])
        assert result == ""

    def test_no_changes(self) -> None:
        result = reconstruct_text("The cat sat.", [])
        assert result == "The cat sat."

    def test_empty_original_no_changes(self) -> None:
        result = reconstruct_text("", [])
        assert result == ""

    def test_whitespace_only_original(self) -> None:
        result = reconstruct_text("   ", [{"original_text": " ", "revised_text": "_"}])
        # replace applies to first occurrence
        assert result == "_  "

    def test_special_characters(self) -> None:
        result = reconstruct_text(
            "He said, \"I'm going!\" — but she didn't hear.",
            [{"original_text": '"I\'m going!"', "revised_text": '"I\'m leaving!"'}],
        )
        assert result == "He said, \"I'm leaving!\" — but she didn't hear."

    def test_change_affects_original_only_once(self) -> None:
        """Multiple occurrences should only replace the first one."""
        result = reconstruct_text(
            "The cat and the cat sat.",
            [{"original_text": "cat", "revised_text": "dog"}],
        )
        assert result == "The dog and the cat sat."

    def test_newlines_preserved(self) -> None:
        result = reconstruct_text(
            "Line one.\nLine two.\nLine three.",
            [{"original_text": "Line two", "revised_text": "Line 2"}],
        )
        assert result == "Line one.\nLine 2.\nLine three."

    def test_unicode_characters(self) -> None:
        result = reconstruct_text(
            "Café résumé naïve.",
            [{"original_text": "Café", "revised_text": "Bistrot"}],
        )
        assert result == "Bistrot résumé naïve."
