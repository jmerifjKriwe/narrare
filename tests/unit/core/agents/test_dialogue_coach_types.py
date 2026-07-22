"""Tests for DialogueCoachAgent types (ADR-069 §6.2.1, ADR-055/057 boundary).

Verifies the Pydantic models parse the governed template's JSON contract,
default fields behave correctly, and voice_metrics are structurally absent.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.dialogue_coach_types import (
    DialogueAlternative,
    DialogueCoachDeps,
    DialogueCoachOutput,
    DialogueIssue,
    DialogueIssueType,
    DialogueSeverity,
)


class TestEnums:
    """Issue type + severity enums match the governed template contract."""

    def test_issue_type_values(self) -> None:
        assert "voice_mismatch" in DialogueIssueType.__args__  # type: ignore[attr-defined]
        assert "subtext_absent" in DialogueIssueType.__args__  # type: ignore[attr-defined]
        assert "exposition_overload" in DialogueIssueType.__args__  # type: ignore[attr-defined]
        assert "tag_overuse" in DialogueIssueType.__args__  # type: ignore[attr-defined]
        assert "redundancy" in DialogueIssueType.__args__  # type: ignore[attr-defined]
        assert "unnatural_cadence" in DialogueIssueType.__args__  # type: ignore[attr-defined]
        assert "inconsistency" in DialogueIssueType.__args__  # type: ignore[attr-defined]

    def test_severity_values(self) -> None:
        assert "low" in DialogueSeverity.__args__  # type: ignore[attr-defined]
        assert "medium" in DialogueSeverity.__args__  # type: ignore[attr-defined]
        assert "high" in DialogueSeverity.__args__  # type: ignore[attr-defined]


class TestDialogueAlternative:
    def test_minimal(self) -> None:
        alt = DialogueAlternative(rewrite="Hello.", explanation="shorter")
        assert alt.rewrite == "Hello."
        assert alt.explanation == "shorter"

    def test_rejects_empty_rewrite(self) -> None:
        with pytest.raises(ValidationError):
            DialogueAlternative(rewrite="", explanation="x")


class TestDialogueIssue:
    def test_analyze_mode_issue(self) -> None:
        issue = DialogueIssue(
            issue_type="voice_mismatch",
            speaker="Alice",
            original_quote='"Good morning," she said.',
            diagnosis="Doesn't match Alice's terse voice.",
            severity="medium",
        )
        assert issue.alternatives is None  # analyze mode

    def test_improve_mode_issue_with_alternatives(self) -> None:
        issue = DialogueIssue(
            issue_type="voice_mismatch",
            speaker="Alice",
            original_quote='"Good morning," she said.',
            diagnosis="Too formal.",
            severity="high",
            alternatives=[
                DialogueAlternative(rewrite='"Hey."', explanation="matches terse voice"),
            ],
        )
        assert issue.alternatives is not None  # type narrowing for pyright
        assert len(issue.alternatives) == 1
        assert issue.alternatives[0].rewrite == '"Hey."'

    def test_rejects_empty_original_quote(self) -> None:
        with pytest.raises(ValidationError):
            DialogueIssue(
                issue_type="voice_mismatch",
                speaker="Alice",
                original_quote="",
                diagnosis="x",
                severity="low",
            )

    def test_rejects_invalid_issue_type(self) -> None:
        with pytest.raises(ValidationError):
            DialogueIssue(
                issue_type="bad_type",  # type: ignore[arg-type]
                speaker="Alice",
                original_quote='"Hi."',
                diagnosis="x",
                severity="low",
            )


class TestDialogueCoachOutput:
    def test_empty_issues_list(self) -> None:
        out = DialogueCoachOutput()
        assert out.issues == []
        assert out.adaptive_summary == ""

    def test_with_issues(self) -> None:
        out = DialogueCoachOutput(
            issues=[
                DialogueIssue(
                    issue_type="redundancy",
                    speaker="Bob",
                    original_quote='"Yes, yes, I agree."',
                    diagnosis="Triplicate repetition.",
                    severity="low",
                ),
            ],
            adaptive_summary="Voice profiles were active for 2 characters.",
        )
        assert len(out.issues) == 1
        assert out.adaptive_summary != ""


class TestDialogueCoachDeps:
    """ADR-055/057 boundary — no voice_metrics field."""

    def test_construction(self) -> None:
        deps = DialogueCoachDeps(
            text_to_analyze='"Hello," she said.',
            mode="improve",
            characters=["Alice", "Bob"],
            project_title="Test Novel",
            genre="Fantasy",
            writing_language="en",
        )
        assert deps.mode == "improve"
        assert deps.characters == ["Alice", "Bob"]

    def test_no_voice_metrics_field(self) -> None:
        """The Deps class MUST NOT carry voice_metrics (ADR-055/057)."""
        # Plain class — inspect __annotations__ + __dict__.
        deps = DialogueCoachDeps(text_to_analyze="x", mode="analyze")
        annotations = set(dir(deps))
        assert "voice_metrics" not in annotations
        assert "metrics" not in annotations

    def test_defaults(self) -> None:
        deps = DialogueCoachDeps(text_to_analyze="x", mode="analyze")
        assert deps.characters == []
        assert deps.project_title == ""
        assert deps.writing_language == "en"
