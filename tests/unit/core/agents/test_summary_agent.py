"""Tests für ChapterSummaryAgent — Instantiation, Output Function, Basic Behavior.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Output Function wird direkt via ``_process_summary`` getestet
- Keine echten LLM-Calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
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

    @pytest.mark.asyncio
    async def test_run_with_test_model(self) -> None:
        agent = ChapterSummaryAgent(model=TestModel())
        result = await agent.run(
            "Summarize a chapter about a wizard.", deps=SummaryDeps(language="en")
        )
        assert isinstance(result, SummaryOutput)

    @pytest.mark.asyncio
    async def test_run_with_custom_deps(self) -> None:
        agent = ChapterSummaryAgent(model=TestModel())
        deps = SummaryDeps(
            language="de", genre="Sci-Fi", chapter_title="Chapter 5", max_sentences=2
        )
        result = await agent.run("Summarize space battle.", deps=deps)
        assert isinstance(result, SummaryOutput)


# ---------------------------------------------------------------------------
# D. Output Function — _process_summary
# ---------------------------------------------------------------------------


class TestProcessSummary:
    """Output Function wird korrekt ausgeführt."""

    @pytest.fixture()
    def run_context(self) -> RunContext[SummaryDeps]:
        return RunContext[SummaryDeps](deps=SummaryDeps(), model=TestModel(), usage=RunUsage())

    @pytest.mark.asyncio
    async def test_process_summary_with_values(self, run_context: RunContext[SummaryDeps]) -> None:
        result = await ChapterSummaryAgent(model=TestModel())._process_summary(
            run_context,
            summary="The wizard casts a spell and saves the kingdom.",
            key_points=["Wizard casts spell"],
        )
        assert result.summary == "The wizard casts a spell and saves the kingdom."
        assert len(result.key_points) == 1
        assert result.word_count == 9

    @pytest.mark.asyncio
    async def test_process_summary_partial_streaming(
        self, run_context: RunContext[SummaryDeps]
    ) -> None:
        run_context.partial_output = True
        result = await ChapterSummaryAgent(model=TestModel())._process_summary(
            run_context,
            summary="Partial summary.",
            key_points=["Partial"],
        )
        assert result.summary == ""
        assert result.key_points == []
        assert result.word_count == 0

    @pytest.mark.asyncio
    async def test_process_summary_empty(self, run_context: RunContext[SummaryDeps]) -> None:
        result = await ChapterSummaryAgent(model=TestModel())._process_summary(run_context)
        assert result.summary == ""
        assert result.key_points == []
        assert result.word_count == 0

    @pytest.mark.asyncio
    async def test_process_summary_word_count_calculation(
        self, run_context: RunContext[SummaryDeps]
    ) -> None:
        result = await ChapterSummaryAgent(model=TestModel())._process_summary(
            run_context, summary="One two three four five."
        )
        assert result.word_count == 5
