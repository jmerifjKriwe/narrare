"""Tests for ConsistencyAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- Each issue must have a non-empty description
- conflicting_facts must have >= 2 entries
- ERROR-severity issues must have a suggestion
- Filter out issues with empty descriptions

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.consistency_agent import ConsistencyAgent
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> ConsistencyAgent:
    return ConsistencyAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[ConsistencyDeps]:
    return RunContext[ConsistencyDeps](
        deps=ConsistencyDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_issue(**overrides: object) -> ConsistencyIssue:
    """Build a valid ConsistencyIssue for testing."""
    defaults: dict[str, object] = {
        "check_type": ConsistencyCheckType.CHARACTER,
        "severity": ConsistencySeverity.ERROR,
        "description": "Anna is described as blue-eyed in Ch.3 but green-eyed in Ch.1.",
        "locations": ["Chapter 1", "Chapter 3"],
        "conflicting_facts": ["Anna has green eyes (Ch.1)", "Anna has blue eyes (Ch.3)"],
        "suggestion": "Set Anna's eye color consistently to green.",
        "confidence": 0.92,
    }
    defaults.update(overrides)
    return ConsistencyIssue(**defaults)  # type: ignore[arg-type]


def _valid_output(**issue_overrides: object) -> ConsistencyOutput:
    """Build a valid ConsistencyOutput for testing."""
    return ConsistencyOutput(
        issues=[_make_issue(**issue_overrides)],
        overall_assessment="One critical contradiction found.",
        checked_types=[ConsistencyCheckType.CHARACTER],
    )


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_error_issue_with_suggestion(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert len(result.issues) == 1
        assert result.issues[0].severity == ConsistencySeverity.ERROR

    @pytest.mark.asyncio
    async def test_valid_warning_issue_without_suggestion(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        """WARNING-level issues don't need a suggestion."""
        output = ConsistencyOutput(
            issues=[
                _make_issue(
                    severity=ConsistencySeverity.WARNING,
                    suggestion=None,
                )
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert result.issues[0].suggestion is None

    @pytest.mark.asyncio
    async def test_valid_info_issue(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(
                    severity=ConsistencySeverity.INFO,
                    suggestion=None,
                )
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert result.issues[0].severity == ConsistencySeverity.INFO

    @pytest.mark.asyncio
    async def test_empty_issues_list_passes(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput()
        result = await agent._validate_output(ctx, output)
        assert result.issues == []


# ---------------------------------------------------------------------------
# B. Filter empty-description issues
# ---------------------------------------------------------------------------


class TestFilterEmptyDescriptions:
    """Issues with empty descriptions are silently filtered out."""

    @pytest.mark.asyncio
    async def test_empty_description_filtered(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        valid = _make_issue()
        invalid = _make_issue(description="")
        output = ConsistencyOutput(issues=[invalid, valid])
        result = await agent._validate_output(ctx, output)
        assert len(result.issues) == 1
        assert "Anna" in result.issues[0].description

    @pytest.mark.asyncio
    async def test_whitespace_description_filtered(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(description="   "),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.issues == []

    @pytest.mark.asyncio
    async def test_all_empty_descriptions_filtered_to_empty(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(description=""),
                _make_issue(description="  "),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.issues == []


# ---------------------------------------------------------------------------
# C. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_conflicting_facts_less_than_two_raises(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(conflicting_facts=["Only one fact"]),
            ]
        )
        with pytest.raises(ModelRetry, match="at least 2 conflicting_facts"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_conflicting_facts_empty_raises(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(conflicting_facts=[]),
            ]
        )
        with pytest.raises(ModelRetry, match="at least 2 conflicting_facts"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_error_severity_without_suggestion_raises(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(suggestion=None),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty suggestion"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_error_severity_whitespace_suggestion_raises(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(suggestion="   "),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty suggestion"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_error_severity_empty_suggestion_raises(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(suggestion=""),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty suggestion"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_exactly_two_conflicting_facts_passes(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        """Boundary: exactly 2 conflicting facts is valid."""
        output = ConsistencyOutput(
            issues=[
                _make_issue(conflicting_facts=["Fact A", "Fact B"]),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.issues[0].conflicting_facts) == 2


# ---------------------------------------------------------------------------
# D. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_warning_without_suggestion_passes(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        """Only ERROR-severity requires a suggestion; WARNING is fine without."""
        output = ConsistencyOutput(
            issues=[
                _make_issue(
                    severity=ConsistencySeverity.WARNING,
                    suggestion=None,
                ),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.issues) == 1

    @pytest.mark.asyncio
    async def test_info_without_suggestion_passes(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(
                    severity=ConsistencySeverity.INFO,
                    suggestion=None,
                ),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.issues) == 1

    @pytest.mark.asyncio
    async def test_mixed_valid_and_empty_description_issues(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(description=""),
                _make_issue(description="Valid issue", conflicting_facts=["A", "B"]),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.issues) == 1
        assert result.issues[0].description == "Valid issue"

    @pytest.mark.asyncio
    async def test_multiple_issues_all_valid(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(
                    severity=ConsistencySeverity.ERROR,
                    description="Issue 1",
                    conflicting_facts=["A", "B"],
                    suggestion="Fix it",
                ),
                _make_issue(
                    severity=ConsistencySeverity.WARNING,
                    description="Issue 2",
                    conflicting_facts=["C", "D"],
                    suggestion=None,
                ),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.issues) == 2


# ---------------------------------------------------------------------------
# E. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert len(result1.issues) == len(result2.issues)
        assert result1.issues[0].description == result2.issues[0].description

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: ConsistencyAgent, ctx: RunContext[ConsistencyDeps]
    ) -> None:
        output = ConsistencyOutput(
            issues=[
                _make_issue(conflicting_facts=["only one"]),
            ]
        )
        for _ in range(3):
            with pytest.raises(ModelRetry, match="at least 2 conflicting_facts"):
                await agent._validate_output(ctx, output)
