"""Tests for DialogueCoachAgent (ASSIST-004 / ADR-069).

TestModel-based structured-output tests (ADR-035). Verifies the agent
parses the governed template's JSON contract + the output validator
enforces invariants.

Note: the agent's structured output is a tool call (``final_result``), so
tests supply ``custom_output_args`` (tool call arguments) rather than
``custom_output_text`` (plain text — incompatible with tool-mode output
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
    """Build ``custom_output_args`` matching DialogueCoachOutput (final_result tool)."""
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
    """Quality Rule: no issue without a verbatim quote (ADR-035)."""

    @pytest.mark.asyncio
    async def test_whitespace_only_quotes_filtered_by_run(self) -> None:
        """Issues whose quote is whitespace-only are dropped by run()'s guard.

        The strict output model enforces min_length=1 on ``original_quote``
        (fully empty quotes are rejected at the tool boundary); the
        run()-level defensive filter catches whitespace-only quotes that
        pass the Field constraint but are semantically empty.
        """
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
                "original_quote": "   ",  # whitespace-only — should be dropped
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
