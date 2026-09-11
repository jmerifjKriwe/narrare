"""Tests for TemporalExtractionAgent — instantiation, deps, and run.

Covers:
1. TemporalExtractionDeps defaults and custom values
2. Agent instantiation
3. Agent run with TestModel (deterministic, no LLM calls)
4. ExtractedTemporalExpression model behaviour
5. TemporalExtractionOutput model behaviour
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.temporal_extraction_agent import (
    TemporalExtractionAgent,
    TemporalExtractionDeps,
)
from narrare_core.agents.temporal_extraction_types import (
    ExtractedTemporalExpression,
    TemporalExtractionOutput,
)

# ---------------------------------------------------------------------------
# A. TemporalExtractionDeps
# ---------------------------------------------------------------------------


class TestTemporalExtractionDeps:
    """TemporalExtractionDeps creates and configures correctly."""

    def test_defaults(self) -> None:
        deps = TemporalExtractionDeps()
        assert deps.genre == ""
        assert deps.language == "en"
        assert deps.existing_events == []

    def test_custom_values(self) -> None:
        deps = TemporalExtractionDeps(
            genre="Fantasy",
            language="de",
            existing_events=["Battle of Helm's Deep", "Arrival at Rivendell"],
        )
        assert deps.genre == "Fantasy"
        assert deps.language == "de"
        assert len(deps.existing_events) == 2
        assert "Battle of Helm's Deep" in deps.existing_events

    def test_existing_events_none_becomes_empty_list(self) -> None:
        deps = TemporalExtractionDeps(existing_events=None)
        assert deps.existing_events == []


# ---------------------------------------------------------------------------
# B. TemporalExtractionAgent — Instantiation
# ---------------------------------------------------------------------------


class TestTemporalExtractionAgentInstantiation:
    """TemporalExtractionAgent instantiates correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = TemporalExtractionAgent(model=TestModel())
        assert isinstance(agent, TemporalExtractionAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        agent = TemporalExtractionAgent(
            model=TestModel(),
            system_prompt="You are a temporal expression extractor.",
        )
        assert isinstance(agent, TemporalExtractionAgent)


# ---------------------------------------------------------------------------
# C. TemporalExtractionAgent — Run with TestModel
# ---------------------------------------------------------------------------


class TestTemporalExtractionAgentRun:
    """TemporalExtractionAgent executes with TestModel (deterministic, no LLM)."""

    @pytest.mark.asyncio
    async def test_run_returns_output(self) -> None:
        agent = TemporalExtractionAgent(model=TestModel())
        deps = TemporalExtractionDeps(genre="Fantasy", language="en")
        result = await agent.run("Extract temporal expressions.", deps=deps)
        assert isinstance(result, TemporalExtractionOutput)

    @pytest.mark.asyncio
    async def test_run_with_custom_deps(self) -> None:
        agent = TemporalExtractionAgent(model=TestModel())
        deps = TemporalExtractionDeps(
            genre="Sci-Fi",
            language="de",
            existing_events=["Launch of the ship", "Arrival at Mars"],
        )
        result = await agent.run("Extrahiere temporale Ausdrücke.", deps=deps)
        assert isinstance(result, TemporalExtractionOutput)

    @pytest.mark.asyncio
    async def test_run_with_system_prompt(self) -> None:
        agent = TemporalExtractionAgent(
            model=TestModel(),
            system_prompt="You are a temporal expression extractor.",
        )
        deps = TemporalExtractionDeps(genre="Fantasy")
        result = await agent.run("Extract.", deps=deps)
        assert isinstance(result, TemporalExtractionOutput)


# ---------------------------------------------------------------------------
# D. ExtractedTemporalExpression
# ---------------------------------------------------------------------------


class TestExtractedTemporalExpression:
    """ExtractedTemporalExpression model works correctly."""

    def test_defaults(self) -> None:
        expr = ExtractedTemporalExpression()
        assert expr.expression == ""
        assert expr.event_name == ""
        assert expr.timestamp_raw == ""
        assert expr.chapter_reference == ""
        assert expr.character_names == []
        assert expr.location_name == ""
        assert expr.confidence == 0.0
        assert expr.context == ""

    def test_custom_values(self) -> None:
        expr = ExtractedTemporalExpression(
            expression="three days later",
            event_name="Arrival at the castle",
            timestamp_raw="three days later",
            chapter_reference="Chapter 5",
            character_names=["Aragorn", "Legolas"],
            location_name="Helm's Deep",
            confidence=0.9,
            context="Three days later, they arrived at the castle.",
        )
        assert expr.expression == "three days later"
        assert expr.event_name == "Arrival at the castle"
        assert expr.confidence == 0.9
        assert len(expr.character_names) == 2


# ---------------------------------------------------------------------------
# E. TemporalExtractionOutput
# ---------------------------------------------------------------------------


class TestTemporalExtractionOutput:
    """TemporalExtractionOutput model works correctly."""

    def test_defaults(self) -> None:
        output = TemporalExtractionOutput()
        assert output.extracted == []
        assert output.chapter_temporal_markers == []
        assert output.extraction_notes == ""
        assert output.metadata == {}

    def test_with_extractions(self) -> None:
        expr = ExtractedTemporalExpression(
            expression="that evening",
            event_name="Council meeting",
            timestamp_raw="that evening",
            chapter_reference="Chapter 2",
            confidence=0.85,
            context="That evening, the council gathered.",
        )
        output = TemporalExtractionOutput(
            extracted=[expr],
            chapter_temporal_markers=["that evening", "later"],
            extraction_notes="Found 1 temporal expression with high confidence.",
        )
        assert len(output.extracted) == 1
        assert output.extracted[0].expression == "that evening"
        assert len(output.chapter_temporal_markers) == 2
        assert "high confidence" in output.extraction_notes
