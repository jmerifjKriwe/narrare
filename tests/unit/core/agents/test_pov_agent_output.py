"""Tests for POVDetectionAgent output types.

Covers:
1. Output type structure (POVDetectedScene, POVDetectedIssue, POVDetectionOutput)
"""

from __future__ import annotations

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
