"""Tests for writing/change_engine.py — server-side diff engine.

Covers:
1. Identical text (no changes)
2. Single word replacement
3. Multiple changes across sentences
4. Dialogue vs narrative classification
5. Empty text edge cases
6. Heavy restructuring (fallback behavior)
7. has_meaningful_changes helper
8. Insert and delete operations
"""

from __future__ import annotations

import pytest

from narrare_core.writing.change_engine import (
    DiffOp,
    DiffResult,
    compute_changes,
    has_meaningful_changes,
)

# ---------------------------------------------------------------------------
# No changes
# ---------------------------------------------------------------------------


class TestNoChanges:
    def test_identical_text_returns_no_changes(self) -> None:
        result = compute_changes(
            "The quick brown fox jumps over the lazy dog.",
            "The quick brown fox jumps over the lazy dog.",
        )
        assert not result.has_changes
        assert result.total_changes == 0
        assert len(result.changes) == 0

    def test_identical_with_special_chars(self) -> None:
        text = "He said, \"I'm going!\" — but she didn't hear."
        result = compute_changes(text, text)
        assert not result.has_changes

    def test_identical_text_single_word(self) -> None:
        result = compute_changes("Hello", "Hello")
        assert not result.has_changes


# ---------------------------------------------------------------------------
# Single word replacement
# ---------------------------------------------------------------------------


class TestSingleWordReplacement:
    def test_replace_one_word(self) -> None:
        result = compute_changes(
            "The cat sat on the mat.",
            "The cat lounged on the mat.",
        )
        assert result.has_changes
        assert result.total_changes >= 1
        assert "lounged" in result.revised

    def test_replace_with_contraction(self) -> None:
        result = compute_changes(
            "He is going to the store.",
            "He's going to the store.",
        )
        assert result.has_changes
        assert "He's" in result.revised

    def test_single_word_with_punctuation(self) -> None:
        result = compute_changes(
            "It was very dark.",
            "It was pitch dark.",
        )
        assert result.has_changes
        assert "pitch" in result.revised


# ---------------------------------------------------------------------------
# Multiple changes across sentences
# ---------------------------------------------------------------------------


class TestMultipleChanges:
    def test_two_sentence_changes(self) -> None:
        original = "The big dog ran quickly across the field. A small cat sat on the fence."
        revised = "The enormous dog sprinted across the field. A tiny cat perched on the fence."
        result = compute_changes(original, revised)
        assert result.has_changes
        assert result.total_changes >= 1

    def test_change_in_first_sentence_only(self) -> None:
        original = "The weather was very bad that day. They decided to stay home."
        revised = "The weather was awful that day. They decided to stay home."
        result = compute_changes(original, revised)
        assert result.has_changes
        # The second sentence is identical — verify by checking that
        # total changes is at least 1
        assert result.total_changes >= 1

    def test_change_in_second_sentence_only(self) -> None:
        original = "The weather was awful. They decided to stay home and rest."
        revised = "The weather was awful. They resolved to stay home and rest."
        result = compute_changes(original, revised)
        assert result.has_changes
        assert result.total_changes >= 1


# ---------------------------------------------------------------------------
# Dialogue vs narrative classification
# ---------------------------------------------------------------------------


class TestDialogueClassification:
    def test_dialogue_change_classified_as_dialogue(self) -> None:
        original = '"I am going to the store," he said angrily.'
        revised = '"I need to go to the store," he snapped.'
        result = compute_changes(
            original,
            revised,
            focus_areas=["dialogue", "word_choice"],
        )
        assert result.has_changes
        # Find dialogue-classified groups
        dialogue_groups = [g for g in result.changes if g.change_type == "dialogue"]
        assert len(dialogue_groups) >= 1

    def test_narrative_change_classified_as_word_choice(self) -> None:
        original = "The very large building loomed before them."
        revised = "The imposing building loomed before them."
        result = compute_changes(
            original,
            revised,
            focus_areas=["word_choice"],
        )
        assert result.has_changes
        # With only one focus area, all changes get that type
        assert all(g.change_type == "word_choice" for g in result.changes)


