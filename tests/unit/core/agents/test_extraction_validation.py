"""Tests for ExtractionAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- entity_type required for new_entity / update_entity
- source_text non-empty for all items
- relationship items need relationship_type AND related_entity_name
- conflict items need conflict_description
- No duplicate items (same name + item_type)
- Filter out items with empty names

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.extraction_agent import ExtractionAgent, ExtractionDeps
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> ExtractionAgent:
    return ExtractionAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[ExtractionDeps]:
    return RunContext[ExtractionDeps](
        deps=ExtractionDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_item(**overrides: object) -> ExtractionItem:
    """Build a valid ExtractionItem for testing."""
    defaults: dict[str, object] = {
        "item_type": "new_entity",
        "entity_type": "character",
        "name": "Elena",
        "confidence": 0.9,
        "source_text": "Elena strode through the marble halls.",
    }
    defaults.update(overrides)
    return ExtractionItem(**defaults)  # type: ignore[arg-type]


def _valid_output(**item_overrides: object) -> ExtractionOutput:
    """Build a valid ExtractionOutput for testing."""
    return ExtractionOutput(results=[_make_item(**item_overrides)])


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_new_entity_passes(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert len(result.results) == 1
        assert result.results[0].name == "Elena"

    @pytest.mark.asyncio
    async def test_valid_update_entity_passes(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(item_type="update_entity", target_entity_id="ent-1"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.results[0].item_type == "update_entity"

    @pytest.mark.asyncio
    async def test_valid_relationship_passes(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(
                    item_type="relationship",
                    entity_type=None,
                    relationship_type="ally",
                    related_entity_name="Marcus",
                ),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.results[0].relationship_type == "ally"

    @pytest.mark.asyncio
    async def test_valid_conflict_passes(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(
                    item_type="conflict",
                    entity_type=None,
                    conflict_description="Elena is described with different eye colors.",
                ),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.results[0].conflict_description is not None

    @pytest.mark.asyncio
    async def test_empty_results_passes(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(results=[])
        result = await agent._validate_output(ctx, output)
        assert result.results == []


# ---------------------------------------------------------------------------
# B. Filter empty-name items
# ---------------------------------------------------------------------------


class TestFilterEmptyNames:
    """Items with empty names are silently filtered out."""

    @pytest.mark.asyncio
    async def test_empty_name_filtered(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(name=""),
                _make_item(name="Elena"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.results) == 1
        assert result.results[0].name == "Elena"

    @pytest.mark.asyncio
    async def test_whitespace_only_name_filtered(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(name="   "),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.results == []


# ---------------------------------------------------------------------------
# C. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_empty_source_text_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(source_text=""),
            ]
        )
        with pytest.raises(ModelRetry, match="empty source_text"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_only_source_text_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(source_text="   "),
            ]
        )
        with pytest.raises(ModelRetry, match="empty source_text"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_new_entity_missing_entity_type_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(entity_type=""),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty entity_type"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_update_entity_missing_entity_type_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(item_type="update_entity", entity_type=None),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty entity_type"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_new_entity_whitespace_entity_type_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(entity_type="   "),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty entity_type"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_relationship_missing_relationship_type_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(
                    item_type="relationship",
                    entity_type=None,
                    relationship_type="",
                    related_entity_name="Marcus",
                ),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty relationship_type"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_relationship_missing_related_entity_name_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(
                    item_type="relationship",
                    entity_type=None,
                    relationship_type="ally",
                    related_entity_name="",
                ),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty related_entity_name"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_conflict_missing_conflict_description_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(
                    item_type="conflict",
                    entity_type=None,
                    conflict_description="",
                ),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty conflict_description"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_duplicate_items_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(name="Elena"),
                _make_item(name="Elena"),
            ]
        )
        with pytest.raises(ModelRetry, match="Duplicate extraction item"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_duplicate_different_item_types_passes(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        """Same name but different item_types are NOT duplicates."""
        output = ExtractionOutput(
            results=[
                _make_item(name="Elena", item_type="new_entity"),
                _make_item(
                    name="Elena",
                    item_type="relationship",
                    entity_type=None,
                    relationship_type="ally",
                    related_entity_name="Marcus",
                ),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.results) == 2


# ---------------------------------------------------------------------------
# D. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_mixed_valid_and_empty_name_items(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(name=""),
                _make_item(name="Elena"),
                _make_item(name="   "),
                _make_item(name="Marcus"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.results) == 2
        assert result.results[0].name == "Elena"
        assert result.results[1].name == "Marcus"

    @pytest.mark.asyncio
    async def test_conflict_whitespace_description_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(
                    item_type="conflict",
                    entity_type=None,
                    conflict_description="   ",
                ),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty conflict_description"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# E. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert len(result1.results) == len(result2.results)
        assert result1.results[0].name == result2.results[0].name

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _make_item(source_text=""),
            ]
        )
        for _ in range(3):
            with pytest.raises(ModelRetry, match="empty source_text"):
                await agent._validate_output(ctx, output)
