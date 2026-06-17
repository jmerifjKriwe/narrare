"""Tests for WorldbuildingAgent output validators — ADR-035.

Tests the deterministic invariants enforced by _validate_phase1 and _validate_phase2:

Phase 1:
- gap_type should be non-empty, description non-empty
- Filter gaps with empty descriptions

Phase 2:
- category and severity from known sets
- entity_ids non-empty

Test strategy:
- Call validators directly with mocked RunContext
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.worldbuilding_types import (
    Phase1GapOutput,
    Phase2ConsistencyOutput,
    WorldbuildingDeps,
    WorldbuildingPhase1Output,
    WorldbuildingPhase2Output,
)
from narrare_core.agents.worldbuilding_validators import (
    validate_worldbuilding_phase1,
    validate_worldbuilding_phase2,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx() -> RunContext[WorldbuildingDeps]:
    return RunContext[WorldbuildingDeps](
        deps=WorldbuildingDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_gap(**overrides: object) -> Phase1GapOutput:
    """Build a valid Phase1GapOutput for testing."""
    defaults: dict[str, object] = {
        "gap_type": "missing_field",
        "description": "The character lacks a backstory.",
    }
    defaults.update(overrides)
    return Phase1GapOutput(**cast("Any", defaults))


def _valid_phase1(**overrides: object) -> WorldbuildingPhase1Output:
    """Build a valid Phase 1 output for testing."""
    defaults: dict[str, object] = {
        "gaps": [_make_gap()],
        "connection_suggestions": [],
        "assessment": "Some gaps found.",
        "worldbuilding_score": 0.5,
        "candidate_pairs_for_consistency": [],
    }
    defaults.update(overrides)
    return WorldbuildingPhase1Output(**cast("Any", defaults))


def _make_phase2_issue(**overrides: object) -> Phase2ConsistencyOutput:
    """Build a valid Phase2ConsistencyOutput for testing."""
    defaults: dict[str, object] = {
        "category": "geography",
        "entity_ids": ["ent-1", "ent-2"],
        "entity_names": ["Castle", "Tower"],
        "description": "Distance contradicts earlier chapter.",
        "contradiction": "Castle is 5 miles in Ch1 but 50 miles in Ch3.",
        "severity": "major",
        "confidence": 0.8,
    }
    defaults.update(overrides)
    return Phase2ConsistencyOutput(**cast("Any", defaults))


def _valid_phase2(**overrides: object) -> WorldbuildingPhase2Output:
    """Build a valid Phase 2 output for testing."""
    defaults: dict[str, object] = {
        "issues": [_make_phase2_issue()],
        "assessment": "One consistency issue found.",
    }
    defaults.update(overrides)
    return WorldbuildingPhase2Output(**cast("Any", defaults))


# ===========================================================================
# Phase 1 Tests
# ===========================================================================


class TestPhase1ValidOutputPasses:
    """Valid Phase 1 output passes the validator."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase1()
        result = await validate_worldbuilding_phase1(ctx, output)
        assert len(result.gaps) == 1

    @pytest.mark.asyncio
    async def test_empty_gaps_passes(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase1(gaps=[])
        result = await validate_worldbuilding_phase1(ctx, output)
        assert result.gaps == []


class TestPhase1FilterGaps:
    """Gaps with empty descriptions are filtered."""

    @pytest.mark.asyncio
    async def test_filter_empty_description(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase1(
            gaps=[
                _make_gap(description=""),
                _make_gap(description="Valid description"),
            ],
        )
        result = await validate_worldbuilding_phase1(ctx, output)
        assert len(result.gaps) == 1
        assert result.gaps[0].description == "Valid description"

    @pytest.mark.asyncio
    async def test_all_gaps_filtered(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase1(
            gaps=[_make_gap(description=""), _make_gap(description="   ")],
        )
        result = await validate_worldbuilding_phase1(ctx, output)
        assert result.gaps == []


class TestPhase1InvariantViolations:
    """Invariant violations raise ModelRetry."""

    @pytest.mark.asyncio
    async def test_empty_gap_type_raises(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase1(
            gaps=[_make_gap(gap_type="")],
        )
        with pytest.raises(ModelRetry, match="non-empty gap_type"):
            await validate_worldbuilding_phase1(ctx, output)


# ===========================================================================
# Phase 2 Tests
# ===========================================================================


class TestPhase2ValidOutputPasses:
    """Valid Phase 2 output passes the validator."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase2()
        result = await validate_worldbuilding_phase2(ctx, output)
        assert len(result.issues) == 1

    @pytest.mark.asyncio
    async def test_empty_issues_passes(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase2(issues=[])
        result = await validate_worldbuilding_phase2(ctx, output)
        assert result.issues == []


class TestPhase2InvariantViolations:
    """Invariant violations raise ModelRetry."""

    @pytest.mark.asyncio
    async def test_empty_entity_ids_raises(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase2(
            issues=[_make_phase2_issue(entity_ids=[])],
        )
        with pytest.raises(ModelRetry, match="at least one entity_id"):
            await validate_worldbuilding_phase2(ctx, output)

    @pytest.mark.asyncio
    async def test_invalid_category_raises(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase2(
            issues=[_make_phase2_issue(category="invalid")],
        )
        with pytest.raises(ModelRetry, match="not valid"):
            await validate_worldbuilding_phase2(ctx, output)

    @pytest.mark.asyncio
    async def test_invalid_severity_raises(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase2(
            issues=[_make_phase2_issue(severity="catastrophic")],
        )
        with pytest.raises(ModelRetry, match="not valid"):
            await validate_worldbuilding_phase2(ctx, output)

    @pytest.mark.asyncio
    async def test_valid_categories_pass(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        for cat in ("geography", "politics", "economics", "system_rules", "timeline", "character"):
            output = _valid_phase2(
                issues=[_make_phase2_issue(category=cat)],
            )
            result = await validate_worldbuilding_phase2(ctx, output)
            assert result.issues[0].category == cat

    @pytest.mark.asyncio
    async def test_valid_severities_pass(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        for sev in ("critical", "major", "minor"):
            output = _valid_phase2(
                issues=[_make_phase2_issue(severity=sev)],
            )
            result = await validate_worldbuilding_phase2(ctx, output)
            assert result.issues[0].severity == sev


# ===========================================================================
# Determinism
# ===========================================================================


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_phase1(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase1()
        result1 = await validate_worldbuilding_phase1(ctx, output)
        result2 = await validate_worldbuilding_phase1(ctx, output)
        assert len(result1.gaps) == len(result2.gaps)

    @pytest.mark.asyncio
    async def test_deterministic_phase2(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase2()
        result1 = await validate_worldbuilding_phase2(ctx, output)
        result2 = await validate_worldbuilding_phase2(ctx, output)
        assert len(result1.issues) == len(result2.issues)

    @pytest.mark.asyncio
    async def test_deterministic_phase2_retry(self, ctx: RunContext[WorldbuildingDeps]) -> None:
        output = _valid_phase2(
            issues=[_make_phase2_issue(entity_ids=[])],
        )
        for _ in range(3):
            with pytest.raises(ModelRetry, match="at least one entity_id"):
                await validate_worldbuilding_phase2(ctx, output)
