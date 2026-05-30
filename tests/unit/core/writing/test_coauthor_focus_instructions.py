"""Tests for get_co_author_focus_instructions — focus-instruction builder."""

from __future__ import annotations

from narrare_core.writing.pipeline_coauthor import get_co_author_focus_instructions


class TestFocusInstructions:
    """Unit tests for the focus-instruction builder."""

    def test_single_focus_returns_instruction(self) -> None:
        result = get_co_author_focus_instructions(["dialogue"])
        assert "### dialogue" in result
        assert "dialogue more natural" in result

    def test_multiple_focus_areas(self) -> None:
        result = get_co_author_focus_instructions(["description", "word_choice"])
        assert "### description" in result
        assert "### word_choice" in result
        assert "### dialogue" not in result

    def test_empty_focus_returns_empty(self) -> None:
        result = get_co_author_focus_instructions([])
        assert result == ""

    def test_unknown_focus_is_ignored(self) -> None:
        result = get_co_author_focus_instructions(["unknown_mode"])
        assert result == ""

    def test_all_four_focus_areas(self) -> None:
        result = get_co_author_focus_instructions(
            ["word_choice", "sentence", "dialogue", "description"],
        )
        assert "### word_choice" in result
        assert "### sentence" in result
        assert "### dialogue" in result
        assert "### description" in result

    def test_mixed_known_and_unknown(self) -> None:
        result = get_co_author_focus_instructions(
            ["word_choice", "bogus", "dialogue"],
        )
        assert "### word_choice" in result
        assert "### dialogue" in result
        assert "### bogus" not in result
