"""Tests for BetaReaderAgent — Phase 1 instantiation, run delegation, and edge cases.

Test strategy:
- TestModel for deterministic agent tests (valid ``custom_output_args`` —
  the agent registers an ADR-035 validator that rejects placeholder output)
- No real LLM calls (RULE-01b)

Split from test_beta_reader_agent.py to stay under 200 lines (RULE-04).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.beta_reader_agent import BetaReaderAgent
from narrare_core.agents.beta_reader_types import (
    BetaReaderDeps,
    BetaReaderPhase1Output,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _phase1_output_args() -> dict[str, Any]:
    """Build valid ``final_result`` tool args for BetaReaderPhase1Output."""
    return {
        "strengths": [
            {"category": "plot", "title": "Strong opening", "description": "Engaging start"},
        ],
        "feedback": [
            {
                "category": "character",
                "severity": "moderate",
                "title": "Flat dialogue",
                "description": "Dialogues feel uniform",
                "suggestion": "Add character-specific speech patterns",
            },
        ],
        "questions": [
            {
                "category": "plot",
                "question": "Where is the antagonist?",
                "context": "Not mentioned",
            },
        ],
        "overall": {
            "summary": "A promising chapter",
            "reader_engagement": 7,
            "emotional_impact": 6,
            "pacing_score": 8,
            "prose_quality": 7,
            "plot_progression": 6,
            "character_development": 5,
        },
    }


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
# B. Agent instantiation and run delegation
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
        model = TestModel(custom_output_args=_phase1_output_args())
        agent = BetaReaderAgent(model=model)
        deps = BetaReaderDeps(chapter_text="Test chapter content.")

        result = await agent.run(prompt="Analyze this", deps=deps)

        assert isinstance(result, BetaReaderPhase1Output)
        assert result.overall.summary == "A promising chapter"
        assert result.strengths[0].title == "Strong opening"
