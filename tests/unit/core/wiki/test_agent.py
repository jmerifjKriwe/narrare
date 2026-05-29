"""Tests for WikiGenerationAgent — instantiation, entity generation, entity output functions.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Output Functions werden direkt via ``_process_entity_output`` getestet
- Keine echten LLM-Calls (RULE-01)
- Prompt loading tests in ``test_prompt_loader.py``
- Chapter tests in ``test_agent_chapter.py``
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
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


@pytest.fixture()
def run_context(deps: WikiGenerationDeps) -> RunContext[WikiGenerationDeps]:
    """Basic RunContext for testing output functions."""
    return RunContext[WikiGenerationDeps](deps=deps, model=TestModel(), usage=RunUsage())


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
        # TestModel with output function returns default values
        assert result.narrative_summary == ""
        assert result.key_attributes == []
        assert result.relationships == []

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


# ---------------------------------------------------------------------------
# C. Output Function: _process_entity_output
# ---------------------------------------------------------------------------


class TestProcessEntityOutput:
    """Entity output function tests."""

    @pytest.mark.asyncio
    async def test_with_full_values(self, run_context: RunContext[WikiGenerationDeps]) -> None:
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent._process_entity_output(
            run_context,
            narrative_summary="Eldrin is a wise wizard who guards the crystal.",
            role_in_story="Mentor to the protagonist.",
            key_attributes=["wise", "ancient", "powerful"],
            relationships=[
                {"target": "Lyra", "type": "apprentice"},
            ],
            character_arc="From isolation to mentorship.",
        )
        assert result.narrative_summary == "Eldrin is a wise wizard who guards the crystal."
        assert result.role_in_story == "Mentor to the protagonist."
        assert len(result.key_attributes) == 3
        assert len(result.relationships) == 1
        assert result.character_arc == "From isolation to mentorship."

    @pytest.mark.asyncio
    async def test_partial_streaming(self, run_context: RunContext[WikiGenerationDeps]) -> None:
        run_context.partial_output = True
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent._process_entity_output(
            run_context,
            narrative_summary="Partial...",
            key_attributes=["wise"],
        )
        assert result.narrative_summary == ""
        assert result.key_attributes == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_empty_defaults(self, run_context: RunContext[WikiGenerationDeps]) -> None:
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent._process_entity_output(run_context)
        assert result.narrative_summary == ""
        assert result.key_attributes == []
        assert result.relationships == []
        assert result.role_in_story is None
        assert result.character_arc is None

    @pytest.mark.asyncio
    async def test_without_character_arc(self, run_context: RunContext[WikiGenerationDeps]) -> None:
        """Non-character entities omit character_arc."""
        agent = WikiGenerationAgent(model=TestModel())
        result = await agent._process_entity_output(
            run_context,
            narrative_summary="A dark forest.",
            key_attributes=["ancient", "magical"],
        )
        assert result.character_arc is None
