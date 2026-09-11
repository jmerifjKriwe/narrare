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

    def test_custom_values(self) -> None:
        deps = POVDeps(
            text="Alice felt a chill...",
            language="de",
        )
        assert deps.text == "Alice felt a chill..."
        assert deps.language == "de"


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
        )
        result = await agent.run("Analysiere die Erzählperspektive.", deps=deps)
        assert isinstance(result, POVDetectionOutput)
