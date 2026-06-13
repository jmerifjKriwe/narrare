"""Tests for writing/draft_processor.py.

Covers:
1. Artifact removal — each pattern type
2. Trailing sentence cleanup — stopped mid-sentence
3. Word count truncation — over target, under target, exact
4. Empty input — returns empty string
5. Already clean text — unchanged
6. ``is_partial=True`` — no trailing cleanup
"""

from __future__ import annotations

import pytest

from narrare_core.writing.draft_processor import DraftProcessor


@pytest.fixture()
def processor() -> DraftProcessor:
    return DraftProcessor()


# ---------------------------------------------------------------------------
# 1. Artifact removal
# ---------------------------------------------------------------------------


class TestArtifactRemoval:
    """Each artifact pattern is stripped correctly."""

    def test_here_is_your_chapter_draft(self, processor: DraftProcessor) -> None:
        text = "Here is your chapter draft:\n\nThe wind howled."
        assert processor.process(text) == "The wind howled."

    def test_heres_the_chapter(self, processor: DraftProcessor) -> None:
        text = "Here's the chapter:\n\nShe walked away."
        assert processor.process(text) == "She walked away."

    def test_here_is_your_text(self, processor: DraftProcessor) -> None:
        text = "Here is your text:\nRain fell softly."
        assert processor.process(text) == "Rain fell softly."

    def test_code_fence_markdown(self, processor: DraftProcessor) -> None:
        text = "```markdown\n# Chapter\n\nProse here.\n```"
        result = processor.process(text)
        assert "```" not in result
        assert "Prose here." in result

    def test_code_fence_plain(self, processor: DraftProcessor) -> None:
        text = "```\nPlain prose.\n```"
        result = processor.process(text)
        assert "```" not in result
        assert "Plain prose." in result

    def test_note_line_removed(self, processor: DraftProcessor) -> None:
        text = "Story text.\n**Note:** This is a generated draft.\nMore story."
        result = processor.process(text)
        assert "**Note:**" not in result
        assert "Story text." in result
        assert "More story." in result

    def test_disclaimer_line_removed(self, processor: DraftProcessor) -> None:
        text = "Prose.\n**Disclaimer**: AI-generated content.\nMore prose."
        result = processor.process(text)
        assert "**Disclaimer**" not in result
        assert "Prose." in result

    def test_chapter_header_artifact_removed(self, processor: DraftProcessor) -> None:
        text = "# Chapter 1: The Beginning\n\nThe real content starts."
        result = processor.process(text)
        assert "Chapter 1" not in result
        assert "The real content starts." in result

    def test_kapitel_header_removed(self, processor: DraftProcessor) -> None:
        text = "## Kapitel 3: Nacht\n\nEs war dunkel."
        result = processor.process(text)
        assert "Kapitel 3" not in result
        assert "Es war dunkel." in result


# ---------------------------------------------------------------------------
# 2. Trailing sentence cleanup
# ---------------------------------------------------------------------------


class TestTrailingSentence:
    """Incomplete trailing sentences are removed."""

    def test_incomplete_sentence_removed(self, processor: DraftProcessor) -> None:
        text = "First sentence. Second sentence. Third is incom"
        result = processor.process(text)
        assert result == "First sentence. Second sentence."

    def test_complete_sentence_preserved(self, processor: DraftProcessor) -> None:
        text = "First sentence. Second sentence."
        result = processor.process(text)
        assert result == text

    def test_ends_with_exclamation(self, processor: DraftProcessor) -> None:
        text = "He shouted!"
        assert processor.process(text) == text

    def test_ends_with_question_mark(self, processor: DraftProcessor) -> None:
        text = "Where did she go?"
        assert processor.process(text) == text

    def test_ends_with_ellipsis(self, processor: DraftProcessor) -> None:
        text = "The trail went cold…"
        assert processor.process(text) == text

    def test_ends_with_closing_quote(self, processor: DraftProcessor) -> None:
        text = 'She said, "I will return."'
        assert processor.process(text) == text

    def test_no_sentence_boundary_returns_as_is(
        self,
        processor: DraftProcessor,
    ) -> None:
        text = "no punctuation at all"
        result = processor.process(text)
        assert result == text

    def test_is_partial_skips_trailing_cleanup(
        self,
        processor: DraftProcessor,
    ) -> None:
        text = "First sentence. Second is incom"
        result = processor.process(text, is_partial=True)
        assert "incom" in result

    def test_trailing_quote_after_period_included_in_sentence(
        self,
        processor: DraftProcessor,
    ) -> None:
        """Closing quote after period is included as part of sentence (line 174)."""
        text = 'She said, "I will return." Then she started to say something'
        result = processor.process(text)
        assert "return." in result
        assert result.endswith('"')
        assert "something" not in result

    def test_public_trailing_quote_included(
        self,
        processor: DraftProcessor,
    ) -> None:
        """remove_incomplete_trailing preserves closing quotes after period."""
        text = 'He thought, "Maybe not." And then he paused'
        result = processor.remove_incomplete_trailing(text)
        assert result.endswith('"')


