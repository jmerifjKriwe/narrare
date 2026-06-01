"""Tests for ReadabilityAgent output types and _process_output.

Covers:
1. Output type structure (SentenceIssue, SentenceSuggestion, ReadabilityAgentOutput)
2. Output function (_process_output) with values and streaming
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.readability_agent import ReadabilityAgent, ReadabilityDeps
from narrare_core.agents.readability_types import (
    ReadabilityAgentOutput,
    SentenceIssue,
    SentenceSuggestion,
)

# ---------------------------------------------------------------------------
# A. Output Types
# ---------------------------------------------------------------------------


class TestSentenceIssue:
    """SentenceIssue validates correctly."""

    def test_defaults(self) -> None:
        issue = SentenceIssue()
        assert issue.type == ""
        assert issue.description == ""

    def test_with_values(self) -> None:
        issue = SentenceIssue(type="too_long", description="Sentence has 40 words.")
        assert issue.type == "too_long"
        assert issue.description == "Sentence has 40 words."

    def test_serialization(self) -> None:
        data = SentenceIssue(type="passive_voice", description="Passive construct.").model_dump()
        assert data["type"] == "passive_voice"
        assert data["description"] == "Passive construct."


class TestSentenceSuggestion:
    """SentenceSuggestion validates correctly."""

    def test_defaults(self) -> None:
        s = SentenceSuggestion()
        assert s.alternative == ""
        assert s.improvement == ""

    def test_with_values(self) -> None:
        s = SentenceSuggestion(
            alternative="She ran quickly.",
            improvement="Active voice replaces passive construct.",
        )
        assert s.alternative == "She ran quickly."

    def test_serialization(self) -> None:
        data = SentenceSuggestion(alternative="Short.", improvement="Shorter.").model_dump()
        assert data["alternative"] == "Short."


class TestReadabilityAgentOutput:
    """ReadabilityAgentOutput validates correctly."""

    def test_defaults(self) -> None:
        output = ReadabilityAgentOutput()
        assert output.problematic_sentences == []
        assert output.overall_assessment == ""

    def test_with_values(self) -> None:
        sentences = [
            {
                "sentence": "The thing was being done by the person.",
                "position": 0,
                "issues": [{"type": "passive_voice", "description": "Passive construct."}],
                "suggestions": [
                    {"alternative": "The person did the thing.", "improvement": "Active voice."},
                ],
            },
        ]
        output = ReadabilityAgentOutput(
            problematic_sentences=sentences,
            overall_assessment="Generally clear with minor issues.",
        )
        assert len(output.problematic_sentences) == 1
        assert output.overall_assessment == "Generally clear with minor issues."

    def test_serialization(self) -> None:
        output = ReadabilityAgentOutput(
            overall_assessment="Easy to read.",
        )
        data = output.model_dump()
        assert data["overall_assessment"] == "Easy to read."
        assert data["problematic_sentences"] == []


# ---------------------------------------------------------------------------
# D. Output Function — _process_output
# ---------------------------------------------------------------------------


class TestProcessOutput:
    """Output Function structures the LLM response correctly."""

    @pytest.fixture()
    def run_context(self) -> RunContext[ReadabilityDeps]:
        return RunContext[ReadabilityDeps](
            deps=ReadabilityDeps(),
            model=TestModel(),
            usage=RunUsage(),
        )

    @pytest.mark.asyncio
    async def test_process_output_with_values(
        self,
        run_context: RunContext[ReadabilityDeps],
    ) -> None:
        sentences = [
            {"sentence": "Long sentence.", "position": 0, "issues": [], "suggestions": []},
        ]
        result = await ReadabilityAgent(model=TestModel())._process_output(
            run_context,
            problematic_sentences=sentences,
            overall_assessment="Clear text overall.",
        )
        assert len(result.problematic_sentences) == 1
        assert result.overall_assessment == "Clear text overall."

    @pytest.mark.asyncio
    async def test_process_output_partial_streaming(
        self,
        run_context: RunContext[ReadabilityDeps],
    ) -> None:
        run_context.partial_output = True
        result = await ReadabilityAgent(model=TestModel())._process_output(
            run_context,
            problematic_sentences=[{"sentence": "test"}],
            overall_assessment="Partial.",
        )
        # Streaming returns empty output
        assert result.problematic_sentences == []
        assert result.overall_assessment == ""

    @pytest.mark.asyncio
    async def test_process_output_empty(
        self,
        run_context: RunContext[ReadabilityDeps],
    ) -> None:
        result = await ReadabilityAgent(model=TestModel())._process_output(
            run_context,
        )
        assert result.problematic_sentences == []
        assert result.overall_assessment == ""

    @pytest.mark.asyncio
    async def test_process_output_returns_correct_type(
        self,
        run_context: RunContext[ReadabilityDeps],
    ) -> None:
        result = await ReadabilityAgent(model=TestModel())._process_output(
            run_context,
            overall_assessment="Test.",
        )
        assert isinstance(result, ReadabilityAgentOutput)
