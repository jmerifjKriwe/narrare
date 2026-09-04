"""Tests for POVDetectionAgent — instantiation, deps, and run.

Covers:
1. Deps defaults and custom values
2. Agent instantiation
3. Agent run with TestModel (deterministic, no LLM calls — valid
   ``custom_output_args``, since the ADR-035 validator rejects placeholder
   output)
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.pov_agent import POVDeps, POVDetectionAgent
from narrare_core.agents.pov_types import POVDetectionOutput


def _pov_output_args() -> dict[str, Any]:
    """Build valid ``final_result`` tool args for POVDetectionOutput."""
    return {
        "scenes": [
            {
                "scene_index": 0,
                "pov_character": "Alice",
                "confidence": 0.9,
                "text_sample": "Alice walked into the room.",
            },
        ],
        "issues": [],
        "pov_distribution": {"Alice": 1.0},
        "switch_count": 0,
        "analysis_type": "third_limited",
        "overall_assessment": "Consistent third-limited POV.",
    }


# ---------------------------------------------------------------------------
# B. POVDeps
# ---------------------------------------------------------------------------


class TestPOVDeps:
    """POVDeps creates and configures correctly."""

    def test_defaults(self) -> None:
        deps = POVDeps()
        assert deps.text == ""
        assert deps.language == "en"
        assert deps.known_characters == []
        assert deps.pov_type_hint is None

    def test_custom_values(self) -> None:
        deps = POVDeps(
            text="Alice felt a chill...",
            language="de",
            known_characters=["Alice", "Bob", "Charlie"],
            pov_type_hint="third_limited",
        )
        assert deps.text == "Alice felt a chill..."
        assert deps.language == "de"
        assert deps.known_characters == ["Alice", "Bob", "Charlie"]
        assert deps.pov_type_hint == "third_limited"

    def test_known_characters_default_empty_list(self) -> None:
        deps = POVDeps()
        assert deps.known_characters == []
        # Ensure it's not shared between instances
        deps2 = POVDeps()
        deps.known_characters.append("Alice")
        assert deps2.known_characters == []


# ---------------------------------------------------------------------------
# C. POVDetectionAgent — Instantiation
# ---------------------------------------------------------------------------


class TestPOVDetectionAgentInstantiation:
    """POVDetectionAgent instantiates correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = POVDetectionAgent(model=TestModel())
        assert isinstance(agent, POVDetectionAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        agent = POVDetectionAgent(
            model=TestModel(),
            system_prompt="You are a POV analyst.",
        )
        assert isinstance(agent, POVDetectionAgent)


# ---------------------------------------------------------------------------
# E. POVDetectionAgent — Run with TestModel
# ---------------------------------------------------------------------------


class TestPOVDetectionAgentRun:
    """POVDetectionAgent executes with TestModel (deterministic, no LLM)."""

    @pytest.mark.asyncio
    async def test_run_returns_output(self) -> None:
        agent = POVDetectionAgent(model=TestModel(custom_output_args=_pov_output_args()))
        deps = POVDeps(text="Alice felt a chill.", language="en")
        result = await agent.run("Analyze POV.", deps=deps)
        assert isinstance(result, POVDetectionOutput)

    @pytest.mark.asyncio
    async def test_run_with_known_characters(self) -> None:
        agent = POVDetectionAgent(model=TestModel(custom_output_args=_pov_output_args()))
        deps = POVDeps(
            text="Alice watched Bob carefully.",
            language="en",
            known_characters=["Alice", "Bob"],
        )
        result = await agent.run("Analyze POV.", deps=deps)
        assert isinstance(result, POVDetectionOutput)

    @pytest.mark.asyncio
    async def test_run_with_pov_type_hint(self) -> None:
        agent = POVDetectionAgent(model=TestModel(custom_output_args=_pov_output_args()))
        deps = POVDeps(
            text="I walked into the dark room.",
            language="en",
            pov_type_hint="first_person",
        )
        result = await agent.run("Analyze POV.", deps=deps)
        assert isinstance(result, POVDetectionOutput)

    @pytest.mark.asyncio
    async def test_run_with_system_prompt(self) -> None:
        agent = POVDetectionAgent(
            model=TestModel(custom_output_args=_pov_output_args()),
            system_prompt="You are a POV analyst.",
        )
        deps = POVDeps(text="She felt the cold wind on her face.")
        result = await agent.run("Analyze POV.", deps=deps)
        assert isinstance(result, POVDetectionOutput)

    @pytest.mark.asyncio
    async def test_run_with_german_language(self) -> None:
        agent = POVDetectionAgent(model=TestModel(custom_output_args=_pov_output_args()))
        deps = POVDeps(
            text="Alice spürte einen Schauer.",
            language="de",
            known_characters=["Alice"],
            pov_type_hint="third_limited",
        )
        result = await agent.run("Analysiere die Erzählperspektive.", deps=deps)
        assert isinstance(result, POVDetectionOutput)
