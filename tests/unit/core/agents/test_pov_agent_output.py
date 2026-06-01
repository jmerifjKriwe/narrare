"""Tests for POVDetectionAgent output types and _process_output.

Covers:
1. Output type structure (POVDetectedScene, POVDetectedIssue, POVDetectionOutput)
2. Output function (_process_output) with values, streaming, and empty input
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.pov_agent import POVDeps, POVDetectionAgent
from narrare_core.agents.pov_types import (
    POVDetectedIssue,
    POVDetectedScene,
    POVDetectionOutput,
)

# ---------------------------------------------------------------------------
# A. Output Types
# ---------------------------------------------------------------------------


class TestPOVDetectedScene:
    """POVDetectedScene validates correctly."""

    def test_defaults(self) -> None:
        scene = POVDetectedScene()
        assert scene.scene_index == 0
        assert scene.pov_character == ""
        assert scene.confidence == 0.0
        assert scene.text_sample == ""

    def test_with_values(self) -> None:
        scene = POVDetectedScene(
            scene_index=2,
            pov_character="Alice",
            confidence=0.92,
            text_sample="Alice felt a chill run down her spine as the door creaked open.",
        )
        assert scene.scene_index == 2
        assert scene.pov_character == "Alice"
        assert scene.confidence == 0.92
        assert "Alice felt" in scene.text_sample

    def test_serialization(self) -> None:
        scene = POVDetectedScene(
            scene_index=0,
            pov_character="Bob",
            confidence=0.75,
        )
        data = scene.model_dump()
        assert data["scene_index"] == 0
        assert data["pov_character"] == "Bob"
        assert data["confidence"] == 0.75
        assert data["text_sample"] == ""


class TestPOVDetectedIssue:
    """POVDetectedIssue validates correctly."""

    def test_defaults(self) -> None:
        issue = POVDetectedIssue()
        assert issue.type == ""
        assert issue.location == ""
        assert issue.text == ""
        assert issue.explanation == ""
        assert issue.suggestion == ""
        assert issue.severity == "warning"

    def test_with_values(self) -> None:
        issue = POVDetectedIssue(
            type="head_hop",
            location="Paragraph 3",
            text="Bob knew she was lying.",
            explanation="Alice is the POV character, but Bob's internal knowledge is revealed.",
            suggestion=(
                "Rewrite from Alice's observation: 'Bob's expression shifted - did he know?'"
            ),
            severity="error",
        )
        assert issue.type == "head_hop"
        assert issue.severity == "error"
        assert "Alice" in issue.explanation

    def test_serialization(self) -> None:
        issue = POVDetectedIssue(
            type="knowledge_leak",
            text="She thought about the hidden letter.",
            explanation="POV character cannot know about the letter.",
            severity="warning",
        )
        data = issue.model_dump()
        assert data["type"] == "knowledge_leak"
        assert data["severity"] == "warning"


class TestPOVDetectionOutput:
    """POVDetectionOutput validates correctly."""

    def test_defaults(self) -> None:
        output = POVDetectionOutput()
        assert output.scenes == []
        assert output.issues == []
        assert output.pov_distribution == {}
        assert output.switch_count == 0
        assert output.analysis_type == ""
        assert output.overall_assessment == ""

    def test_with_values(self) -> None:
        scenes = [
            POVDetectedScene(
                scene_index=0,
                pov_character="Alice",
                confidence=0.9,
                text_sample="Alice walked into the room.",
            ),
        ]
        issues = [
            POVDetectedIssue(
                type="head_hop",
                location="Paragraph 2",
                text="Bob felt angry.",
                explanation="Switch to Bob's perspective mid-scene.",
                suggestion="Rewrite as Alice's observation of Bob's anger.",
                severity="error",
            ),
        ]
        output = POVDetectionOutput(
            scenes=scenes,
            issues=issues,
            pov_distribution={"Alice": 0.8, "Bob": 0.2},
            switch_count=1,
            analysis_type="third_limited",
            overall_assessment="Mostly consistent third-limited POV with one head-hop violation.",
        )
        assert len(output.scenes) == 1
        assert len(output.issues) == 1
        assert output.pov_distribution["Alice"] == 0.8
        assert output.switch_count == 1
        assert output.analysis_type == "third_limited"

    def test_serialization(self) -> None:
        output = POVDetectionOutput(
            analysis_type="first_person",
            overall_assessment="Consistent first-person narration.",
        )
        data = output.model_dump()
        assert data["analysis_type"] == "first_person"
        assert data["scenes"] == []
        assert data["issues"] == []


# ---------------------------------------------------------------------------
# D. Output Function — _process_output
# ---------------------------------------------------------------------------


class TestProcessOutput:
    """Output Function structures the LLM response correctly."""

    @pytest.fixture()
    def run_context(self) -> RunContext[POVDeps]:
        return RunContext[POVDeps](
            deps=POVDeps(),
            model=TestModel(),
            usage=RunUsage(),
        )

    @pytest.mark.asyncio
    async def test_process_output_with_values(
        self,
        run_context: RunContext[POVDeps],
    ) -> None:
        scenes = [
            {
                "scene_index": 0,
                "pov_character": "Alice",
                "confidence": 0.9,
                "text_sample": "Alice walked into the room.",
            },
        ]
        issues = [
            {
                "type": "head_hop",
                "location": "Paragraph 2",
                "text": "Bob felt angry.",
                "explanation": "Switch to Bob's perspective.",
                "suggestion": "Rewrite as observation.",
                "severity": "error",
            },
        ]
        result = await POVDetectionAgent(model=TestModel())._process_output(
            run_context,
            scenes=scenes,
            issues=issues,
            pov_distribution={"Alice": 0.85, "Bob": 0.15},
            switch_count=1,
            analysis_type="third_limited",
            overall_assessment="Mostly consistent with one head-hop.",
        )
        assert len(result.scenes) == 1
        assert result.scenes[0].pov_character == "Alice"
        assert len(result.issues) == 1
        assert result.issues[0].type == "head_hop"
        assert result.pov_distribution["Alice"] == 0.85
        assert result.switch_count == 1
        assert result.analysis_type == "third_limited"
        assert "head-hop" in result.overall_assessment

    @pytest.mark.asyncio
    async def test_process_output_partial_streaming(
        self,
        run_context: RunContext[POVDeps],
    ) -> None:
        run_context.partial_output = True
        result = await POVDetectionAgent(model=TestModel())._process_output(
            run_context,
            scenes=[{"scene_index": 0}],
            issues=[{"type": "head_hop"}],
            overall_assessment="Partial.",
        )
        # Streaming returns empty output
        assert result.scenes == []
        assert result.issues == []
        assert result.overall_assessment == ""

    @pytest.mark.asyncio
    async def test_process_output_empty(
        self,
        run_context: RunContext[POVDeps],
    ) -> None:
        result = await POVDetectionAgent(model=TestModel())._process_output(
            run_context,
        )
        assert result.scenes == []
        assert result.issues == []
        assert result.pov_distribution == {}
        assert result.switch_count == 0
        assert result.analysis_type == ""
        assert result.overall_assessment == ""

    @pytest.mark.asyncio
    async def test_process_output_returns_correct_type(
        self,
        run_context: RunContext[POVDeps],
    ) -> None:
        result = await POVDetectionAgent(model=TestModel())._process_output(
            run_context,
            analysis_type="omniscient",
        )
        assert isinstance(result, POVDetectionOutput)
        assert result.analysis_type == "omniscient"

    @pytest.mark.asyncio
    async def test_process_output_handles_none_values(
        self,
        run_context: RunContext[POVDeps],
    ) -> None:
        result = await POVDetectionAgent(model=TestModel())._process_output(
            run_context,
            scenes=None,
            issues=None,
            pov_distribution=None,
            switch_count=None,
            analysis_type=None,
            overall_assessment=None,
        )
        assert result.scenes == []
        assert result.issues == []
        assert result.pov_distribution == {}
        assert result.switch_count == 0
        assert result.analysis_type == ""
        assert result.overall_assessment == ""
