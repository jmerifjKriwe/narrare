"""Tests for ReadabilityAgent — deps and instantiation.

Covers:
1. Deps defaults and custom values
2. Agent instantiation
"""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from narrare_core.agents.readability_agent import ReadabilityAgent, ReadabilityDeps

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
