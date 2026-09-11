"""Tests for generate_chapter path (WikiGenerationAgent → WikiChapterGenerator).

Test-Strategie:
- TestModel für deterministische Agent-Tests
- generate_chapter auf WikiGenerationAgent testet die Integration
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from narrare_core.wiki.agent import WikiGenerationAgent
from narrare_core.wiki.agent_chapter import WikiChapterGenerator
from narrare_core.wiki.types import WikiChapterOutput, WikiGenerationDeps


def _chapter_output() -> WikiChapterOutput:
    """Minimal valid chapter output (real value object, ADR-030)."""
    return WikiChapterOutput(
        narrative_summary="Summary.", key_events=[], entities_involved=[], themes=[]
    )


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


# ---------------------------------------------------------------------------
# B. WikiChapterGenerator — model_settings/usage_limits pass-through (Task 1)
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


class TestChapterGeneratorSettings:
    """WikiChapterGenerator.generate forwards kwargs to the internal agent."""

    @pytest.mark.asyncio
    async def test_run_forwards_settings_and_limits(self, deps_chapter: WikiGenerationDeps) -> None:
        generator = WikiChapterGenerator(model=TestModel())
        expected = _chapter_output()
        stub_agent = AsyncMock(name="inner_agent")
        stub_agent.run = AsyncMock(return_value=SimpleNamespace(output=expected))
        cast("Any", generator)._chapter_agent = stub_agent
        sentinel_settings = ModelSettings(max_tokens=12_345)
        sentinel_limits = UsageLimits(request_limit=7)

        result = await generator.generate(
            "Prompt text.",
            deps_chapter,
            model_settings=sentinel_settings,
            usage_limits=sentinel_limits,
        )

        assert result is expected
        kwargs = stub_agent.run.call_args
        assert kwargs is not None
        assert kwargs.kwargs["model_settings"] is sentinel_settings
        assert kwargs.kwargs["usage_limits"] is sentinel_limits

    @pytest.mark.asyncio
    async def test_stream_forwards_settings_and_limits(
        self, deps_chapter: WikiGenerationDeps
    ) -> None:
        generator = WikiChapterGenerator(model=TestModel())
        expected = _chapter_output()
        run_stream_stub = _RunStreamStub(expected)
        stub_agent = AsyncMock(name="inner_agent")
        stub_agent.run_stream = run_stream_stub
        cast("Any", generator)._chapter_agent = stub_agent
        sentinel_settings = ModelSettings(max_tokens=12_345)
        sentinel_limits = UsageLimits(request_limit=7)

        result = await generator.generate(
            "Prompt text.",
            deps_chapter,
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
    async def test_run_defaults_to_none(self, deps_chapter: WikiGenerationDeps) -> None:
        """Without kwargs the internal run receives None (backward compat)."""
        generator = WikiChapterGenerator(model=TestModel())
        stub_agent = AsyncMock(name="inner_agent")
        stub_agent.run = AsyncMock(return_value=SimpleNamespace(output=_chapter_output()))
        cast("Any", generator)._chapter_agent = stub_agent

        await generator.generate("Prompt text.", deps_chapter)

        run_call = stub_agent.run.call_args
        assert run_call is not None
        assert run_call.kwargs["model_settings"] is None
        assert run_call.kwargs["usage_limits"] is None
