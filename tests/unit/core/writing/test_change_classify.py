"""Tests for writing/_change_classify.py — change classification edge cases.

Covers uncovered branches in:
1. ``_build_change_group`` with empty ops list (line 35)
2. ``_expand_to_sentence`` with empty text (line 69)
3. ``classify_groups`` with empty group_lists (line 116)
4. Classification branches: description, word_choice, sentence (lines 164, 167, 170)
"""

from __future__ import annotations

from narrare_core.writing._change_classify import (
    _build_change_group,
    _expand_to_sentence,
    classify_groups,
)
from narrare_core.writing._change_types import DiffOp

# ---------------------------------------------------------------------------
# _build_change_group with empty ops
# ---------------------------------------------------------------------------


class TestBuildChangeGroupEmptyOps:
    def test_build_change_group_empty_ops_returns_empty_group(self) -> None:
        """Empty ops list produces a ChangeGroup with empty text and no ops."""
        group = _build_change_group(
            ops=[], original="Hello world.", revised="Hello world.", change_type="test", index=0
        )
        assert group.original_text == ""
        assert group.revised_text == ""
        assert group.ops == []
        assert group.change_type == "test"
        assert group.index == 0


# ---------------------------------------------------------------------------
# _expand_to_sentence with empty text
# ---------------------------------------------------------------------------


class TestExpandToSentenceEmptyText:
    def test_expand_to_sentence_empty_text_returns_start_end(self) -> None:
        """Empty text returns the start/end pair unchanged."""
        result = _expand_to_sentence(start=5, end=10, text="")
        assert result == (5, 10)


# ---------------------------------------------------------------------------
# classify_groups with empty input
# ---------------------------------------------------------------------------


class TestClassifyGroupsEmpty:
    def test_classify_groups_empty_returns_empty_list(self) -> None:
        """Empty group_lists produces an empty result."""
        result = classify_groups(
            group_lists=[], focus_areas=["dialogue"], original="foo", revised="bar"
        )
        assert result == []


# ---------------------------------------------------------------------------
# Classification branches via classify_groups
# ---------------------------------------------------------------------------


def _make_replace_op(orig: str, rev: str) -> DiffOp:
    """Helper: create a single replace DiffOp."""
    return DiffOp(
        type="replace",
        original_start=0,
        original_end=len(orig),
        revised_start=0,
        revised_end=len(rev),
        content_original=orig,
        content_revised=rev,
    )


class TestClassifyDescriptionBranch:
    def test_description_focus_no_quotes_classifies_as_description(self) -> None:
        """When 'description' in focus_areas and text has no quotes → 'description'."""
        ops = [_make_replace_op("The dark forest loomed.", "The ancient forest loomed.")]
        result = classify_groups(
            group_lists=[ops],
            focus_areas=["description"],
            original="The dark forest loomed.",
            revised="The ancient forest loomed.",
        )
        assert len(result) == 1
        assert result[0].change_type == "description"


class TestClassifyWordChoiceBranch:
    def test_word_choice_single_word_change_classifies_as_word_choice(self) -> None:
        """Single-word replace with 'word_choice' in focus → 'word_choice'."""
        ops = [_make_replace_op("dark", "ancient")]
        result = classify_groups(
            group_lists=[ops],
            focus_areas=["word_choice"],
            original="The dark forest.",
            revised="The ancient forest.",
        )
        assert len(result) == 1
        assert result[0].change_type == "word_choice"


class TestClassifySentenceBranch:
    def test_sentence_focus_multi_word_classifies_as_sentence(self) -> None:
        """Multi-word change with 'sentence' in focus → 'sentence'."""
        ops = [_make_replace_op("The cat sat down.", "A mysterious cat appeared.")]
        result = classify_groups(
            group_lists=[ops],
            focus_areas=["sentence"],
            original="The cat sat down.",
            revised="A mysterious cat appeared.",
        )
        assert len(result) == 1
        assert result[0].change_type == "sentence"


class TestClassifyFallbackBranch:
    def test_fallback_short_text_classifies_as_word_choice(self) -> None:
        """No focus area match, short text → fallback 'word_choice'."""
        ops = [_make_replace_op("cat", "dog")]
        result = classify_groups(
            group_lists=[ops],
            focus_areas=[],
            original="The cat slept.",
            revised="The dog slept.",
        )
        assert len(result) == 1
        # "cat" is 1 word, so fallback is "word_choice"
        assert result[0].change_type == "word_choice"

    def test_fallback_long_text_classifies_as_sentence(self) -> None:
        """No focus area match, long text → fallback 'sentence'."""
        ops = [
            _make_replace_op(
                "The cat slept on the mat all day long",
                "The dog rested upon the rug for hours",
            )
        ]
        result = classify_groups(
            group_lists=[ops],
            focus_areas=[],
            original="The cat slept on the mat all day long.",
            revised="The dog rested upon the rug for hours.",
        )
        assert len(result) == 1
        # More than 3 words → fallback "sentence"
        assert result[0].change_type == "sentence"


# ---------------------------------------------------------------------------
# _classify_single_group branches (multi-focus, skips single-focus shortcut)
# ---------------------------------------------------------------------------


class TestClassifySingleGroupDescription:
    """``_classify_single_group`` with ``description`` match (line 164)."""

    def test_description_in_multi_focus_without_quotes_returns_description(
        self,
    ) -> None:
        """Multiple focus areas with description match → 'description'."""
        ops = [_make_replace_op("The dark forest loomed.", "The ancient forest loomed.")]
        result = classify_groups(
            group_lists=[ops],
            focus_areas=["description", "sentence"],
            original="The dark forest loomed.",
            revised="The ancient forest loomed.",
        )
        assert len(result) == 1
        assert result[0].change_type == "description"


class TestClassifySingleGroupWordChoice:
    """``_classify_single_group`` with ``word_choice`` match (line 167)."""

    def test_word_choice_lower_priority_in_multi_focus_without_dialogue_or_description(
        self,
    ) -> None:
        """word_choice in multi-focus where ``dialogue`` does not match → 'word_choice'."""
        ops = [_make_replace_op("dark", "ancient")]
        result = classify_groups(
            group_lists=[ops],
            focus_areas=["dialogue", "word_choice"],
            original="The dark forest.",
            revised="The ancient forest.",
        )
        assert len(result) == 1
        assert result[0].change_type == "word_choice"


class TestClassifySingleGroupSentence:
    """``_classify_single_group`` with ``sentence`` match (line 170)."""

    def test_sentence_in_multi_focus_without_dialogue_or_description_or_word_choice(
        self,
    ) -> None:
        """sentence in multi-focus where others don't match → 'sentence'."""
        ops = [
            _make_replace_op(
                "The cat slept on the mat all day long",
                "The dog rested upon the rug for hours",
            )
        ]
        result = classify_groups(
            group_lists=[ops],
            focus_areas=["dialogue", "sentence"],
            original="The cat slept on the mat all day long.",
            revised="The dog rested upon the rug for hours.",
        )
        assert len(result) == 1
        assert result[0].change_type == "sentence"
