"""Tests for worldbuilding_agent output functions — Phase 1 & Phase 2.

Test-Strategie:
- Output Functions tested directly via _process_phase1 / _process_phase2
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.worldbuilding_agent import WorldbuildingAgent
from narrare_core.agents.worldbuilding_types import (
    Phase1ConnectionOutput,
    Phase1GapOutput,
    Phase2ConsistencyOutput,
    WorldbuildingDeps,
)

# ---------------------------------------------------------------------------
# Output Function — _process_phase1
# ---------------------------------------------------------------------------


class TestProcessPhase1:
    """_process_phase1 output function structures LLM response."""

    @pytest.fixture()
    def run_context(self) -> RunContext[WorldbuildingDeps]:
        return RunContext[WorldbuildingDeps](
            deps=WorldbuildingDeps(),
            model=TestModel(),
            usage=RunUsage(),
        )

    @pytest.mark.asyncio
    async def test_process_phase1_with_gaps_and_connections(
        self,
        run_context: RunContext[WorldbuildingDeps],
    ) -> None:
        result = await WorldbuildingAgent(model=TestModel())._process_phase1(
            run_context,
            gaps=[
                {
                    "gap_type": "missing_connection",
                    "description": "No connection between kingdom and magic system",
                    "entity_id": "ent-1",
                },
            ],
            connection_suggestions=[
                {
                    "source_entity_id": "ent-1",
                    "source_entity_name": "Kingdom",
                    "target_entity_id": "ent-2",
                    "target_entity_name": "Magic Academy",
                    "suggested_rel_type": "governs",
                    "reasoning": "The kingdom funds the academy.",
                    "confidence": 0.85,
                },
            ],
            assessment="World has potential but needs connections.",
            worldbuilding_score=0.6,
            candidate_pairs=[["ent-1", "ent-2"]],
        )
        assert len(result.gaps) == 1
        assert isinstance(result.gaps[0], Phase1GapOutput)
        assert result.gaps[0].gap_type == "missing_connection"
        assert len(result.connection_suggestions) == 1
        assert isinstance(result.connection_suggestions[0], Phase1ConnectionOutput)
        assert result.connection_suggestions[0].confidence == 0.85
        assert result.assessment == "World has potential but needs connections."
        assert result.worldbuilding_score == 0.6
        assert len(result.candidate_pairs_for_consistency) == 1

    @pytest.mark.asyncio
    async def test_process_phase1_partial_streaming(
        self,
        run_context: RunContext[WorldbuildingDeps],
    ) -> None:
        run_context.partial_output = True
        result = await WorldbuildingAgent(model=TestModel())._process_phase1(
            run_context,
            gaps=[{"gap_type": "test", "description": "test"}],
        )
        assert result.gaps == []
        assert result.connection_suggestions == []
        assert result.assessment == ""
        assert result.worldbuilding_score == 0.0
        assert result.candidate_pairs_for_consistency == []

    @pytest.mark.asyncio
    async def test_process_phase1_empty_input(
        self,
        run_context: RunContext[WorldbuildingDeps],
    ) -> None:
        result = await WorldbuildingAgent(model=TestModel())._process_phase1(
            run_context,
        )
        assert result.gaps == []
        assert result.connection_suggestions == []
        assert result.assessment == ""
        assert result.worldbuilding_score == 0.0

    @pytest.mark.asyncio
    async def test_process_phase1_score_clamped_to_range(
        self,
        run_context: RunContext[WorldbuildingDeps],
    ) -> None:
        result = await WorldbuildingAgent(model=TestModel())._process_phase1(
            run_context,
            worldbuilding_score=1.5,
        )
        assert result.worldbuilding_score == 1.0

    @pytest.mark.asyncio
    async def test_process_phase1_score_clamped_negative(
        self,
        run_context: RunContext[WorldbuildingDeps],
    ) -> None:
        result = await WorldbuildingAgent(model=TestModel())._process_phase1(
            run_context,
            worldbuilding_score=-0.5,
        )
        assert result.worldbuilding_score == 0.0

    @pytest.mark.asyncio
    async def test_process_phase1_candidate_pairs_filters_invalid(
        self,
        run_context: RunContext[WorldbuildingDeps],
    ) -> None:
        """Candidate pairs with != 2 elements are filtered out."""
        result = await WorldbuildingAgent(model=TestModel())._process_phase1(
            run_context,
            candidate_pairs=[["a", "b"], ["c"]],  # "c" is invalid
        )
        assert len(result.candidate_pairs_for_consistency) == 1
        assert result.candidate_pairs_for_consistency[0] == ("a", "b")


# ---------------------------------------------------------------------------
# Output Function — _process_phase2
# ---------------------------------------------------------------------------


class TestProcessPhase2:
    """_process_phase2 output function structures consistency results."""

    @pytest.fixture()
    def run_context(self) -> RunContext[WorldbuildingDeps]:
        return RunContext[WorldbuildingDeps](
            deps=WorldbuildingDeps(),
            model=TestModel(),
            usage=RunUsage(),
        )

    @pytest.mark.asyncio
    async def test_process_phase2_with_issues(
        self,
        run_context: RunContext[WorldbuildingDeps],
    ) -> None:
        result = await WorldbuildingAgent(model=TestModel())._process_phase2(
            run_context,
            issues=[
                {
                    "category": "geography",
                    "entity_ids": ["ent-1", "ent-2"],
                    "entity_names": ["Castle", "Village"],
                    "description": "Distance contradiction",
                    "contradiction": "Castle is both 1 day and 3 weeks away.",
                    "severity": "major",
                    "confidence": 0.9,
                },
            ],
            assessment="Geography has inconsistencies.",
        )
        assert len(result.issues) == 1
        assert isinstance(result.issues[0], Phase2ConsistencyOutput)
        assert result.issues[0].category == "geography"
        assert result.assessment == "Geography has inconsistencies."

    @pytest.mark.asyncio
    async def test_process_phase2_partial_streaming(
        self,
        run_context: RunContext[WorldbuildingDeps],
    ) -> None:
        run_context.partial_output = True
        result = await WorldbuildingAgent(model=TestModel())._process_phase2(
            run_context,
            issues=[
                {
                    "category": "test",
                    "entity_ids": [],
                    "entity_names": [],
                    "description": "",
                    "contradiction": "",
                    "confidence": 0.5,
                }
            ],
        )
        assert result.issues == []
        assert result.assessment == ""

    @pytest.mark.asyncio
    async def test_process_phase2_empty(
        self,
        run_context: RunContext[WorldbuildingDeps],
    ) -> None:
        result = await WorldbuildingAgent(model=TestModel())._process_phase2(
            run_context,
        )
        assert result.issues == []
        assert result.assessment == ""
