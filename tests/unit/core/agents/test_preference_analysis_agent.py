"""Tests for agents/preference_analysis_agent.py — PreferenceAnalysisAgent.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_ai.models.test import TestModel

from narrare_core.agents.preference_analysis_agent import (
    PreferenceAnalysisAgent,
    PreferenceAnalysisDeps,
)
from narrare_core.agents.preference_analysis_types import PreferenceAnalysisOutput

# ---------------------------------------------------------------------------
# A. PreferenceAnalysisOutput
# ---------------------------------------------------------------------------


class TestPreferenceAnalysisOutput:
    """PreferenceAnalysisOutput validates correctly."""

    def test_defaults(self) -> None:
        output = PreferenceAnalysisOutput()
        assert output.style_patterns == []
        assert output.content_patterns == []
        assert output.avoidance_patterns == []
        assert output.confidence == 0.0
        assert output.summary == ""

    def test_with_values(self) -> None:
        output = PreferenceAnalysisOutput(
            style_patterns=["prefers concise sentences"],
            content_patterns=["favors dialogue over description"],
            avoidance_patterns=["dislikes cliffhangers"],
            confidence=0.85,
            summary="User prefers tight prose with dialogue.",
        )
        assert len(output.style_patterns) == 1
        assert len(output.content_patterns) == 1
        assert len(output.avoidance_patterns) == 1
        assert output.confidence == 0.85
        assert "tight prose" in output.summary

    def test_confidence_boundary_zero(self) -> None:
        output = PreferenceAnalysisOutput(confidence=0.0)
        assert output.confidence == 0.0

    def test_confidence_boundary_one(self) -> None:
        output = PreferenceAnalysisOutput(confidence=1.0)
        assert output.confidence == 1.0

    def test_confidence_rejects_above_one(self) -> None:
        with pytest.raises(ValidationError):
            PreferenceAnalysisOutput(confidence=1.5)

    def test_confidence_rejects_below_zero(self) -> None:
        with pytest.raises(ValidationError):
            PreferenceAnalysisOutput(confidence=-0.1)

    def test_serialization(self) -> None:
        output = PreferenceAnalysisOutput(
            style_patterns=["concise"],
            confidence=0.7,
        )
        data = output.model_dump()
        assert data["style_patterns"] == ["concise"]
        assert data["confidence"] == 0.7


# ---------------------------------------------------------------------------
# B. PreferenceAnalysisDeps
# ---------------------------------------------------------------------------


class TestPreferenceAnalysisDeps:
    """PreferenceAnalysisDeps creates and configures correctly."""

    def test_defaults(self) -> None:
        deps = PreferenceAnalysisDeps()
        assert deps.language == "en"
        assert deps.genre == ""
        assert deps.event_count == 0
        assert deps.feedback_text == ""

    def test_custom_values(self) -> None:
        deps = PreferenceAnalysisDeps(
            language="de",
            genre="Fantasy",
            event_count=42,
            feedback_text="User accepted 30 suggestions...",
        )
        assert deps.language == "de"
        assert deps.genre == "Fantasy"
        assert deps.event_count == 42
        assert "accepted 30" in deps.feedback_text


# ---------------------------------------------------------------------------
# C. PreferenceAnalysisAgent — Instantiation
# ---------------------------------------------------------------------------


class TestPreferenceAnalysisAgentInstantiation:
    """PreferenceAnalysisAgent instantiates and executes correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = PreferenceAnalysisAgent(model=TestModel())
        assert isinstance(agent, PreferenceAnalysisAgent)

    @pytest.mark.asyncio
    async def test_run_with_test_model(self) -> None:
        agent = PreferenceAnalysisAgent(model=TestModel())
        deps = PreferenceAnalysisDeps(
            language="en",
            event_count=10,
            feedback_text="Some feedback text",
        )
        result = await agent.run("Analyze the following feedback history.", deps=deps)
        assert isinstance(result, PreferenceAnalysisOutput)

    @pytest.mark.asyncio
    async def test_run_with_custom_deps(self) -> None:
        agent = PreferenceAnalysisAgent(model=TestModel())
        deps = PreferenceAnalysisDeps(
            language="de",
            genre="Sci-Fi",
            event_count=50,
            feedback_text="User rejected long descriptions consistently.",
        )
        result = await agent.run("Analyze feedback.", deps=deps)
        assert isinstance(result, PreferenceAnalysisOutput)
