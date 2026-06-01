"""Tests for ReadabilityAgent — instantiation, deps, and run.

Covers:
1. Deps defaults and custom values
2. Agent instantiation
3. Agent run with TestModel (deterministic, no LLM calls)
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.readability_agent import ReadabilityAgent, ReadabilityDeps
from narrare_core.agents.readability_types import ReadabilityAgentOutput

# ---------------------------------------------------------------------------
# B. ReadabilityDeps
# ---------------------------------------------------------------------------


class TestReadabilityDeps:
    """ReadabilityDeps creates and configures correctly."""

    def test_defaults(self) -> None:
        deps = ReadabilityDeps()
        assert deps.text == ""
        assert deps.language == "en"

    def test_custom_values(self) -> None:
        deps = ReadabilityDeps(text="Some passage.", language="de")
        assert deps.text == "Some passage."
        assert deps.language == "de"


# ---------------------------------------------------------------------------
# C. ReadabilityAgent — Instantiation
# ---------------------------------------------------------------------------


class TestReadabilityAgentInstantiation:
    """ReadabilityAgent instantiates correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = ReadabilityAgent(model=TestModel())
        assert isinstance(agent, ReadabilityAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        agent = ReadabilityAgent(
            model=TestModel(),
            system_prompt="You are a readability analyst.",
        )
        assert isinstance(agent, ReadabilityAgent)


# ---------------------------------------------------------------------------
# E. ReadabilityAgent — Run with TestModel
# ---------------------------------------------------------------------------


class TestReadabilityAgentRun:
    """ReadabilityAgent executes with TestModel (deterministic, no LLM)."""

    @pytest.mark.asyncio
    async def test_run_returns_output(self) -> None:
        agent = ReadabilityAgent(model=TestModel())
        deps = ReadabilityDeps(text="Test text.", language="en")
        result = await agent.run("Analyze readability.", deps=deps)
        assert isinstance(result, ReadabilityAgentOutput)

    @pytest.mark.asyncio
    async def test_run_with_custom_deps(self) -> None:
        agent = ReadabilityAgent(model=TestModel())
        deps = ReadabilityDeps(
            text="A very long passage with many sentences and complex words.",
            language="de",
        )
        result = await agent.run("Analysiere Lesbarkeit.", deps=deps)
        assert isinstance(result, ReadabilityAgentOutput)

    @pytest.mark.asyncio
    async def test_run_with_system_prompt(self) -> None:
        agent = ReadabilityAgent(
            model=TestModel(),
            system_prompt="You are a readability analyst.",
        )
        deps = ReadabilityDeps(text="Hello world.")
        result = await agent.run("Analyze.", deps=deps)
        assert isinstance(result, ReadabilityAgentOutput)