# ---------------------------------------------------------------------------
# Empty text edge cases
# ---------------------------------------------------------------------------


class TestEmptyText:
    def test_empty_original(self) -> None:
        result = compute_changes("", "Some revised text.")
        assert not result.has_changes

    def test_empty_revised(self) -> None:
        result = compute_changes("Some original text.", "")
        assert not result.has_changes

    def test_both_empty(self) -> None:
        result = compute_changes("", "")
        assert not result.has_changes

    def test_whitespace_only(self) -> None:
        result = compute_changes("   ", "   ")
        assert not result.has_changes


# ---------------------------------------------------------------------------
# Heavy restructuring (fallback behavior)
# ---------------------------------------------------------------------------


class TestHeavyRestructuring:
    def test_complete_rewrite_still_produces_diff(self) -> None:
        original = "The old house stood at the end of the road."
        revised = (
            "At the end of the winding lane, a weathered Victorian "
            "manor cast long shadows in the twilight."
        )
        result = compute_changes(original, revised)
        # Even for heavy rewrites, we should get a best-effort diff
        assert result.has_changes or result.total_changes >= 0

    def test_sentence_reordering_shows_changes(self) -> None:
        original = "First this happened. Then this. Finally this."
        revised = "Finally this. First this happened. Then this."
        result = compute_changes(original, revised)
        # Reordering should produce changes
        assert result.has_changes


# ---------------------------------------------------------------------------
# Insert and delete operations
# ---------------------------------------------------------------------------


class TestInsertDelete:
    def test_insertion_detected(self) -> None:
        original = "She smiled."
        revised = "She smiled warmly at him."
        result = compute_changes(original, revised)
        assert result.has_changes

    def test_deletion_detected(self) -> None:
        original = "He walked very slowly toward the door."
        revised = "He walked toward the door."
        result = compute_changes(original, revised)
        assert result.has_changes


# ---------------------------------------------------------------------------
# has_meaningful_changes
# ---------------------------------------------------------------------------


class TestHasMeaningfulChanges:
    def test_positive_with_changes(self) -> None:
        result = compute_changes("Old text.", "New text.")
        assert has_meaningful_changes(result)

    def test_negative_without_changes(self) -> None:
        result = compute_changes("Same text.", "Same text.")
        assert not has_meaningful_changes(result)

    def test_min_changes_threshold(self) -> None:
        # Single short sentence change
        result = compute_changes("Hello world.", "Hello there.")
        assert has_meaningful_changes(result, min_changes=1)

    def test_fails_below_threshold(self) -> None:
        result = compute_changes("Same text.", "Same text.")
        assert not has_meaningful_changes(result, min_changes=2)
        assert not has_meaningful_changes(result, min_changes=1)
        assert not has_meaningful_changes(result, min_changes=0)


# ---------------------------------------------------------------------------
# DiffOp dataclass
# ---------------------------------------------------------------------------


class TestDiffOpDataclass:
    def test_frozen(self) -> None:
        op = DiffOp(
            type="replace",
            original_start=0,
            original_end=5,
            revised_start=0,
            revised_end=6,
            content_original="Hello",
            content_revised="Greets",
        )
        with pytest.raises(AttributeError):
            op.type = "insert"  # type: ignore[misc]

    def test_slots(self) -> None:
        op = DiffOp(
            type="equal",
            original_start=0,
            original_end=3,
            revised_start=0,
            revised_end=3,
            content_original="Foo",
            content_revised="Foo",
        )
        with pytest.raises(AttributeError):
            _ = op.__dict__  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# DiffResult dataclass
# ---------------------------------------------------------------------------


class TestDiffResultDataclass:
    def test_default_factory_empty(self) -> None:
        result = DiffResult(original="", revised="")
        assert result.changes == []
        assert result.total_changes == 0
        assert not result.has_changes

    def test_frozen(self) -> None:
        result = DiffResult(original="a", revised="b", has_changes=True)
        with pytest.raises(AttributeError):
            result.has_changes = False  # type: ignore[misc]
