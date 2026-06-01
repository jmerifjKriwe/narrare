"""Tests for deterministic readability metrics computation (ADR-021).

Covers:
1. Flesch Reading Ease — easy and hard texts
2. Flesch-Kincaid Grade Level — easy and hard texts
3. Gunning Fog Index — easy and hard texts
4. Edge cases — empty text, single word, no punctuation
5. Syllable counting heuristic
6. Complex word detection
7. Genre benchmarks structure
8. Protocol compliance — satisfies ReadabilityAnalyzer
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.contracts_readability import ReadabilityAnalyzer
from narrare_core.analysis.readability import FormulaReadabilityAnalyzer
from narrare_core.analysis.types import ReadabilityMetrics, ReadabilityResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def analyzer() -> FormulaReadabilityAnalyzer:
    """Fresh readability analyzer instance."""
    return FormulaReadabilityAnalyzer()


# ---------------------------------------------------------------------------
# A. Flesch Reading Ease
# ---------------------------------------------------------------------------


class TestFleschReadingEase:
    """Flesch Reading Ease score computation."""

    @pytest.mark.asyncio
    async def test_easy_text_scores_high(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Simple text with short words should score high on Flesch Reading Ease."""
        text = "The cat sat on the mat. The dog ran to the park. It was a good day."
        result = await analyzer.analyze(text)
        assert result.metrics.flesch_reading_ease > 70.0

    @pytest.mark.asyncio
    async def test_hard_text_scores_low(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Complex academic text should score low on Flesch Reading Ease."""
        text = (
            "Notwithstanding the aforementioned circumstances, the constitutional "
            "amendment necessitates comprehensive reevaluation of subsidiary "
            "legislative frameworks."
        )
        result = await analyzer.analyze(text)
        assert result.metrics.flesch_reading_ease < 50.0

    @pytest.mark.asyncio
    async def test_score_bounded_0_to_100(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Score should be clamped between 0 and 100."""
        text = "Run. Go. See. Do."
        result = await analyzer.analyze(text)
        assert 0.0 <= result.metrics.flesch_reading_ease <= 100.0


# ---------------------------------------------------------------------------
# B. Flesch-Kincaid Grade Level
# ---------------------------------------------------------------------------


class TestFleschKincaidGrade:
    """Flesch-Kincaid Grade Level computation."""

    @pytest.mark.asyncio
    async def test_easy_text_low_grade(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Simple text should have a low grade level."""
        text = "The cat sat on the mat. The dog ran to the park."
        result = await analyzer.analyze(text)
        assert result.metrics.flesch_kincaid_grade < 6.0

    @pytest.mark.asyncio
    async def test_hard_text_high_grade(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Complex text should have a high grade level."""
        text = (
            "The epistemological implications of quantum entanglement "
            "necessitate fundamental reconsideration of observational "
            "methodologies."
        )
        result = await analyzer.analyze(text)
        assert result.metrics.flesch_kincaid_grade > 10.0

    @pytest.mark.asyncio
    async def test_grade_non_negative(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Grade level should never be negative."""
        text = "I am here. You are there. We are all fine."
        result = await analyzer.analyze(text)
        assert result.metrics.flesch_kincaid_grade >= 0.0


# ---------------------------------------------------------------------------
# C. Gunning Fog Index
# ---------------------------------------------------------------------------


class TestGunningFog:
    """Gunning Fog Index computation."""

    @pytest.mark.asyncio
    async def test_easy_text_low_fog(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Simple text should have a low Gunning Fog Index."""
        text = "The cat sat on the mat. The dog ran fast. The bird flew high."
        result = await analyzer.analyze(text)
        assert result.metrics.gunning_fog < 10.0

    @pytest.mark.asyncio
    async def test_hard_text_high_fog(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Complex text should have a high Gunning Fog Index."""
        text = (
            "Organizational restructuring necessitates comprehensive "
            "reconfiguration of departmental hierarchies and interpersonal "
            "communication methodologies."
        )
        result = await analyzer.analyze(text)
        assert result.metrics.gunning_fog > 12.0

    @pytest.mark.asyncio
    async def test_fog_non_negative(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Fog index should never be negative."""
        text = "Hi. Bye."
        result = await analyzer.analyze(text)
        assert result.metrics.gunning_fog >= 0.0


# ---------------------------------------------------------------------------
# D. Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case handling."""

    @pytest.mark.asyncio
    async def test_empty_text_returns_zeros(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Empty text should return zeroed metrics."""
        result = await analyzer.analyze("")
        m = result.metrics
        assert m.flesch_reading_ease == 0.0
        assert m.flesch_kincaid_grade == 0.0
        assert m.gunning_fog == 0.0
        assert m.word_count == 0
        assert m.sentence_count == 0

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_zeros(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Whitespace-only text should return zeroed metrics."""
        result = await analyzer.analyze("   \n\t  ")
        assert result.metrics.word_count == 0
        assert result.metrics.sentence_count == 0

    @pytest.mark.asyncio
    async def test_single_word(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Single word should produce minimal metrics."""
        result = await analyzer.analyze("Hello")
        assert result.metrics.word_count == 1
        assert result.metrics.sentence_count == 1
        assert result.metrics.avg_sentence_length == 1.0
        assert result.metrics.avg_syllables_per_word >= 1.0

    @pytest.mark.asyncio
    async def test_no_punctuation_treated_as_one_sentence(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Text without punctuation treated as one sentence."""
        result = await analyzer.analyze("the cat sat on the mat")
        assert result.metrics.sentence_count == 1
        assert result.metrics.word_count == 6

    @pytest.mark.asyncio
    async def test_returns_readability_result_type(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """analyze() returns ReadabilityResult (not just ReadabilityMetrics)."""
        result = await analyzer.analyze("Hello world.")
        assert isinstance(result, ReadabilityResult)
        assert isinstance(result.metrics, ReadabilityMetrics)

    @pytest.mark.asyncio
    async def test_sentence_analyses_always_empty(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Deterministic analyzer never produces sentence analyses."""
        result = await analyzer.analyze("Some text to analyze.")
        assert result.sentence_analyses == []

    @pytest.mark.asyncio
    async def test_overall_assessment_is_none(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Deterministic analyzer never produces overall assessment."""
        result = await analyzer.analyze("Some text to analyze.")
        assert result.overall_assessment is None


# ---------------------------------------------------------------------------
# E. Syllable Counter
# ---------------------------------------------------------------------------


class TestSyllableCounter:
    """Test the syllable counting heuristic."""

    def test_single_syllable_words(self) -> None:
        """Common single-syllable words."""
        analyzer = FormulaReadabilityAnalyzer()
        for word in ["cat", "dog", "the", "a", "is", "run", "big", "small"]:
            assert analyzer._count_syllables(word) == 1, f"Expected 1 for '{word}'"

    def test_two_syllable_words(self) -> None:
        """Common two-syllable words."""
        analyzer = FormulaReadabilityAnalyzer()
        for word, expected in [("apple", 2), ("happy", 2), ("running", 2), ("simple", 2)]:
            result = analyzer._count_syllables(word)
            assert result == expected, f"Expected {expected} for '{word}', got {result}"

    def test_three_syllable_words(self) -> None:
        """Common three-syllable words."""
        analyzer = FormulaReadabilityAnalyzer()
        for word in ["beautiful", "important", "understand"]:
            result = analyzer._count_syllables(word)
            assert result >= 3, f"Expected >= 3 for '{word}', got {result}"

    def test_silent_e(self) -> None:
        """Trailing silent 'e' should reduce syllable count."""
        analyzer = FormulaReadabilityAnalyzer()
        # "make" has one syllable (silent e)
        assert analyzer._count_syllables("make") == 1
        # "home" has one syllable
        assert analyzer._count_syllables("home") == 1

    def test_empty_string_returns_zero(self) -> None:
        """Empty string has zero syllables."""
        analyzer = FormulaReadabilityAnalyzer()
        assert analyzer._count_syllables("") == 0

    def test_minimum_syllable_count(self) -> None:
        """Non-empty words should have at least 1 syllable."""
        analyzer = FormulaReadabilityAnalyzer()
        assert analyzer._count_syllables("xyz") >= 1


# ---------------------------------------------------------------------------
# F. Complex Word Detection
# ---------------------------------------------------------------------------


class TestComplexWordDetection:
    """Words with ≥ 3 syllables are 'complex'."""

    def test_simple_words_not_complex(self) -> None:
        analyzer = FormulaReadabilityAnalyzer()
        assert not analyzer._is_complex_word("cat")
        assert not analyzer._is_complex_word("running")
        assert not analyzer._is_complex_word("simple")

    def test_complex_words_detected(self) -> None:
        analyzer = FormulaReadabilityAnalyzer()
        assert analyzer._is_complex_word("beautiful")
        assert analyzer._is_complex_word("important")
        assert analyzer._is_complex_word("understanding")


# ---------------------------------------------------------------------------
# G. Genre Benchmarks
# ---------------------------------------------------------------------------


class TestGenreBenchmarks:
    """Genre benchmarks are included and correctly structured."""

    @pytest.mark.asyncio
    async def test_benchmarks_includes_all_genres(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """All expected genres are present in benchmarks."""
        result = await analyzer.analyze("Some text here.")
        expected_genres = {"middle_grade", "young_adult", "commercial_fiction", "literary_fiction"}
        assert set(result.genre_benchmarks.keys()) == expected_genres

    @pytest.mark.asyncio
    async def test_benchmarks_are_readability_metrics(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Each benchmark value is a ReadabilityMetrics instance."""
        result = await analyzer.analyze("Some text.")
        for genre, metrics in result.genre_benchmarks.items():
            assert isinstance(metrics, ReadabilityMetrics), f"Genre '{genre}' has wrong type"

    @pytest.mark.asyncio
    async def test_benchmarks_are_ordered_by_difficulty(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """middle_grade has highest reading ease, literary_fiction lowest."""
        result = await analyzer.analyze("Text.")
        mg = result.genre_benchmarks["middle_grade"]
        lf = result.genre_benchmarks["literary_fiction"]
        assert mg.flesch_reading_ease > lf.flesch_reading_ease
        assert mg.flesch_kincaid_grade < lf.flesch_kincaid_grade

    @pytest.mark.asyncio
    async def test_benchmarks_are_copies(
        self,
        analyzer: FormulaReadabilityAnalyzer,
    ) -> None:
        """Each call returns a fresh copy of benchmarks."""
        r1 = await analyzer.analyze("Text one.")
        r2 = await analyzer.analyze("Text two.")
        r1.genre_benchmarks["middle_grade"] = ReadabilityMetrics(
            flesch_reading_ease=999.0,
            flesch_kincaid_grade=0.0,
            gunning_fog=0.0,
            avg_sentence_length=0.0,
            avg_syllables_per_word=0.0,
            complex_word_ratio=0.0,
            word_count=0,
            sentence_count=0,
        )
        assert r2.genre_benchmarks["middle_grade"].flesch_reading_ease == 80.0


# ---------------------------------------------------------------------------
# H. Protocol Compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """FormulaReadabilityAnalyzer satisfies ReadabilityAnalyzer protocol."""

    def test_satisfies_protocol(self) -> None:
        """Instance is recognized as ReadabilityAnalyzer via runtime check."""
        analyzer = FormulaReadabilityAnalyzer()
        assert isinstance(analyzer, ReadabilityAnalyzer)

    @pytest.mark.asyncio
    async def test_analyze_signature_matches_protocol(self) -> None:
        """analyze() has the expected signature."""
        analyzer = FormulaReadabilityAnalyzer()
        result = await analyzer.analyze("Test.", language="en")
        assert isinstance(result, ReadabilityResult)
