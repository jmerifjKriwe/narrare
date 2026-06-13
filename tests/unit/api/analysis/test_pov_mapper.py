"""Unit tests for POV output mapping (pov_mapper.py).

Covers map_issue_type, map_output_to_result, and build_deps —
the static translation layer between agent output and API types.
"""

from __future__ import annotations

from typing import Any

import pytest

from narrare.analysis.services.pov_mapper import (
    build_deps,
    map_issue_type,
    map_output_to_result,
)
from narrare_core.analysis.types import (
    POVIssue,
    POVIssueType,
    POVResult,
    POVScene,
)

# ---------------------------------------------------------------------------
# A. map_issue_type
# ---------------------------------------------------------------------------


class TestMapIssueType:
    """Issue type string to POVIssueType enum mapping."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("head_hop", POVIssueType.HEAD_HOP),
            ("knowledge_leak", POVIssueType.KNOWLEDGE_LEAK),
            ("emotional_leak", POVIssueType.EMOTIONAL_LEAK),
            ("physical_impossibility", POVIssueType.PHYSICAL_IMPOSSIBILITY),
        ],
    )
    def test_known_types_map_correctly(self, raw: str, expected: POVIssueType) -> None:
        assert map_issue_type(raw) == expected

    def test_unknown_type_falls_back_to_head_hop(self) -> None:
        assert map_issue_type("totally_bogus") == POVIssueType.HEAD_HOP

    def test_empty_string_falls_back_to_head_hop(self) -> None:
        assert map_issue_type("") == POVIssueType.HEAD_HOP


# ---------------------------------------------------------------------------
# B. map_output_to_result
# ---------------------------------------------------------------------------


def _agent_output(**overrides: Any) -> dict[str, Any]:
    """Build a raw POVDetectionOutput dict for testing."""
    base: dict[str, Any] = {
        "scenes": [
            {"scene_index": 0, "pov_character": "Alice", "confidence": 0.9},
            {"scene_index": 1, "pov_character": "Bob", "confidence": 0.8},
        ],
        "issues": [
            {
                "type": "head_hop",
                "location": "Ch 1, Para 3",
                "text": "Bob suddenly knew what Alice was thinking.",
                "explanation": "POV switches mid-scene.",
                "suggestion": "Add a scene break.",
                "severity": "error",
            },
        ],
        "pov_distribution": {"Alice": 0.6, "Bob": 0.4},
        "switch_count": 3,
        "analysis_type": "third_limited",
        "overall_assessment": "Mostly consistent with some head-hopping.",
    }
    base.update(overrides)
    return base


class TestMapOutputToResult:
    """POVDetectionOutput to POVResult mapping."""

    def test_returns_pov_result(self) -> None:
        result = map_output_to_result(_agent_output())
        assert isinstance(result, POVResult)

    def test_scenes_mapped_correctly(self) -> None:
        result = map_output_to_result(_agent_output())
        assert len(result.scenes) == 2
        assert isinstance(result.scenes[0], POVScene)
        assert result.scenes[0].scene_index == 0
        assert result.scenes[0].pov_character == "Alice"
        assert result.scenes[0].confidence == pytest.approx(0.9)

    def test_issues_mapped_correctly(self) -> None:
        result = map_output_to_result(_agent_output())
        assert len(result.issues) == 1
        issue = result.issues[0]
        assert isinstance(issue, POVIssue)
        assert issue.type == POVIssueType.HEAD_HOP
        assert issue.severity == "error"
        assert "scene break" in issue.suggestion

    def test_distribution_and_counts_passed_through(self) -> None:
        result = map_output_to_result(_agent_output())
        assert result.pov_distribution == {"Alice": 0.6, "Bob": 0.4}
        assert result.switch_count == 3
        assert result.analysis_type == "third_limited"

    def test_empty_output_produces_empty_result(self) -> None:
        result = map_output_to_result(
            {
                "scenes": [],
                "issues": [],
                "pov_distribution": {},
                "switch_count": 0,
                "analysis_type": "",
            }
        )
        assert result.scenes == []
        assert result.issues == []
        assert result.switch_count == 0

    def test_scene_with_empty_pov_character_becomes_none(self) -> None:
        result = map_output_to_result(
            {
                "scenes": [
                    {"scene_index": 0, "pov_character": "", "confidence": 0.5},
                ],
                "issues": [],
                "pov_distribution": {},
                "switch_count": 0,
                "analysis_type": "omniscient",
            }
        )
        assert result.scenes[0].pov_character is None

    def test_issue_type_uses_map_issue_type(self) -> None:
        result = map_output_to_result(
            {
                "scenes": [],
                "issues": [
                    {
                        "type": "knowledge_leak",
                        "location": "",
                        "text": "",
                        "explanation": "",
                        "suggestion": "",
                        "severity": "warning",
                    },
                ],
                "pov_distribution": {},
                "switch_count": 0,
                "analysis_type": "",
            }
        )
        assert result.issues[0].type == POVIssueType.KNOWLEDGE_LEAK


# ---------------------------------------------------------------------------
# C. build_deps
# ---------------------------------------------------------------------------


class TestBuildDeps:
    """POVDeps construction."""

    def test_creates_deps_with_all_fields(self) -> None:
        deps = build_deps(
            text="Alice walked home.",
            language="en",
            known_characters=["Alice", "Bob"],
            pov_type_hint="third_limited",
        )
        assert deps.text == "Alice walked home."
        assert deps.language == "en"
        assert deps.known_characters == ["Alice", "Bob"]
        assert deps.pov_type_hint == "third_limited"

    def test_none_pov_type_hint_accepted(self) -> None:
        deps = build_deps(
            text="Some text.",
            language="de",
            known_characters=[],
            pov_type_hint=None,
        )
        assert deps.pov_type_hint is None
        assert deps.known_characters == []
