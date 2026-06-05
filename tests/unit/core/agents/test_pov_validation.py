"""Tests for POVDetectionAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- scene_index values should be unique
- pov_character should be non-empty for each scene
- issue severity should be "error" or "warning"
- issue type from known set (head_hop/knowledge_leak/emotional_leak/physical_impossibility)

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.pov_agent import POVDeps, POVDetectionAgent
from narrare_core.agents.pov_types import (
    POVDetectedIssue,
    POVDetectedScene,
    POVDetectionOutput,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> POVDetectionAgent:
    return POVDetectionAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[POVDeps]:
    return RunContext[POVDeps](
        deps=POVDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_scene(**overrides: object) -> POVDetectedScene:
    """Build a valid POVDetectedScene for testing."""
    defaults: dict[str, object] = {
        "scene_index": 0,
        "pov_character": "Alice",
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return POVDetectedScene(**defaults)  # type: ignore[arg-type]


def _make_issue(**overrides: object) -> POVDetectedIssue:
    """Build a valid POVDetectedIssue for testing."""
    defaults: dict[str, object] = {
        "type": "head_hop",
        "location": "Chapter 3, para 4",
        "text": "Bob felt angry.",
        "explanation": "Switch from Alice's POV.",
        "severity": "warning",
    }
    defaults.update(overrides)
    return POVDetectedIssue(**defaults)  # type: ignore[arg-type]


def _valid_output(**overrides: object) -> POVDetectionOutput:
    """Build a valid POVDetectionOutput for testing."""
    defaults: dict[str, object] = {
        "scenes": [_make_scene()],
        "issues": [_make_issue()],
    }
    defaults.update(overrides)
    return POVDetectionOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert len(result.scenes) == 1
        assert result.scenes[0].pov_character == "Alice"

    @pytest.mark.asyncio
    async def test_valid_with_multiple_scenes(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output(
            scenes=[
                _make_scene(scene_index=0, pov_character="Alice"),
                _make_scene(scene_index=1, pov_character="Bob"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.scenes) == 2

    @pytest.mark.asyncio
    async def test_empty_scenes_and_issues_passes(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output(scenes=[], issues=[])
        result = await agent._validate_output(ctx, output)
        assert result.scenes == []
        assert result.issues == []


# ---------------------------------------------------------------------------
# B. Scene invariants
# ---------------------------------------------------------------------------


class TestSceneInvariants:
    """Scene invariants are enforced."""

    @pytest.mark.asyncio
    async def test_duplicate_scene_index_raises(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output(
            scenes=[
                _make_scene(scene_index=0, pov_character="Alice"),
                _make_scene(scene_index=0, pov_character="Bob"),
            ]
        )
        with pytest.raises(ModelRetry, match="Duplicate scene_index"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_empty_pov_character_raises(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output(scenes=[_make_scene(pov_character="")])
        with pytest.raises(ModelRetry, match="empty pov_character"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_pov_character_raises(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output(scenes=[_make_scene(pov_character="   ")])
        with pytest.raises(ModelRetry, match="empty pov_character"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Issue invariants
# ---------------------------------------------------------------------------


class TestIssueInvariants:
    """Issue type and severity must be from known sets."""

    @pytest.mark.asyncio
    async def test_invalid_issue_type_raises(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output(issues=[_make_issue(type="invalid_type")])
        with pytest.raises(ModelRetry, match="not valid"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_invalid_severity_raises(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output(issues=[_make_issue(severity="critical")])
        with pytest.raises(ModelRetry, match="not valid"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_valid_issue_types_pass(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        for itype in ("head_hop", "knowledge_leak", "emotional_leak", "physical_impossibility"):
            output = _valid_output(issues=[_make_issue(type=itype)])
            result = await agent._validate_output(ctx, output)
            assert result.issues[0].type == itype

    @pytest.mark.asyncio
    async def test_valid_severities_pass(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        for sev in ("error", "warning"):
            output = _valid_output(issues=[_make_issue(severity=sev)])
            result = await agent._validate_output(ctx, output)
            assert result.issues[0].severity == sev


# ---------------------------------------------------------------------------
# D. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert len(result1.scenes) == len(result2.scenes)

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: POVDetectionAgent, ctx: RunContext[POVDeps]
    ) -> None:
        output = _valid_output(scenes=[_make_scene(scene_index=0), _make_scene(scene_index=0)])
        for _ in range(3):
            with pytest.raises(ModelRetry, match="Duplicate scene_index"):
                await agent._validate_output(ctx, output)
