"""Tests for agents/kb_improve_agent.py — Instantiation and Output Function.

Test-Strategie:
- TestModel for deterministic agent tests
- Output Function tested directly via _process_output
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.kb_improve_agent import KBImproveAgent
from narrare_core.agents.kb_improve_types import (
    ImprovementSuggestion,
    KBImproveDeps,
    SuggestionType,
)

# ---------------------------------------------------------------------------
# A. KBImproveAgent — Instantiation
# ---------------------------------------------------------------------------


class TestKBImproveAgentInstantiation:
    """KBImproveAgent can be instantiated with and without KBAgent."""

    def test_instantiation_without_kb_agent(self) -> None:
        agent = KBImproveAgent(model=TestModel())
        assert isinstance(agent, KBImproveAgent)
        assert agent._agent is not None

    def test_instantiation_with_system_prompt(self) -> None:
        agent = KBImproveAgent(
            model=TestModel(),
            system_prompt="You are a KB improvement analyzer.",
        )
        assert isinstance(agent, KBImproveAgent)


# ---------------------------------------------------------------------------
# B. Output Function — _process_output
# ---------------------------------------------------------------------------


class TestProcessOutput:
    """_process_output output function structures LLM response."""

    @pytest.fixture()
    def run_context(self) -> RunContext[KBImproveDeps]:
        return RunContext[KBImproveDeps](
            deps=KBImproveDeps(),
            model=TestModel(),
            usage=RunUsage(),
        )

    @pytest.mark.asyncio
    async def test_process_output_with_suggestions(
        self,
        run_context: RunContext[KBImproveDeps],
    ) -> None:
        result = await KBImproveAgent(model=TestModel())._process_output(
            run_context,
            suggestions=[
                {
                    "type": "expand",
                    "target": "backstory",
                    "description": "Backstory is too sparse.",
                    "confidence": 0.8,
                },
                {
                    "type": "connect",
                    "target": "location_id",
                    "description": "No home location set.",
                    "related_entity_id": "loc-1",
                    "related_entity_name": "Castle",
                    "confidence": 0.6,
                },
            ],
            overall_assessment="Entry needs expansion.",
            completeness_score=0.4,
        )
        assert len(result.suggestions) == 2
        assert isinstance(result.suggestions[0], ImprovementSuggestion)
        assert result.suggestions[0].type == SuggestionType.EXPAND
        assert result.suggestions[1].type == SuggestionType.CONNECT
        assert result.overall_assessment == "Entry needs expansion."
        assert result.completeness_score == 0.4

    @pytest.mark.asyncio
    async def test_process_output_partial_streaming(
        self,
        run_context: RunContext[KBImproveDeps],
    ) -> None:
        run_context.partial_output = True
        result = await KBImproveAgent(model=TestModel())._process_output(
            run_context,
            suggestions=[{"type": "expand", "target": "test", "description": "test"}],
        )
        assert result.suggestions == []
        assert result.overall_assessment == ""
        assert result.completeness_score == 0.0

    @pytest.mark.asyncio
    async def test_process_output_empty(
        self,
        run_context: RunContext[KBImproveDeps],
    ) -> None:
        result = await KBImproveAgent(model=TestModel())._process_output(
            run_context,
        )
        assert result.suggestions == []
        assert result.overall_assessment == ""
        assert result.completeness_score == 0.0

    @pytest.mark.asyncio
    async def test_process_output_score_clamped_high(
        self,
        run_context: RunContext[KBImproveDeps],
    ) -> None:
        result = await KBImproveAgent(model=TestModel())._process_output(
            run_context,
            completeness_score=1.5,
        )
        assert result.completeness_score == 1.0

    @pytest.mark.asyncio
    async def test_process_output_score_clamped_negative(
        self,
        run_context: RunContext[KBImproveDeps],
    ) -> None:
        result = await KBImproveAgent(model=TestModel())._process_output(
            run_context,
            completeness_score=-0.3,
        )
        assert result.completeness_score == 0.0

    @pytest.mark.asyncio
    async def test_process_output_context_used(
        self,
        run_context: RunContext[KBImproveDeps],
    ) -> None:
        result = await KBImproveAgent(model=TestModel())._process_output(
            run_context,
            context_used=["Alice", "Castle"],
        )
        assert result.context_used == ["Alice", "Castle"]

    @pytest.mark.asyncio
    async def test_process_output_suggestion_defaults(
        self,
        run_context: RunContext[KBImproveDeps],
    ) -> None:
        """Suggestion with minimal fields gets sensible defaults."""
        result = await KBImproveAgent(model=TestModel())._process_output(
            run_context,
            suggestions=[{}],
        )
        assert len(result.suggestions) == 1
        assert result.suggestions[0].type == SuggestionType.EXPAND  # default
        assert result.suggestions[0].target == ""
        assert result.suggestions[0].confidence == 0.5
