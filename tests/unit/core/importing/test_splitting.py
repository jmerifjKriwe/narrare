# tests/unit/core/importing/test_splitting.py
"""Golden tests for import section splitting (SETUP-003 v1)."""

from __future__ import annotations

from narrare_core.importing.splitting import (
    fallback_title,
    split_markdown_sections,
    split_marker_sections,
)


class TestSplitMarkdownSections:
    def test_no_headings_returns_single_preamble_section(self) -> None:
        assert split_markdown_sections("Just prose.\nMore prose.") == [
            ("", "Just prose.\nMore prose.")
        ]

    def test_h1_and_h2_split_deeper_headings_stay_inside(self) -> None:
        text = "# One\nbody one\n### deep\nstill one\n## Two\nbody two"
        sections = split_markdown_sections(text)
        assert [h for h, _ in sections] == ["One", "Two"]
        assert "### deep" in sections[0][1]
        assert sections[1][1] == "body two"

    def test_nonempty_preamble_becomes_own_section(self) -> None:
        sections = split_markdown_sections("Intro text\n# One\nbody")
        assert sections[0] == ("", "Intro text")
        assert sections[1] == ("One", "body")

    def test_empty_preamble_is_dropped(self) -> None:
        assert split_markdown_sections("# One\nbody")[0] == ("One", "body")


class TestSplitMarkerSections:
    def test_english_arabic_marker(self) -> None:
        sections = split_marker_sections("Chapter 1\nalpha\nChapter 2\nbeta")
        assert [t for t, _ in sections] == ["Chapter 1", "Chapter 2"]
        assert sections[0][1] == "alpha"

    def test_german_roman_marker_case_insensitive(self) -> None:
        sections = split_marker_sections("kapitel iv\ntext")
        assert sections == [("kapitel iv", "text")]

    def test_marker_with_trailing_text_keeps_whole_line_title(self) -> None:
        sections = split_marker_sections("Chapter 12 — The Storm\nwind")
        assert sections[0][0] == "Chapter 12 — The Storm"

    def test_spelled_out_number_is_not_a_marker(self) -> None:
        assert split_marker_sections("Chapter one\nprose") == [("", "Chapter one\nprose")]

    def test_no_markers_returns_single_section(self) -> None:
        assert split_marker_sections("plain text file body") == [("", "plain text file body")]


class TestFallbackTitle:
    def test_dashes_become_spaces_and_title_case(self) -> None:
        assert fallback_title("my-chapter.md") == "My Chapter"

    def test_no_extension(self) -> None:
        assert fallback_title("notes") == "Notes"

    def test_empty_stem_gets_untitled(self) -> None:
        assert fallback_title("") == "Untitled Chapter"
