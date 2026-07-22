"""Tests for DialogueCoachAgent (ASSIST-004 / ADR-069).

TestModel-based structured-output tests (ADR-035). Verifies the agent
parses the governed template's JSON contract + the output validator
enforces invariants.

Note: because the agent uses ``output_type=[_process_output, Model]``
(tool-mode output), tests use ``custom_output_args`` (tool call arguments)
rather than ``custom_output_text`` (plain text — incompatible with tool mode
in pydantic-ai 2.x).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.dialogue_coach_agent import DialogueCoachAgent
from narrare_core.agents.dialogue_coach_types import DialogueCoachDeps


def _coach_output_args(
    *,
    issues: list[dict[str, Any]] | None = None,
    adaptive_summary: str = "",
) -> dict[str, Any]:
    """Build custom_output_args matching _process_output kwargs."""
    return {
        "issues": issues or [],
        "adaptive_summary": adaptive_summary,
    }


class TestDialogueCoachAgentAnalyzeMode:
    """Agent parses analyze-mode output (no alternatives)."""

    @pytest.mark.asyncio
    async def test_returns_output_with_issues(self) -> None:
        issues = [
            {
                "issue_type": "voice_mismatch",
                "speaker": "Alice",
                "original_quote": '"Good morning."',
                "diagnosis": "Too formal for Alice's terse voice.",
                "severity": "medium",
            }
        ]
        model = TestModel(custom_output_args=_coach_output_args(issues=issues))
        agent = DialogueCoachAgent(model=model)
        deps = DialogueCoachDeps(text_to_analyze='"Good morning."', mode="analyze")
        result = await agent.run(prompt="Analyse this dialogue.", deps=deps)

        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "voice_mismatch"
        assert result.issues[0].alternatives is None  # analyze mode

    @pytest.mark.asyncio
    async def test_returns_empty_issues_when_passage_clean(self) -> None:
        model = TestModel(custom_output_args=_coach_output_args())
        agent = DialogueCoachAgent(model=model)
        deps = DialogueCoachDeps(text_to_analyze='"Hi."', mode="analyze")
        result = await agent.run(prompt="x", deps=deps)
        assert result.issues == []


class TestDialogueCoachAgentImproveMode:
    """Agent parses improve-mode output (alternatives present)."""

    @pytest.mark.asyncio
    async def test_returns_output_with_alternatives(self) -> None:
        issues = [
            {
                "issue_type": "voice_mismatch",
                "speaker": "Alice",
                "original_quote": '"Good morning."',
                "diagnosis": "Too formal.",
                "severity": "high",
                "alternatives": [
                    {
                        "rewrite": '"Hey."',
                        "explanation": "Terse — matches Alice's voice.",
                    }
                ],
            }
        ]
        model = TestModel(custom_output_args=_coach_output_args(issues=issues))
        agent = DialogueCoachAgent(model=model)
        deps = DialogueCoachDeps(text_to_analyze='"Good morning."', mode="improve")
        result = await agent.run(prompt="Improve this dialogue.", deps=deps)

        assert len(result.issues) == 1
        issue = result.issues[0]
        assert issue.alternatives is not None  # type narrowing for pyright
        assert len(issue.alternatives) == 1
        assert issue.alternatives[0].rewrite == '"Hey."'


class TestDialogueCoachAgentValidator:
    """Output validator enforces ADR-035 invariants."""

    @pytest.mark.asyncio
    async def test_drops_issues_with_empty_original_quote(self) -> None:
        """Quality Rule: no issue without a verbatim quote."""
        issues = [
            {
                "issue_type": "redundancy",
                "speaker": "",
                "original_quote": "valid quote",
                "diagnosis": "x",
                "severity": "low",
            },
            {
                "issue_type": "redundancy",
                "speaker": "",
                "original_quote": "",  # empty — should be dropped
                "diagnosis": "y",
                "severity": "low",
            },
        ]
        model = TestModel(custom_output_args=_coach_output_args(issues=issues))
        agent = DialogueCoachAgent(model=model)
        deps = DialogueCoachDeps(text_to_analyze="x", mode="analyze")
        result = await agent.run(prompt="x", deps=deps)
        assert len(result.issues) == 1
        assert result.issues[0].original_quote == "valid quote"
