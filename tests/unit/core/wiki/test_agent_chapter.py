"""Tests for WikiChapterGenerator and generate_chapter path.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Output Function (``_process_output``) wird direkt via WikiChapterGenerator getestet
- generate_chapter auf WikiGenerationAgent testet die Integration
- Keine echten LLM-Calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.wiki.agent import WikiGenerationAgent
from narrare_core.wiki.agent_chapter import WikiChapterGenerator
from narrare_core.wiki.types import WikiChapterOutput, WikiGenerationDeps

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def deps_chapter() -> WikiGenerationDeps:
    """Generation deps for chapter summary."""
    return WikiGenerationDeps(
        language="en",
        genre="Fantasy",
        entity_type="chapter",
        entity_name="The Crystal Cave",
        entity_body="Lyra and Eldrin descend into the crystal cave...",
        entity_metadata={"chapter_number": 7},
        relationships=[
            {"name": "Lyra", "role": "protagonist", "significance": 0.9},
            {"name": "Eldrin", "role": "mentor", "significance": 0.7},
        ],
        chapter_context=["Full chapter text here..."],
    )


@pytest.fixture()
def deps() -> WikiGenerationDeps:
    """Default generation deps for a character entity (used for chapter fallback test)."""
    return WikiGenerationDeps(
        language="en",
        genre="Fantasy",
        entity_type="character",
        entity_name="Eldrin the Wise",
        entity_body="Eldrin is an ancient wizard who guards the Crystal of Eternity.",
        entity_metadata={"age": "immortal", "alignment": "neutral good"},
        relationships=[
            {"name": "Lyra", "type": "apprentice", "context": "Chapter 3"},
            {"name": "Morgath", "type": "rival", "context": "Chapter 5"},
        ],
        chapter_context=["Chapter 3: Eldrin teaches Lyra about the crystal."],
    )


@pytest.fixture()
def run_context(deps_chapter: WikiGenerationDeps) -> RunContext[WikiGenerationDeps]:
    """Basic RunContext for testing output functions."""
    return RunContext[WikiGenerationDeps](deps=deps_chapter, model=TestModel(), usage=RunUsage())


# ---------------------------------------------------------------------------
# A. generate_chapter via WikiGenerationAgent
# ---------------------------------------------------------------------------


class TestGenerateChapter:
    """generate_chapter mit TestModel (via WikiGenerationAgent)."""

    @pytest.mark.asyncio
    async def test_generate_chapter_returns_output(self, deps_chapter: WikiGenerationDeps) -> None:
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent.generate_chapter(deps=deps_chapter)
        assert isinstance(result, WikiChapterOutput)
        # TestModel with output function returns default values
        assert result.narrative_summary == ""
        assert result.key_events == []
        assert result.entities_involved == []
        assert result.themes == []

    @pytest.mark.asyncio
    async def test_generate_chapter_with_entity_deps_falls_back(
        self, deps: WikiGenerationDeps
    ) -> None:
        """Chapter generation with entity deps (entity_type=character) still works."""
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent.generate_chapter(deps=deps)
        assert isinstance(result, WikiChapterOutput)


# ---------------------------------------------------------------------------
# B. Output Function: WikiChapterGenerator._process_output
# ---------------------------------------------------------------------------


class TestProcessChapterOutput:
    """Chapter output function tests (WikiChapterGenerator)."""

    @pytest.mark.asyncio
    async def test_with_full_values(self, run_context: RunContext[WikiGenerationDeps]) -> None:
        generator = WikiChapterGenerator(model=TestModel())
        result = await generator._process_output(
            run_context,
            narrative_summary="Lyra and Eldrin descend into the cave.",
            key_events=["Enter cave", "Find crystal", "Confront guardian"],
            entities_involved=[
                {"name": "Lyra", "role": "protagonist", "significance": 0.9},
            ],
            themes=["Discovery", "Courage"],
            emotional_arc="From tension to triumph.",
        )
        assert result.narrative_summary == "Lyra and Eldrin descend into the cave."
        assert len(result.key_events) == 3
        assert len(result.entities_involved) == 1
        assert len(result.themes) == 2
        assert result.emotional_arc == "From tension to triumph."

    @pytest.mark.asyncio
    async def test_partial_streaming(self, run_context: RunContext[WikiGenerationDeps]) -> None:
        run_context.partial_output = True
        generator = WikiChapterGenerator(model=TestModel())
        result = await generator._process_output(
            run_context,
            narrative_summary="Partial...",
            key_events=["Partial event"],
        )
        assert result.narrative_summary == ""
        assert result.key_events == []
        assert result.entities_involved == []
        assert result.themes == []

    @pytest.mark.asyncio
    async def test_empty_defaults(self, run_context: RunContext[WikiGenerationDeps]) -> None:
        generator = WikiChapterGenerator(model=TestModel())
        result = await generator._process_output(run_context)
        assert result.narrative_summary == ""
        assert result.key_events == []
        assert result.entities_involved == []
        assert result.themes == []
