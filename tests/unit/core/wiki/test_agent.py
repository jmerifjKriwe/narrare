"""Tests for WikiGenerationAgent — instantiation and entity generation.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Keine echten LLM-Calls (RULE-01b)
- Prompt loading tests in ``test_prompt_loader.py``
- Chapter tests in ``test_agent_chapter.py``
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from narrare_core.wiki.agent import WikiGenerationAgent
from narrare_core.wiki.types import (
    WikiChapterOutput,
    WikiEntityOutput,
    WikiGenerationDeps,
)


def _entity_output() -> WikiEntityOutput:
    """Minimal valid entity output (real value object, ADR-030)."""
    return WikiEntityOutput(narrative_summary="Summary.", key_attributes=[], relationships=[])


def _chapter_output() -> WikiChapterOutput:
    """Minimal valid chapter output (real value object, ADR-030)."""
    return WikiChapterOutput(
        narrative_summary="Summary.", key_events=[], entities_involved=[], themes=[]
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


# ---------------------------------------------------------------------------
# C. generate_entity — model_settings/usage_limits pass-through (Task 1)
# ---------------------------------------------------------------------------


class _StreamResultStub:
    """Stub for the pydantic-ai run_stream result object."""

    def __init__(self, output: object) -> None:
        self._output = output

    async def get_output(self) -> object:
        return self._output


class _StreamContextStub:
    """Async context manager yielded by a stubbed run_stream call."""

    def __init__(self, result: _StreamResultStub) -> None:
        self._result = result

    async def __aenter__(self) -> _StreamResultStub:
        return self._result

    async def __aexit__(self, *args: object) -> None:
        return None


class _RunStreamStub:
    """Callable fake recording run_stream calls (ADR-030 fake style)."""

    def __init__(self, output: object) -> None:
        self._context = _StreamContextStub(_StreamResultStub(output))
        self.calls: list[dict[str, object]] = []

    def __call__(self, *args: object, **kwargs: object) -> _StreamContextStub:
        self.calls.append({"args": args, "kwargs": kwargs})
        return self._context


class TestGenerateEntitySettings:
    """generate_entity forwards the prepared-triple half to the inner run."""

    @pytest.mark.asyncio
    async def test_run_forwards_settings_and_limits(self, deps: WikiGenerationDeps) -> None:
        agent = WikiGenerationAgent(model=TestModel())
        expected = _entity_output()
        stub_agent = AsyncMock(name="inner_agent")
        stub_agent.run = AsyncMock(return_value=SimpleNamespace(output=expected))
        cast("Any", agent)._agent = stub_agent
        sentinel_settings = ModelSettings(max_tokens=12_345)
        sentinel_limits = UsageLimits(request_limit=7)

        result = await agent.generate_entity(
            deps=deps,
            model_settings=sentinel_settings,
            usage_limits=sentinel_limits,
        )

        assert result is expected
        kwargs = stub_agent.run.call_args.kwargs
        assert kwargs["model_settings"] is sentinel_settings
        assert kwargs["usage_limits"] is sentinel_limits

    @pytest.mark.asyncio
    async def test_stream_forwards_settings_and_limits(self, deps: WikiGenerationDeps) -> None:
        agent = WikiGenerationAgent(model=TestModel())
        expected = _entity_output()
        run_stream_stub = _RunStreamStub(expected)
        stub_agent = AsyncMock(name="inner_agent")
        stub_agent.run_stream = run_stream_stub
        cast("Any", agent)._agent = stub_agent
        sentinel_settings = ModelSettings(max_tokens=12_345)
        sentinel_limits = UsageLimits(request_limit=7)

        result = await agent.generate_entity(
            deps=deps,
            stream=True,
            model_settings=sentinel_settings,
            usage_limits=sentinel_limits,
        )

        assert result is expected
        assert len(run_stream_stub.calls) == 1
        kwargs = cast("dict[str, object]", run_stream_stub.calls[0]["kwargs"])
        assert kwargs["model_settings"] is sentinel_settings
        assert kwargs["usage_limits"] is sentinel_limits

    @pytest.mark.asyncio
    async def test_run_defaults_to_none(self, deps: WikiGenerationDeps) -> None:
        """Without kwargs the inner run receives None (backward compat)."""
        agent = WikiGenerationAgent(model=TestModel())
        stub_agent = AsyncMock(name="inner_agent")
        stub_agent.run = AsyncMock(return_value=SimpleNamespace(output=_entity_output()))
        cast("Any", agent)._agent = stub_agent

        await agent.generate_entity(deps=deps)

        kwargs = stub_agent.run.call_args.kwargs
        assert kwargs["model_settings"] is None
        assert kwargs["usage_limits"] is None


# ---------------------------------------------------------------------------
# D. generate_chapter — delegation kwargs pass-through (Task 1)
# ---------------------------------------------------------------------------


class TestGenerateChapterSettings:
    """generate_chapter forwards the kwargs to WikiChapterGenerator.generate."""

    @pytest.mark.asyncio
    async def test_forwards_settings_and_limits(self, deps: WikiGenerationDeps) -> None:
        expected = _chapter_output()
        sentinel_settings = ModelSettings(max_tokens=12_345)
        sentinel_limits = UsageLimits(request_limit=7)

        with patch("narrare_core.wiki.agent.WikiChapterGenerator") as MockGenerator:
            agent = WikiGenerationAgent(model=TestModel())
            MockGenerator.return_value.generate = AsyncMock(return_value=expected)

            result = await agent.generate_chapter(
                deps=deps,
                model_settings=sentinel_settings,
                usage_limits=sentinel_limits,
            )

        assert result is expected
        kwargs = MockGenerator.return_value.generate.call_args.kwargs
        assert kwargs["model_settings"] is sentinel_settings
        assert kwargs["usage_limits"] is sentinel_limits
