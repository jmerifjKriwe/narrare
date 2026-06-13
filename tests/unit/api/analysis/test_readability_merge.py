"""Unit tests for ReadabilityService._merge_agent_result and _build_deps.

Extracted from test_readability_service.py for RULE-04 compliance.
"""

from __future__ import annotations

from narrare.analysis.services.readability_service import (
    ReadabilityService,
    _build_deps,
)
from narrare_core.analysis.types import ReadabilityMetrics, ReadabilityResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_METRICS = ReadabilityMetrics(
    flesch_reading_ease=75.0,
    flesch_kincaid_grade=5.0,
    gunning_fog=7.0,
    avg_sentence_length=12.0,
    avg_syllables_per_word=1.3,
    complex_word_ratio=0.05,
    word_count=50,
    sentence_count=4,
)


def _formula_result() -> ReadabilityResult:
    return ReadabilityResult(
        metrics=_METRICS,
        genre_benchmarks={},
        sentence_analyses=[],
        overall_assessment=None,
    )


# ---------------------------------------------------------------------------
# _merge_agent_result — static method
# ---------------------------------------------------------------------------


class TestMergeAgentResult:
    def test_empty_output_returns_no_analyses(self) -> None:
        result = ReadabilityService._merge_agent_result(
            _formula_result(), {"problematic_sentences": [], "overall_assessment": "Fine."}
        )
        assert result.sentence_analyses == []
        assert result.overall_assessment == "Fine."

    def test_issues_as_list_of_strings(self) -> None:
        result = ReadabilityService._merge_agent_result(
            _formula_result(),
            {
                "problematic_sentences": [
                    {
                        "sentence": "Too long.",
                        "sentence_index": 1,
                        "issues": ["too_long", "passive_voice"],
                        "readability_score": 0.3,
                        "suggestions": [],
                    }
                ],
                "overall_assessment": "Needs work.",
            },
        )
        assert result.sentence_analyses[0].issues == ["too_long", "passive_voice"]

    def test_issues_as_non_list_string(self) -> None:
        result = ReadabilityService._merge_agent_result(
            _formula_result(),
            {
                "problematic_sentences": [
                    {
                        "sentence": "Bad.",
                        "sentence_index": 0,
                        "issues": "just_one_string",
                        "readability_score": 0.2,
                        "suggestions": [],
                    }
                ],
                "overall_assessment": "Bad.",
            },
        )
        assert result.sentence_analyses[0].issues == ["just_one_string"]

    def test_suggestions_as_list_of_dicts(self) -> None:
        result = ReadabilityService._merge_agent_result(
            _formula_result(),
            {
                "problematic_sentences": [
                    {
                        "sentence": "Hard.",
                        "sentence_index": 0,
                        "issues": [],
                        "readability_score": 0.1,
                        "suggestions": [{"alternative": "Easier.", "improvement": "Shorter."}],
                    }
                ],
                "overall_assessment": "Some issues.",
            },
        )
        assert result.sentence_analyses[0].suggestions == ["Easier."]

    def test_suggestions_as_list_of_strings(self) -> None:
        result = ReadabilityService._merge_agent_result(
            _formula_result(),
            {
                "problematic_sentences": [
                    {
                        "sentence": "Hard.",
                        "sentence_index": 0,
                        "issues": [],
                        "readability_score": 0.1,
                        "suggestions": ["Try this."],
                    }
                ],
                "overall_assessment": "OK",
            },
        )
        assert result.sentence_analyses[0].suggestions == ["Try this."]

    def test_suggestions_as_non_list_string(self) -> None:
        result = ReadabilityService._merge_agent_result(
            _formula_result(),
            {
                "problematic_sentences": [
                    {
                        "sentence": "Hard.",
                        "sentence_index": 0,
                        "issues": [],
                        "readability_score": 0.1,
                        "suggestions": "Single suggestion.",
                    }
                ],
                "overall_assessment": "OK",
            },
        )
        assert result.sentence_analyses[0].suggestions == ["Single suggestion."]

    def test_overall_assessment_empty_becomes_none(self) -> None:
        result = ReadabilityService._merge_agent_result(
            _formula_result(), {"problematic_sentences": [], "overall_assessment": ""}
        )
        assert result.overall_assessment is None

    def test_metrics_carried_from_formula_result(self) -> None:
        formula = _formula_result()
        result = ReadabilityService._merge_agent_result(
            formula, {"problematic_sentences": [], "overall_assessment": "Good."}
        )
        assert result.metrics is formula.metrics
        assert result.genre_benchmarks == formula.genre_benchmarks

    def test_multiple_problematic_sentences(self) -> None:
        result = ReadabilityService._merge_agent_result(
            _formula_result(),
            {
                "problematic_sentences": [
                    {
                        "sentence": "First.",
                        "sentence_index": 0,
                        "issues": [],
                        "readability_score": 0.5,
                    },
                    {
                        "sentence": "Second.",
                        "sentence_index": 1,
                        "issues": [],
                        "readability_score": 0.4,
                    },
                ],
                "overall_assessment": "Two issues.",
            },
        )
        assert len(result.sentence_analyses) == 2
        assert result.sentence_analyses[0].sentence == "First."
        assert result.sentence_analyses[1].sentence == "Second."


# ---------------------------------------------------------------------------
# _build_deps — module-level helper
# ---------------------------------------------------------------------------


class TestBuildDeps:
    def test_creates_deps_with_text_and_language(self) -> None:
        deps = _build_deps("Some text.", "fr")
        assert deps.text == "Some text."
        assert deps.language == "fr"

    def test_default_language(self) -> None:
        deps = _build_deps("Text.", "en")
        assert deps.language == "en"
