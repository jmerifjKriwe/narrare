"""Tests for relationship endpoint validation in ExtractionAgent._validate_output.

Covers the predicate-contract invariants for relationship items (prompt
v1.4.0): ``name`` carries the predicate, ``source_entity_name`` identifies
the subject, and the target comes from ``target_entity_name`` (legacy
``related_entity_name`` accepted as fallback). Also covers duplicate
detection keyed on endpoints + predicate instead of ``name`` alone —
under the predicate contract, ``name`` alone would falsely collide for
same-type edges between different endpoint pairs.

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


def _relationship_item(**overrides: object) -> ExtractionItem:
    """Build a valid predicate-contract relationship item."""
    item = ExtractionItem(
        item_type="relationship",
        name="engaged_to",
        confidence=0.75,
        source_text="Anna got engaged to Peter.",
        relationship_type="engaged_to",
        source_entity_name="Anna Meyer",
        target_entity_name="Peter Meyer",
    )
    return item.model_copy(update=overrides)


# ---------------------------------------------------------------------------
# A. Valid predicate-contract items pass
# ---------------------------------------------------------------------------


class TestPredicateContractPasses:
    """New-contract relationship items pass the validator."""

    @pytest.mark.asyncio
    async def test_relationship_with_endpoint_names_passes(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(results=[_relationship_item()])
        result = await agent._validate_output(ctx, output)
        assert result.results[0].source_entity_name == "Anna Meyer"
        assert result.results[0].target_entity_name == "Peter Meyer"

    @pytest.mark.asyncio
    async def test_legacy_related_entity_name_accepted_as_target(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        """related_entity_name satisfies the target invariant (legacy output)."""
        output = ExtractionOutput(
            results=[
                _relationship_item(
                    target_entity_name=None,
                    related_entity_name="Peter Meyer",
                ),
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.results) == 1


# ---------------------------------------------------------------------------
# B. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestEndpointInvariants:
    """Missing endpoint names raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_missing_source_entity_name_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[_relationship_item(source_entity_name=None)],
        )
        with pytest.raises(ModelRetry, match="non-empty source_entity_name"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_source_entity_name_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[_relationship_item(source_entity_name="   ")],
        )
        with pytest.raises(ModelRetry, match="non-empty source_entity_name"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_missing_both_target_fields_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _relationship_item(
                    target_entity_name=None,
                    related_entity_name=None,
                ),
            ],
        )
        with pytest.raises(ModelRetry, match="non-empty target_entity_name"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_both_target_fields_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        output = ExtractionOutput(
            results=[
                _relationship_item(
                    target_entity_name="  ",
                    related_entity_name=" ",
                ),
            ],
        )
        with pytest.raises(ModelRetry, match="non-empty target_entity_name"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Duplicate detection keyed on endpoints + predicate
# ---------------------------------------------------------------------------


class TestRelationshipDuplicateDetection:
    """Duplicates for relationships are detected by (predicate, endpoints)."""

    @pytest.mark.asyncio
    async def test_same_predicate_different_endpoints_pass(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        """Two engaged_to edges between different pairs are NOT duplicates."""
        output = ExtractionOutput(
            results=[
                _relationship_item(),
                _relationship_item(
                    source_entity_name="Kael",
                    target_entity_name="Mira",
                ),
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_same_predicate_same_endpoints_raises(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        """The same edge proposed twice is a duplicate despite name collision."""
        output = ExtractionOutput(
            results=[
                _relationship_item(),
                _relationship_item(),
            ],
        )
        with pytest.raises(ModelRetry, match="Duplicate extraction item"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_same_name_new_entity_duplicates_still_raise(
        self, agent: ExtractionAgent, ctx: RunContext[ExtractionDeps]
    ) -> None:
        """Non-relationship dedup (name + item_type) is unchanged."""
        item = ExtractionItem(
            item_type="new_entity",
            entity_type="character",
            name="Elena",
            confidence=0.9,
            source_text="Elena strode through the marble halls.",
        )
        output = ExtractionOutput(results=[item, item.model_copy()])
        with pytest.raises(ModelRetry, match="Duplicate extraction item"):
            await agent._validate_output(ctx, output)
