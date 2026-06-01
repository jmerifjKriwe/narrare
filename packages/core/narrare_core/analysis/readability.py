"""Deterministic readability metrics computation (ADR-021).

Formula-based: Flesch Reading Ease, Flesch-Kincaid Grade Level, Gunning Fog Index.
No LLM calls — pure math for instant results.

Implements the :class:`ReadabilityAnalyzer` Protocol from ``contracts.py``.
All methods are pure functions — no state, no I/O, deterministic.

Usage::

    from narrare_core.analysis.readability import FormulaReadabilityAnalyzer

    analyzer = FormulaReadabilityAnalyzer()
    result = await analyzer.analyze("The cat sat on the mat.", language="en")
    print(result.metrics.flesch_reading_ease)
    print(result.metrics.flesch_kincaid_grade)
    print(result.metrics.gunning_fog)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from narrare_core.analysis.types import ReadabilityMetrics, ReadabilityResult

if TYPE_CHECKING:
    from narrare_core.nlp.contracts_types import LanguageCode

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Genre benchmarks — pre-computed readability targets for common genres
# ---------------------------------------------------------------------------

_GENRE_BENCHMARKS: dict[str, ReadabilityMetrics] = {
    "middle_grade": ReadabilityMetrics(
        flesch_reading_ease=80.0,
        flesch_kincaid_grade=5.0,
        gunning_fog=6.0,
        avg_sentence_length=12.0,
        avg_syllables_per_word=1.3,
        complex_word_ratio=0.05,
        word_count=0,
        sentence_count=0,
    ),
    "young_adult": ReadabilityMetrics(
        flesch_reading_ease=70.0,
        flesch_kincaid_grade=7.0,
        gunning_fog=9.0,
        avg_sentence_length=15.0,
        avg_syllables_per_word=1.4,
        complex_word_ratio=0.08,
        word_count=0,
        sentence_count=0,
    ),
    "commercial_fiction": ReadabilityMetrics(
        flesch_reading_ease=65.0,
        flesch_kincaid_grade=8.0,
        gunning_fog=10.0,
        avg_sentence_length=17.0,
        avg_syllables_per_word=1.5,
        complex_word_ratio=0.10,
        word_count=0,
        sentence_count=0,
    ),
    "literary_fiction": ReadabilityMetrics(
        flesch_reading_ease=50.0,
        flesch_kincaid_grade=10.0,
        gunning_fog=13.0,
        avg_sentence_length=20.0,
        avg_syllables_per_word=1.7,
        complex_word_ratio=0.15,
        word_count=0,
        sentence_count=0,
    ),
}

# Vowel pattern for syllable counting (English-centric heuristic)
_VOWEL_GROUPS_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)


class FormulaReadabilityAnalyzer:
    """Deterministic readability analyzer — implements ReadabilityAnalyzer protocol.

    Computes Flesch Reading Ease, Flesch-Kincaid Grade Level, Gunning Fog Index,
    plus sentence length, syllable count, and complex word ratio.
    All methods are pure functions — no state, no I/O.

    Identical input always produces identical output (ADR-021).
    """

    async def analyze(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> ReadabilityResult:
        """Compute formula-based readability metrics for the given text.

        Args:
            text: The text to analyse (chapter content, passage, etc.).
            language: Language code (``"en"``, ``"de"``, ``"fr"``).
                Currently only affects syllable counting heuristic.
                Defaults to ``"en"``.

        Returns:
            A :class:`ReadabilityResult` with deterministic metrics and
            genre benchmarks.  ``sentence_analyses`` is always empty —
            use :class:`ReadabilityAgentProtocol` for AI-powered analysis.
        """
        if not text or not text.strip():
            return ReadabilityResult(
                metrics=self._empty_metrics(),
                genre_benchmarks=dict(_GENRE_BENCHMARKS),
                sentence_analyses=[],
                overall_assessment=None,
            )

        sentences = self._split_sentences(text)
        words = self._extract_words(text)

        if not words:
            return ReadabilityResult(
                metrics=self._empty_metrics(),
                genre_benchmarks=dict(_GENRE_BENCHMARKS),
                sentence_analyses=[],
                overall_assessment=None,
            )

        total_words = len(words)
        total_sentences = max(len(sentences), 1)
        total_syllables = sum(self._count_syllables(w) for w in words)
        complex_words = sum(1 for w in words if self._is_complex_word(w))

        metrics = ReadabilityMetrics(
            flesch_reading_ease=self._flesch_reading_ease(
                total_syllables,
                total_words,
                total_sentences,
            ),
            flesch_kincaid_grade=self._flesch_kincaid_grade(
                total_syllables,
                total_words,
                total_sentences,
            ),
            gunning_fog=self._gunning_fog(
                total_words,
                complex_words,
                total_sentences,
            ),
            avg_sentence_length=total_words / total_sentences,
            avg_syllables_per_word=total_syllables / total_words,
            complex_word_ratio=complex_words / total_words,
            word_count=total_words,
            sentence_count=total_sentences,
        )

        return ReadabilityResult(
            metrics=metrics,
            genre_benchmarks=dict(_GENRE_BENCHMARKS),
            sentence_analyses=[],
            overall_assessment=None,
        )

    # ------------------------------------------------------------------
    # Static helpers — pure functions
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_metrics() -> ReadabilityMetrics:
        """Return zeroed-out metrics for edge cases (empty text, no words)."""
        return ReadabilityMetrics(
            flesch_reading_ease=0.0,
            flesch_kincaid_grade=0.0,
            gunning_fog=0.0,
            avg_sentence_length=0.0,
            avg_syllables_per_word=0.0,
            complex_word_ratio=0.0,
            word_count=0,
            sentence_count=0,
        )

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences using punctuation boundaries.

        Handles ``.``, ``!``, ``?``, and ellipsis.  Treats text with no
        punctuation as a single sentence.

        Args:
            text: Raw text to split.

        Returns:
            List of sentence strings (may include empty strings).
        """
        # Split on sentence-ending punctuation followed by whitespace or end.
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        # Filter out empty strings
        return [p for p in parts if p.strip()]

    @staticmethod
    def _extract_words(text: str) -> list[str]:
        """Extract word tokens from text.

        Strips punctuation and returns lowercase words with at least one
        alphabetic character.

        Args:
            text: Raw text.

        Returns:
            List of word strings.
        """
        tokens = re.findall(r"[a-zA-Z'\u00C0-\u024F]+", text)
        return [t.lower() for t in tokens if any(c.isalpha() for c in t)]

    @staticmethod
    def _count_syllables(word: str) -> int:
        """Estimate syllable count for an English word.

        Uses a vowel-group heuristic:
        1. Count contiguous vowel groups (``a``, ``e``, ``i``, ``o``, ``u``, ``y``).
        2. Ensure at least 1 syllable per word.
        3. Subtract 1 for trailing silent ``e`` (except for ``le`` after consonant).
        4. Subtract 1 for ``es`` / ``ed`` suffixes when preceded by consonant.

        This is intentionally simple — a full CMU Pronouncing Dictionary
        would be more accurate but adds a heavy dependency.

        Args:
            word: A single word (lowercase recommended).

        Returns:
            Estimated syllable count (minimum 1).
        """
        word = word.lower().strip()
        if not word:
            return 0

        # Count vowel groups
        groups = _VOWEL_GROUPS_RE.findall(word)
        count = len(groups)

        if count == 0:
            return 1

        # Subtract for trailing silent 'e'
        if word.endswith("e") and not word.endswith("le") and count > 1:
            count -= 1

        # Subtract for -es / -ed suffixes after consonant
        if len(word) > 3 and (
            (word.endswith("es") and word[-3] not in "aeiouy")
            or (word.endswith("ed") and word[-3] not in "aeiouy")
        ):
            count -= 1

        return max(count, 1)

    @staticmethod
    def _is_complex_word(word: str) -> bool:
        """Check if a word has 3 or more syllables (complex word).

        Used for Gunning Fog Index calculation.

        Args:
            word: A single word.

        Returns:
            ``True`` if the word has ≥ 3 syllables.
        """
        return FormulaReadabilityAnalyzer._count_syllables(word) >= 3

    @staticmethod
    def _flesch_reading_ease(
        total_syllables: int,
        total_words: int,
        total_sentences: int,
    ) -> float:
        """Compute Flesch Reading Ease score.

        Formula: ``206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)``

        Range: 0-100 (higher = easier to read).

        Args:
            total_syllables: Total syllable count in the text.
            total_words: Total word count.
            total_sentences: Total sentence count.

        Returns:
            Flesch Reading Ease score, clamped to ``[0.0, 100.0]``.
        """
        if total_words == 0 or total_sentences == 0:
            return 0.0
        score = (
            206.835
            - 1.015 * (total_words / total_sentences)
            - 84.6 * (total_syllables / total_words)
        )
        return max(0.0, min(100.0, score))

    @staticmethod
    def _flesch_kincaid_grade(
        total_syllables: int,
        total_words: int,
        total_sentences: int,
    ) -> float:
        """Compute Flesch-Kincaid Grade Level.

        Formula: ``0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59``

        Range: ~0-18 (approximate US school grade).

        Args:
            total_syllables: Total syllable count.
            total_words: Total word count.
            total_sentences: Total sentence count.

        Returns:
            Flesch-Kincaid Grade Level, floored at 0.0.
        """
        if total_words == 0 or total_sentences == 0:
            return 0.0
        grade = (
            0.39 * (total_words / total_sentences) + 11.8 * (total_syllables / total_words) - 15.59
        )
        return max(0.0, grade)

    @staticmethod
    def _gunning_fog(
        total_words: int,
        complex_words: int,
        total_sentences: int,
    ) -> float:
        """Compute Gunning Fog Index.

        Formula: ``0.4 * ((words/sentences) + 100 * (complex_words/words))``

        Range: ~0-20 (years of formal education needed).

        Args:
            total_words: Total word count.
            complex_words: Number of words with ≥ 3 syllables.
            total_sentences: Total sentence count.

        Returns:
            Gunning Fog Index, floored at 0.0.
        """
        if total_words == 0 or total_sentences == 0:
            return 0.0
        fog = 0.4 * ((total_words / total_sentences) + 100.0 * (complex_words / total_words))
        return max(0.0, fog)
