"""Tests for ReadabilityAgent output types.

Covers:
1. Output type structure (SentenceIssue, SentenceSuggestion, ReadabilityAgentOutput)
"""

from __future__ import annotations

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
