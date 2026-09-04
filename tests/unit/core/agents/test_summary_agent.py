"""Tests für ChapterSummaryAgent — Instantiation und Output-Typen.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Validator-Tests live in ``test_summary_validation.py`` (ADR-035)
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.agents.summary_types import SummaryOutput

# ---------------------------------------------------------------------------
# A. SummaryOutput
# ---------------------------------------------------------------------------


class TestSummaryOutput:
    """SummaryOutput validiert korrekt."""

    def test_defaults(self) -> None:
        output = SummaryOutput()
        assert output.summary == ""
        assert output.key_points == []
        assert output.word_count == 0
        assert output.metadata == {}

    def test_with_values(self) -> None:
        output = SummaryOutput(
            summary="The hero enters the dark forest.", key_points=["First trial"], word_count=15
        )
        assert output.summary == "The hero enters the dark forest."
        assert len(output.key_points) == 1
        assert output.word_count == 15

    def test_serialization(self) -> None:
        data = SummaryOutput(summary="A summary.", key_points=["Point 1"]).model_dump()
        assert data["summary"] == "A summary."
        assert data["key_points"] == ["Point 1"]


# ---------------------------------------------------------------------------
# B. SummaryDeps
# ---------------------------------------------------------------------------


class TestSummaryDeps:
    """SummaryDeps erzeugt und konfiguriert korrekt."""

    def test_defaults(self) -> None:
        deps = SummaryDeps()
        assert deps.language == "en"
        assert deps.genre == ""
        assert deps.chapter_title == ""
        assert deps.max_sentences == 4

    def test_custom_values(self) -> None:
        deps = SummaryDeps(
            language="de", genre="Fantasy", chapter_title="The Awakening", max_sentences=3
        )
        assert deps.language == "de"
        assert deps.genre == "Fantasy"
        assert deps.chapter_title == "The Awakening"
        assert deps.max_sentences == 3


# ---------------------------------------------------------------------------
# C. ChapterSummaryAgent — Instantiation
# ---------------------------------------------------------------------------


class TestChapterSummaryAgent:
    """ChapterSummaryAgent instantiiert und executed korrekt."""

    def test_can_be_instantiated(self) -> None:
        agent = ChapterSummaryAgent(model=TestModel())
        assert isinstance(agent, ChapterSummaryAgent)