# ---------------------------------------------------------------------------
# 3. Word count enforcement
# ---------------------------------------------------------------------------


class TestWordCount:
    """Word-target truncation with ±10 % tolerance."""

    def test_within_tolerance_unchanged(self, processor: DraftProcessor) -> None:
        text = " ".join(f"word{i}." for i in range(100))
        result = processor.process(text, word_target=100)
        assert result == text

    def test_over_target_truncates(self, processor: DraftProcessor) -> None:
        # 150 words, target 100 → max 110, min 90
        words = [f"word{i}." for i in range(150)]
        text = " ".join(words)
        result = processor.process(text, word_target=100)
        result_words = len(result.split())
        assert result_words <= 110
        assert result_words >= 90

    def test_truncation_at_sentence_boundary(
        self,
        processor: DraftProcessor,
    ) -> None:
        # Build text where each "sentence" is one word ending with .
        text = " ".join(f"w{i}." for i in range(150))
        result = processor.process(text, word_target=100)
        # Should end at a sentence boundary
        assert result.endswith(".")
        assert not result.rstrip().endswith("w")

    def test_word_target_truncates_including_trailing_quote(
        self,
        processor: DraftProcessor,
    ) -> None:
        """Truncation preserves closing quotes after sentence boundary (line 210)."""
        # Build text where the 110th word (or near there) ends with ."
        # so that _enforce_word_target scans back and finds . followed by "
        words = ["hello." for _ in range(100)] + ['said, "word."' for _ in range(20)]
        text = " ".join(words)
        result = processor.process(text, word_target=100)
        assert 90 <= len(result.split()) <= 110

    def test_below_target_not_truncated(self, processor: DraftProcessor) -> None:
        text = "Short text here."
        result = processor.process(text, word_target=1000)
        assert result == text

    def test_exactly_at_target(self, processor: DraftProcessor) -> None:
        words = [f"word{i}." for i in range(100)]
        text = " ".join(words)
        result = processor.process(text, word_target=100)
        assert result == text

    def test_truncation_below_minimum_returns_original(self, processor: DraftProcessor) -> None:
        first_sentence = "Long sentence here with many words that goes on and on and finally"
        text = f"{first_sentence} ends. " + " ".join(f"word{i}" for i in range(10))
        result = processor.process(text, word_target=20, is_partial=True)
        assert result == text


# ---------------------------------------------------------------------------
# 4. Empty / edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and combined processing."""

    def test_empty_string(self, processor: DraftProcessor) -> None:
        assert processor.process("") == ""

    def test_whitespace_only(self, processor: DraftProcessor) -> None:
        assert processor.process("   \n\n  ") == ""

    def test_already_clean_text(self, processor: DraftProcessor) -> None:
        text = "The cat sat on the mat. It purred softly."
        assert processor.process(text) == text

    def test_multiple_blank_lines_normalised(
        self,
        processor: DraftProcessor,
    ) -> None:
        text = "Para one.\n\n\n\n\nPara two."
        result = processor.process(text)
        assert "\n\n\n" not in result
        assert "Para one." in result
        assert "Para two." in result

    def test_scene_break_normalised(self, processor: DraftProcessor) -> None:
        text = "Scene one.****Scene two."
        result = processor.process(text)
        assert "***" in result
        assert "Scene one." in result
        assert "Scene two." in result

    def test_combined_artifacts_and_trailing(
        self,
        processor: DraftProcessor,
    ) -> None:
        text = (
            "Here is your chapter draft:\n\n"
            "```markdown\n"
            "# Chapter 1: Beginnings\n\n"
            "The story begins here. But then it cuts off mid"
        )
        result = processor.process(text)
        assert "Here is" not in result
        assert "```" not in result
        assert "Chapter 1" not in result
        assert result == "The story begins here."


# ---------------------------------------------------------------------------
# 5. Public API — wrappers tested directly
# ---------------------------------------------------------------------------


class TestPublicAPI:
    """Public wrapper methods tested directly."""

    def test_strip_artifacts_removes_boilerplate(self, processor: DraftProcessor) -> None:
        text = "Here is your chapter draft:\n\nProse."
        assert processor.strip_artifacts(text) == "Prose."

    def test_normalise_markdown_collapses_blank_lines(self, processor: DraftProcessor) -> None:
        text = "text\n\n\n\nmore"
        assert processor.normalise_markdown(text) == "text\n\nmore"

    def test_remove_incomplete_trailing_truncates_fragment(self, processor: DraftProcessor) -> None:
        text = "First. Second. Incom"
        assert processor.remove_incomplete_trailing(text) == "First. Second."

    def test_enforce_word_target_truncates(self, processor: DraftProcessor) -> None:
        words = [f"w{i}." for i in range(150)]
        text = " ".join(words)
        result = processor.enforce_word_target(text, word_target=100)
        result_words = len(result.split())
        assert 90 <= result_words <= 110
