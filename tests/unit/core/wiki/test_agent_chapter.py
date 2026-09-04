"""Tests for generate_chapter path (WikiGenerationAgent → WikiChapterGenerator).

Test-Strategie:
- TestModel für deterministische Agent-Tests
- generate_chapter auf WikiGenerationAgent testet die Integration
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.wiki.agent import WikiGenerationAgent
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
        # TestModel fills the strict output schema with type-based placeholders
        assert isinstance(result.narrative_summary, str)
        assert isinstance(result.key_events, list)
        assert isinstance(result.entities_involved, list)
        assert isinstance(result.themes, list)

    @pytest.mark.asyncio
    async def test_generate_chapter_with_entity_deps_falls_back(
        self, deps: WikiGenerationDeps
    ) -> None:
        """Chapter generation with entity deps (entity_type=character) still works."""
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent.generate_chapter(deps=deps)
        assert isinstance(result, WikiChapterOutput)
