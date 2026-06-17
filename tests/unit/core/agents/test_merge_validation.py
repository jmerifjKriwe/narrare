"""Tests for KBMergeAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- decision should be one of "merge", "distinct", "uncertain"
- pair_id must be non-empty for each decision
- When decision is "merge", merge_strategy must be present
- No duplicate pair_ids

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.merge_agent import KBMergeAgent, KBMergeDeps
from narrare_core.agents.merge_types import MergeDecision, MergeOutput, MergeStrategy

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> KBMergeAgent:
    return KBMergeAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[KBMergeDeps]:
    return RunContext[KBMergeDeps](
        deps=KBMergeDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_decision(**overrides: object) -> MergeDecision:
    """Build a valid MergeDecision for testing."""
    defaults: dict[str, object] = {
        "pair_id": "pair-1",
        "decision": "distinct",
        "confidence": 0.9,
        "reasoning": "Names differ too much.",
    }
    defaults.update(overrides)
    return MergeDecision(**defaults)  # type: ignore[arg-type]


def _valid_output(**overrides: object) -> MergeOutput:
    """Build a valid MergeOutput for testing."""
    defaults: dict[str, object] = {
        "merge_decisions": [_make_decision()],
        "overall_notes": "One pair analyzed.",
    }
    defaults.update(overrides)
    return MergeOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_distinct_passes(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert result.merge_decisions[0].decision == "distinct"

    @pytest.mark.asyncio
    async def test_valid_merge_with_strategy_passes(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output(
            merge_decisions=[
                _make_decision(
                    decision="merge",
                    merge_strategy=MergeStrategy(keep_name="Anna"),
                ),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.merge_decisions[0].decision == "merge"
        assert result.merge_decisions[0].merge_strategy is not None

    @pytest.mark.asyncio
    async def test_valid_uncertain_passes(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output(merge_decisions=[_make_decision(decision="uncertain")])
        result = await agent._validate_output(ctx, output)
        assert result.merge_decisions[0].decision == "uncertain"

    @pytest.mark.asyncio
    async def test_empty_decisions_passes(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output(merge_decisions=[])
        result = await agent._validate_output(ctx, output)
        assert result.merge_decisions == []


# ---------------------------------------------------------------------------
# B. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_empty_pair_id_raises(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output(merge_decisions=[_make_decision(pair_id="")])
        with pytest.raises(ModelRetry, match="non-empty pair_id"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_invalid_decision_raises(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output(merge_decisions=[_make_decision(decision="maybe")])
        with pytest.raises(ModelRetry, match="must be one of"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_merge_without_strategy_raises(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output(
            merge_decisions=[_make_decision(decision="merge", merge_strategy=None)]
        )
        with pytest.raises(ModelRetry, match="merge_strategy"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_duplicate_pair_ids_raises(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output(
            merge_decisions=[
                _make_decision(pair_id="pair-1"),
                _make_decision(pair_id="pair-1"),
            ]
        )
        with pytest.raises(ModelRetry, match="Duplicate pair_id"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_different_pair_ids_passes(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output(
            merge_decisions=[
                _make_decision(pair_id="pair-1"),
                _make_decision(pair_id="pair-2"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.merge_decisions) == 2

    @pytest.mark.asyncio
    async def test_distinct_without_strategy_passes(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        """distinct decision doesn't need a strategy."""
        output = _valid_output(
            merge_decisions=[_make_decision(decision="distinct", merge_strategy=None)]
        )
        result = await agent._validate_output(ctx, output)
        assert result.merge_decisions[0].merge_strategy is None


# ---------------------------------------------------------------------------
# D. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert len(result1.merge_decisions) == len(result2.merge_decisions)

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: KBMergeAgent, ctx: RunContext[KBMergeDeps]
    ) -> None:
        output = _valid_output(merge_decisions=[_make_decision(pair_id="")])
        for _ in range(3):
            with pytest.raises(ModelRetry, match="non-empty pair_id"):
                await agent._validate_output(ctx, output)
