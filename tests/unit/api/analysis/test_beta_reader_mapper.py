"""Unit tests for beta_reader_mapper — response mapping functions."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from narrare.analysis.beta_reader_mapper import (
    build_deepdive_prompt,
    build_user_prompt,
    map_phase1_response,
    map_phase2_response,
)
from narrare.analysis.contracts import FeedbackCategory, FeedbackSeverity
from narrare_core.agents.beta_reader_types import (
    AgentDeepDiveFeedback,
    AgentFeedbackItem,
    AgentOverallAssessment,
    AgentStrength,
    BetaReaderDeps,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)


class TestMapPhase1Response:
    def test_maps_strengths_correctly(self) -> None:
        output = MagicMock(spec=BetaReaderPhase1Output)
        strength = MagicMock(
            spec=AgentStrength,
            category="plot",
            title="Strong plot",
            description="Good plot",
            text_excerpt="text",
        )
        output.strengths = [strength]
        output.feedback = []
        output.questions = []
        overall = MagicMock(
            spec=AgentOverallAssessment,
            summary="Good",
            reader_engagement=8.0,
            emotional_impact=7.0,
            pacing_score=8.0,
            prose_quality=7.0,
            plot_progression=8.0,
            character_development=7.0,
        )
        output.overall = overall

        result = map_phase1_response(output, uuid4(), ["ch1"], word_count=1000)
        assert len(result.strengths) == 1
        assert result.strengths[0].category == FeedbackCategory.PLOT

    def test_maps_feedback_with_severity(self) -> None:
        output = MagicMock(spec=BetaReaderPhase1Output)
        output.strengths = []
        fb = MagicMock(
            spec=AgentFeedbackItem,
            category="character",
            severity="moderate",
            location="p1",
            title="Issue",
            description="Fix this",
            suggestion="Edit",
            text_excerpt="text",
        )
        output.feedback = [fb]
        output.questions = []
        output.overall = MagicMock(
            spec=AgentOverallAssessment,
            summary="OK",
            reader_engagement=5.0,
            emotional_impact=5.0,
            pacing_score=5.0,
            prose_quality=5.0,
            plot_progression=5.0,
            character_development=5.0,
        )

        result = map_phase1_response(output, uuid4(), ["ch1"], word_count=500)
        assert len(result.feedback) == 1
        assert result.feedback[0].severity == FeedbackSeverity.MODERATE

    def test_sets_novel_id_and_word_count(self) -> None:
        novel_id = uuid4()
        output = MagicMock(spec=BetaReaderPhase1Output)
        output.strengths = []
        output.feedback = []
        output.questions = []
        output.overall = MagicMock(
            spec=AgentOverallAssessment,
            summary="",
            reader_engagement=1,
            emotional_impact=1,
            pacing_score=1,
            prose_quality=1,
            plot_progression=1,
            character_development=1,
        )

        result = map_phase1_response(output, novel_id, ["ch1", "ch2"], word_count=3000)
        assert result.novel_id == str(novel_id)
        assert result.total_word_count == 3000


class TestMapPhase2Response:
    def test_maps_detailed_feedback(self) -> None:
        output = MagicMock(spec=BetaReaderPhase2Output)
        detail = MagicMock(
            spec=AgentDeepDiveFeedback,
            category="pacing",
            severity="minor",
            location="p2",
            title="Slow",
            description="Draggy",
            suggestion="Cut",
            text_excerpt="text",
        )
        output.detailed_feedback = [detail]
        output.revision_suggestions = ["Shorten scene"]
        output.category_score = 6

        result = map_phase2_response(output, uuid4(), FeedbackCategory.PACING)
        assert len(result.detailed_feedback) == 1
        assert result.category == FeedbackCategory.PACING
        assert result.category_score == 6


class TestBuildUserPrompt:
    def test_includes_genre_and_chapters(self) -> None:
        deps = MagicMock(spec=BetaReaderDeps)
        deps.genre = "fantasy"
        deps.chapter_titles = ["Chapter 1", "Chapter 2"]
        deps.word_count = 5000
        deps.focus_categories = ["plot", "character"]
        deps.previous_chapter_summaries = []
        deps.kb_characters = []
        deps.kb_locations = []
        deps.chapter_text = "Once upon a time..."

        prompt = build_user_prompt(deps)
        assert "fantasy" in prompt
        assert "Chapter 1" in prompt
        assert "5000" in prompt
        assert "plot" in prompt

    def test_includes_kb_data(self) -> None:
        deps = MagicMock(spec=BetaReaderDeps)
        deps.genre = ""
        deps.chapter_titles = ["Ch1"]
        deps.word_count = 1000
        deps.focus_categories = None
        deps.previous_chapter_summaries = ["Summary of prev"]
        deps.kb_characters = [{"name": "Alice", "summary": "protagonist"}]
        deps.kb_locations = [{"name": "Castle", "summary": "main setting"}]
        deps.chapter_text = "The castle loomed."

        prompt = build_user_prompt(deps)
        assert "Alice" in prompt
        assert "Castle" in prompt
        assert "Summary of prev" in prompt


class TestBuildDeepdivePrompt:
    def test_includes_category_and_phase1_data(self) -> None:
        deps = MagicMock(spec=BetaReaderDeps)
        deps.deepdive_category = "character"
        deps.phase1_strengths_summary = "Strong dialogue"
        deps.phase1_feedback_summary = "Weak pacing"
        deps.chapter_text = "Chapter text here."

        prompt = build_deepdive_prompt(deps)
        assert "character" in prompt
        assert "Strong dialogue" in prompt
        assert "Weak pacing" in prompt
