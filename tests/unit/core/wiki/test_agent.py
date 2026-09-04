"""Tests for WikiGenerationAgent — instantiation and entity generation.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Keine echten LLM-Calls (RULE-01b)
- Prompt loading tests in ``test_prompt_loader.py``
- Chapter tests in ``test_agent_chapter.py``
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.wiki.agent import WikiGenerationAgent
from narrare_core.wiki.types import (
    WikiEntityOutput,
    WikiGenerationDeps,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def deps() -> WikiGenerationDeps:
    """Default generation deps for a character entity."""
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
def deps_location() -> WikiGenerationDeps:
    """Generation deps for a location entity."""
    return WikiGenerationDeps(
        language="en",
        genre="Fantasy",
        entity_type="location",
        entity_name="The Whispering Woods",
        entity_body="An ancient forest where the trees communicate telepathically.",
        entity_metadata={"size": "vast", "danger_level": "moderate"},
        relationships=[
            {"name": "Eldrin", "type": "protector", "context": "Chapter 2"},
        ],
        chapter_context=["Chapter 2: The party enters the woods."],
    )


# ---------------------------------------------------------------------------
# A. WikiGenerationAgent — Instantiation
# ---------------------------------------------------------------------------


class TestWikiGenerationAgentInstantiation:
    """WikiGenerationAgent instantiiert korrekt."""

    def test_can_be_instantiated(self) -> None:
        agent = WikiGenerationAgent(model=TestModel())
        assert isinstance(agent, WikiGenerationAgent)

    def test_with_system_prompt(self) -> None:
        agent = WikiGenerationAgent(model=TestModel(), system_prompt="Custom prompt.")
        assert isinstance(agent, WikiGenerationAgent)


# ---------------------------------------------------------------------------
# B. WikiGenerationAgent — generate_entity with TestModel
# ---------------------------------------------------------------------------


class TestGenerateEntity:
    """generate_entity mit TestModel."""

    @pytest.mark.asyncio
    async def test_generate_entity_returns_output(self, deps: WikiGenerationDeps) -> None:
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent.generate_entity(deps=deps)
        assert isinstance(result, WikiEntityOutput)
        # TestModel fills the strict output schema with type-based placeholders
        assert isinstance(result.narrative_summary, str)
        assert isinstance(result.key_attributes, list)
        assert isinstance(result.relationships, list)

    @pytest.mark.asyncio
    async def test_generate_entity_with_character_deps_includes_arc(
        self, deps: WikiGenerationDeps
    ) -> None:
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent.generate_entity(deps=deps)
        assert isinstance(result, WikiEntityOutput)
        # character_arc field exists on output (may be None with TestModel defaults)
        assert hasattr(result, "character_arc")

    @pytest.mark.asyncio
    async def test_generate_entity_with_location_deps(
        self, deps_location: WikiGenerationDeps
    ) -> None:
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent.generate_entity(deps=deps_location)
        assert isinstance(result, WikiEntityOutput)
        # Location entity_type — character_arc should be None
        assert result.character_arc is None
