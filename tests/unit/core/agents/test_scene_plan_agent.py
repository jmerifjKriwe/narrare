"""Tests for ScenePlanAgent — instantiation, execution, and output guard.

Test strategy:
- TestModel / FunctionModel for deterministic structured-output tests
  (no real LLM — RULE-01b)
- Guard tests call ``_validate_output`` directly with a constructed
  RunContext (``test_summary_validation.py`` pattern)

See PLAN-001 Task 6 (scene planning, ADR-096).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from narrare_core.agents.errors import ModelRetryExhaustedError
from narrare_core.agents.scene_plan_agent import ScenePlanAgent, ScenePlanDeps
from narrare_core.agents.scene_plan_types import (
    SceneDraftOutput,
    ScenePresenceModel,
    SceneProposal,
    SceneRefineOutput,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SCENE_DATA: dict[str, Any] = {
    "title": "The Ambush at the Gate",
    "pov_character_name": "John Smith",
    "location_name": "The Castle",
    "present_characters": [
        {"name": "John Smith", "goal": "wants to warn the guard"},
        {"name": "Mara"},
    ],
    "purpose": "John must reach the gate before dawn.",
    "conflict": "Mara blocks the path; loyalty vs duty.",
    "resolution": "John talks his way past but at a cost.",
    "beats": ["John reaches the gate", "Mara confronts him", "The horn sounds"],
}


def _draft_response(scenes: list[dict[str, Any]]) -> ModelResponse:
    """Build a FunctionModel ModelResponse carrying a SceneDraftOutput tool call."""
    return ModelResponse(
        parts=[ToolCallPart(tool_name="final_result", args=json.dumps({"scenes": scenes}))]
    )


def _refine_response(scene: dict[str, Any]) -> ModelResponse:
    """Build a FunctionModel ModelResponse carrying a SceneRefineOutput tool call."""
    return ModelResponse(
        parts=[ToolCallPart(tool_name="final_result", args=json.dumps({"scene": scene}))]
    )


def _proposal(**overrides: Any) -> SceneProposal:
    """Build a valid SceneProposal for testing."""
    defaults: dict[str, Any] = {
        "title": "The Ambush at the Gate",
        "purpose": "John must reach the gate before dawn.",
    }
    defaults.update(overrides)
    return SceneProposal(**defaults)


# ---------------------------------------------------------------------------
# A. Output types
# ---------------------------------------------------------------------------


class TestScenePlanTypes:
    """Scene-plan output models default and populate correctly."""

    def test_presence_defaults(self) -> None:
        presence = ScenePresenceModel(name="Mara")
        assert presence.name == "Mara"
        assert presence.goal == ""

    def test_proposal_defaults(self) -> None:
        proposal = SceneProposal()
        assert proposal.title == ""
        assert proposal.pov_character_name == ""
        assert proposal.location_name == ""
        assert proposal.present_characters == []
        assert proposal.purpose == ""
        assert proposal.conflict == ""
        assert proposal.resolution == ""
        assert proposal.beats == []

    def test_proposal_with_values(self) -> None:
        proposal = SceneProposal(
            title="The Ambush",
            pov_character_name="John",
            location_name="The Gate",
            present_characters=[ScenePresenceModel(name="Mara", goal="stop him")],
            purpose="Reach the gate.",
            conflict="Mara blocks.",
            resolution="Talked past.",
            beats=["Arrival", "Confrontation"],
        )
        assert proposal.title == "The Ambush"
        assert proposal.present_characters[0].goal == "stop him"
        assert len(proposal.beats) == 2

    def test_draft_output_defaults(self) -> None:
        output = SceneDraftOutput()
        assert output.scenes == []

    def test_refine_output_requires_scene(self) -> None:
        output = SceneRefineOutput(scene=SceneProposal(title="T"))
        assert isinstance(output.scene, SceneProposal)
        assert output.scene.title == "T"


# ---------------------------------------------------------------------------
# B. ScenePlanDeps
# ---------------------------------------------------------------------------


class TestScenePlanDeps:
    """ScenePlanDeps is created and configured correctly."""

    def test_defaults(self) -> None:
        deps = ScenePlanDeps()
        assert deps.language == "en"
        assert deps.genre == ""
        assert deps.project_title == ""

    def test_custom_values(self) -> None:
        deps = ScenePlanDeps(language="de", genre="Fantasy", project_title="The Last Kingdom")
        assert deps.language == "de"
        assert deps.genre == "Fantasy"
        assert deps.project_title == "The Last Kingdom"


# ---------------------------------------------------------------------------
# C. ScenePlanAgent — Instantiation
# ---------------------------------------------------------------------------


class TestScenePlanAgentInstantiation:
    """ScenePlanAgent instantiates for both draft and refine output types."""

    def test_draft_agent_can_be_instantiated(self) -> None:
        agent = ScenePlanAgent(model=TestModel(), output_type=SceneDraftOutput)
        assert isinstance(agent, ScenePlanAgent)

    def test_refine_agent_can_be_instantiated(self) -> None:
        agent = ScenePlanAgent(model=TestModel(), output_type=SceneRefineOutput)
        assert isinstance(agent, ScenePlanAgent)

    def test_agent_with_system_prompt(self) -> None:
        """Agent can receive a system_prompt (from PromptComposer)."""
        agent = ScenePlanAgent(
            model=TestModel(),
            output_type=SceneDraftOutput,
            system_prompt="You are a story structure planner.",
        )
        assert isinstance(agent, ScenePlanAgent)


# ---------------------------------------------------------------------------
# D. ScenePlanAgent — Execution
# ---------------------------------------------------------------------------


class TestScenePlanAgentExecution:
    """ScenePlanAgent runs return the requested structured output."""

    @pytest.mark.asyncio
    async def test_draft_run_returns_output_with_proposals(self) -> None:
        agent = ScenePlanAgent(
            model=FunctionModel(
                lambda messages, info: _draft_response(
                    [_SCENE_DATA, dict(_SCENE_DATA, title="The Horn Sounds")]
                )
            ),
            output_type=SceneDraftOutput,
        )
        result = await agent.run(
            prompt="<chapter_context>Ch 4 summary</chapter_context>", deps=ScenePlanDeps()
        )
        assert isinstance(result, SceneDraftOutput)
        assert len(result.scenes) >= 1
        assert isinstance(result.scenes[0], SceneProposal)
        assert result.scenes[0].title == "The Ambush at the Gate"
        assert result.scenes[1].title == "The Horn Sounds"

    @pytest.mark.asyncio
    async def test_draft_run_proposal_carries_nested_types(self) -> None:
        agent = ScenePlanAgent(
            model=FunctionModel(lambda messages, info: _draft_response([_SCENE_DATA])),
            output_type=SceneDraftOutput,
        )
        result = await agent.run(
            prompt="<chapter_context>Ch 4</chapter_context>", deps=ScenePlanDeps()
        )
        assert isinstance(result, SceneDraftOutput)
        proposal = result.scenes[0]
        assert isinstance(proposal.present_characters[0], ScenePresenceModel)
        assert proposal.present_characters[0].name == "John Smith"
        assert proposal.present_characters[1].goal == ""
        assert proposal.beats == ["John reaches the gate", "Mara confronts him", "The horn sounds"]

    @pytest.mark.asyncio
    async def test_refine_run_returns_single_scene_output(self) -> None:
        agent = ScenePlanAgent(
            model=FunctionModel(lambda messages, info: _refine_response(_SCENE_DATA)),
            output_type=SceneRefineOutput,
        )
        result = await agent.run(prompt="<scene_plan>Scene 1</scene_plan>", deps=ScenePlanDeps())
        assert isinstance(result, SceneRefineOutput)
        assert result.scene.title == "The Ambush at the Gate"
        assert result.scene.purpose == "John must reach the gate before dawn."

    @pytest.mark.asyncio
    async def test_draft_run_with_test_model_output_passes_guard(self) -> None:
        """TestModel-generated output (non-empty proposal) passes the guard wiring."""
        model = TestModel(custom_output_args={"scenes": [{"title": "The Ambush"}]})
        agent = ScenePlanAgent(model=model, output_type=SceneDraftOutput)
        result = await agent.run(
            prompt="<chapter_context>Ch 4</chapter_context>", deps=ScenePlanDeps()
        )
        assert isinstance(result, SceneDraftOutput)
        assert len(result.scenes) == 1
        assert result.scenes[0].title == "The Ambush"


# ---------------------------------------------------------------------------
# E. Output guard — _validate_output (direct calls)
# ---------------------------------------------------------------------------


@pytest.fixture()
def draft_agent() -> ScenePlanAgent:
    return ScenePlanAgent(model=TestModel(), output_type=SceneDraftOutput)


@pytest.fixture()
def refine_agent() -> ScenePlanAgent:
    return ScenePlanAgent(model=TestModel(), output_type=SceneRefineOutput)


@pytest.fixture()
def ctx() -> RunContext[ScenePlanDeps]:
    return RunContext[ScenePlanDeps](
        deps=ScenePlanDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


class TestOutputGuardValid:
    """Valid outputs pass the guard unchanged."""

    @pytest.mark.asyncio
    async def test_valid_draft_passes(
        self, draft_agent: ScenePlanAgent, ctx: RunContext[ScenePlanDeps]
    ) -> None:
        output = SceneDraftOutput(scenes=[_proposal(), _proposal(title="The Horn Sounds")])
        result = await draft_agent._validate_output(ctx, output)
        assert isinstance(result, SceneDraftOutput)
        assert result.scenes == output.scenes

    @pytest.mark.asyncio
    async def test_valid_refine_passes(
        self, refine_agent: ScenePlanAgent, ctx: RunContext[ScenePlanDeps]
    ) -> None:
        output = SceneRefineOutput(scene=_proposal())
        result = await refine_agent._validate_output(ctx, output)
        assert isinstance(result, SceneRefineOutput)
        assert result.scene.title == output.scene.title

    @pytest.mark.asyncio
    async def test_purpose_only_is_sufficient(
        self, draft_agent: ScenePlanAgent, ctx: RunContext[ScenePlanDeps]
    ) -> None:
        """A proposal needs title OR purpose — purpose alone passes."""
        output = SceneDraftOutput(scenes=[_proposal(title="")])
        result = await draft_agent._validate_output(ctx, output)
        assert isinstance(result, SceneDraftOutput)
        assert result.scenes[0].purpose != ""


class TestOutputGuardViolations:
    """Empty title+purpose proposals are rejected with ModelRetry."""

    @pytest.mark.asyncio
    async def test_draft_all_empty_proposals_raises(
        self, draft_agent: ScenePlanAgent, ctx: RunContext[ScenePlanDeps]
    ) -> None:
        output = SceneDraftOutput(scenes=[_proposal(title="", purpose="")])
        with pytest.raises(ModelRetry, match=r"non-empty title or purpose"):
            await draft_agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_draft_one_empty_among_valid_raises(
        self, draft_agent: ScenePlanAgent, ctx: RunContext[ScenePlanDeps]
    ) -> None:
        output = SceneDraftOutput(scenes=[_proposal(), _proposal(title="", purpose="")])
        with pytest.raises(ModelRetry, match=r"non-empty title or purpose"):
            await draft_agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_only_counts_as_empty(
        self, draft_agent: ScenePlanAgent, ctx: RunContext[ScenePlanDeps]
    ) -> None:
        output = SceneDraftOutput(scenes=[_proposal(title="   ", purpose="  ")])
        with pytest.raises(ModelRetry, match="non-empty"):
            await draft_agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_refine_empty_scene_raises(
        self, refine_agent: ScenePlanAgent, ctx: RunContext[ScenePlanDeps]
    ) -> None:
        output = SceneRefineOutput(scene=_proposal(title="", purpose=""))
        with pytest.raises(ModelRetry, match=r"non-empty title or purpose"):
            await refine_agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_draft_empty_scenes_list_passes(
        self, draft_agent: ScenePlanAgent, ctx: RunContext[ScenePlanDeps]
    ) -> None:
        """An empty scenes list has no offending proposal — no rejection here."""
        output = SceneDraftOutput(scenes=[])
        result = await draft_agent._validate_output(ctx, output)
        assert isinstance(result, SceneDraftOutput)
        assert result.scenes == []


# ---------------------------------------------------------------------------
# F. End-to-end retry exhaustion
# ---------------------------------------------------------------------------


class TestGuardRetryExhaustion:
    """A model that keeps returning empty proposals exhausts retries."""

    @pytest.mark.asyncio
    async def test_draft_run_with_empty_proposals_raises_retry_exhausted(self) -> None:
        model = TestModel(custom_output_args={"scenes": [{"title": "", "purpose": ""}]})
        agent = ScenePlanAgent(model=model, output_type=SceneDraftOutput)
        with pytest.raises(ModelRetryExhaustedError):
            await agent.run(prompt="<chapter_context>Ch 4</chapter_context>", deps=ScenePlanDeps())
