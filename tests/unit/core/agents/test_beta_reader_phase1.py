"""Tests for BetaReaderAgent — Phase 1 output parsing, instantiation, and edge cases.

Test strategy:
- TestModel for deterministic agent tests
- Output functions tested directly via _process_phase1
- No real LLM calls (RULE-01b)

Split from test_beta_reader_agent.py to stay under 200 lines (RULE-04).
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.beta_reader_agent import BetaReaderAgent
from narrare_core.agents.beta_reader_processors import process_beta_reader_phase1
from narrare_core.agents.beta_reader_types import (
    BetaReaderDeps,
    BetaReaderPhase1Output,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_context(**overrides: object) -> RunContext[BetaReaderDeps]:
    """Create a RunContext with default BetaReaderDeps."""
    deps = BetaReaderDeps(**overrides)  # type: ignore[arg-type]
    return RunContext[BetaReaderDeps](deps=deps, model=TestModel(), usage=RunUsage())


# ---------------------------------------------------------------------------
# A. BetaReaderDeps defaults
# ---------------------------------------------------------------------------


class TestBetaReaderDeps:
    """BetaReaderDeps creates correctly with defaults."""

    def test_defaults(self) -> None:
        deps = BetaReaderDeps()
        assert deps.language == "en"
        assert deps.chapter_text == ""
        assert deps.chapter_titles == []
        assert deps.word_count == 0
        assert deps.previous_chapter_summaries == []
        assert deps.kb_characters == ""
        assert deps.kb_locations == ""
        assert deps.genre == ""
        assert deps.focus_categories is None
        assert deps.deepdive_category is None

    def test_custom_values(self) -> None:
        deps = BetaReaderDeps(
            language="de",
            chapter_text="Some text",
            chapter_titles=["Chapter 1"],
            word_count=500,
            genre="Fantasy",
            focus_categories=["plot", "character"],
            deepdive_category="prose",
        )
        assert deps.language == "de"
        assert deps.word_count == 500
        assert deps.deepdive_category == "prose"


# ---------------------------------------------------------------------------
# B. Phase 1 output parsing
# ---------------------------------------------------------------------------


class TestProcessPhase1:
    """_process_phase1 structures LLM response correctly."""

    @pytest.mark.asyncio
    async def test_partial_output_returns_defaults(self) -> None:
        """During streaming (partial_output), returns empty defaults."""
        ctx = _make_run_context()
        ctx.partial_output = True

        result = await process_beta_reader_phase1(ctx)

        assert isinstance(result, BetaReaderPhase1Output)
        assert result.strengths == []
        assert result.feedback == []
        assert result.questions == []
        assert result.overall.summary == ""
        assert result.overall.reader_engagement == 5

    @pytest.mark.asyncio
    async def test_full_output_maps_correctly(self) -> None:
        """Full LLM response maps to structured output."""
        ctx = _make_run_context()

        result = await process_beta_reader_phase1(
            ctx,
            strengths=[
                {"category": "plot", "title": "Strong opening", "description": "Engaging start"},
            ],
            feedback=[
                {
                    "category": "character",
                    "severity": "moderate",
                    "title": "Flat dialogue",
                    "description": "Dialogues feel uniform",
                    "suggestion": "Add character-specific speech patterns",
                },
            ],
            questions=[
                {
                    "category": "plot",
                    "question": "Where is the antagonist?",
                    "context": "Not mentioned",
                },
            ],
            overall={
                "summary": "A promising chapter",
                "reader_engagement": 7,
                "emotional_impact": 6,
                "pacing_score": 8,
                "prose_quality": 7,
                "plot_progression": 6,
                "character_development": 5,
            },
        )

        assert len(result.strengths) == 1
        assert result.strengths[0].title == "Strong opening"
        assert len(result.feedback) == 1
        assert result.feedback[0].severity == "moderate"
        assert len(result.questions) == 1
        assert result.overall.summary == "A promising chapter"
        assert result.overall.reader_engagement == 7

    @pytest.mark.asyncio
    async def test_empty_input_returns_minimal_output(self) -> None:
        """No arguments produces empty lists and default overall."""
        ctx = _make_run_context()

        result = await process_beta_reader_phase1(ctx)

        assert result.strengths == []
        assert result.feedback == []
        assert result.questions == []
        assert result.overall.summary == ""


# ---------------------------------------------------------------------------
# C. Agent instantiation and run delegation
# ---------------------------------------------------------------------------


class TestBetaReaderAgent:
    """Agent instantiation and default run() delegation."""

    def test_instantiation_with_test_model(self) -> None:
        """Agent can be instantiated with TestModel."""
        agent = BetaReaderAgent(model=TestModel())
        assert isinstance(agent, BetaReaderAgent)

    @pytest.mark.asyncio
    async def test_run_delegates_to_run_phase1(self) -> None:
        """Default run() delegates to run_phase1()."""
        agent = BetaReaderAgent(model=TestModel())
        deps = BetaReaderDeps(chapter_text="Test chapter content.")

        result = await agent.run(prompt="Analyze this", deps=deps)

        assert isinstance(result, BetaReaderPhase1Output)
