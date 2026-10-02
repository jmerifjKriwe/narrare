# tests/unit/core/importing/test_detector.py
"""Golden tests for chapter detection (SETUP-003 v1, ADR-091)."""

from __future__ import annotations

from narrare_core.importing.detector import detect_chapters


class TestDetectMarkdown:
    def test_frontmatter_title_and_status_honored(self) -> None:
        text = "---\ntitle: The Thorn Wall\nstatus: final\n---\n\nBody text here."
        chapters = detect_chapters("ch-01.md", text)
        assert len(chapters) == 1
        assert chapters[0].title == "The Thorn Wall"
        assert chapters[0].status == "final"
        assert chapters[0].word_count == 3
        assert chapters[0].source_file == "ch-01.md"
        assert "title:" not in chapters[0].content

    def test_heading_split_per_chapter_with_preamble(self) -> None:
        text = "Preamble prose.\n# One\nbody one\n# Two\nbody two"
        chapters = detect_chapters("book.md", text)
        assert [c.title for c in chapters] == ["Book", "One", "Two"]
        assert chapters[0].content == "Preamble prose."
        assert chapters[1].content == "body one"

    def test_no_heading_no_frontmatter_uses_filename_stem(self) -> None:
        chapters = detect_chapters("my-chapter.md", "just body")
        assert chapters[0].title == "My Chapter"
        assert chapters[0].status == "draft"

    def test_invalid_status_coerces_to_draft(self) -> None:
        text = "---\nstatus: banana\n---\nbody"
        assert detect_chapters("a.md", text)[0].status == "draft"

    def test_heading_without_body_is_skipped(self) -> None:
        chapters = detect_chapters("a.md", "# Empty\n# Full\nbody")
        assert [c.title for c in chapters] == ["Full"]

    def test_whitespace_only_file_yields_no_chapters(self) -> None:
        assert detect_chapters("empty.md", "  \n\t\n") == []

    def test_long_title_is_truncated_to_limit(self) -> None:
        chapters = detect_chapters("a.md", f"# {'x' * 600}\nbody")
        assert len(chapters[0].title) == 500


class TestDetectTxt:
    def test_markers_split_and_marker_line_is_title(self) -> None:
        chapters = detect_chapters("novel.txt", "Chapter 1\na b c\nChapter 2\nd e f")
        assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
        assert [c.word_count for c in chapters] == [3, 3]
        assert all(c.status == "draft" for c in chapters)

    def test_no_marker_single_chapter_from_stem(self) -> None:
        chapters = detect_chapters("draft-notes.txt", "one two three")
        assert len(chapters) == 1
        assert chapters[0].title == "Draft Notes"

    def test_marker_preamble_gets_fallback_title(self) -> None:
        chapters = detect_chapters("book.txt", "intro text\nChapter 1\nbody")
        assert chapters[0].title == "Book"
        assert chapters[1].title == "Chapter 1"


class TestDeterminism:
    def test_identical_input_yields_identical_output(self) -> None:
        text = "---\ntitle: T\n---\n# A\nx\n# B\ny"
        assert detect_chapters("f.md", text) == detect_chapters("f.md", text)

    def test_unknown_extension_yields_no_chapters(self) -> None:
        assert detect_chapters("file.docx", "# H\nbody") == []
