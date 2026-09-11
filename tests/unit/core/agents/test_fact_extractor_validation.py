"""Tests for FactExtractorAgent — output validation.

ADR-044 — Staged Multi-Agent Consistency Pipeline.

Test strategy:
- Validation tested directly via _validate_output
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.fact_extractor_agent import FactExtractorAgent
from narrare_core.agents.fact_extractor_types import (
    ExtractedFact,
    FactExtractorDeps,
    FactExtractorOutput,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> FactExtractorAgent:
    return FactExtractorAgent(model=TestModel())


@pytest.fixture()
def run_context() -> RunContext[FactExtractorDeps]:
    return RunContext[FactExtractorDeps](
        deps=FactExtractorDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


# ---------------------------------------------------------------------------
# A. Output Validator — _validate_output
# ---------------------------------------------------------------------------


class TestValidateOutput:
    """_validate_output enforces deterministic invariants (ADR-035)."""

    def _make_output(self, **fact_overrides: object) -> FactExtractorOutput:
        defaults: dict[str, object] = {
            "fact_type": "character_state",
            "subject": "Anna",
            "predicate": "has eye color",
            "object_value": "green",
            "chapter_id": "ch-1",
            "evidence_text": "Anna's green eyes sparkled.",
            "confidence": 0.9,
        }
        defaults.update(fact_overrides)
        fact = ExtractedFact(**defaults)  # type: ignore[arg-type]
        return FactExtractorOutput(facts=[fact])

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        output = self._make_output()
        result = await agent._validate_output(run_context, output)
        assert len(result.facts) == 1

    @pytest.mark.asyncio
    async def test_empty_evidence_text_raises(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        output = self._make_output(evidence_text="")
        with pytest.raises(ModelRetry, match="empty evidence_text"):
            await agent._validate_output(run_context, output)

    @pytest.mark.asyncio
    async def test_whitespace_evidence_text_raises(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        output = self._make_output(evidence_text="   ")
        with pytest.raises(ModelRetry, match="empty evidence_text"):
            await agent._validate_output(run_context, output)

    @pytest.mark.asyncio
    async def test_empty_chapter_id_raises(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        output = self._make_output(chapter_id="")
        with pytest.raises(ModelRetry, match="empty chapter_id"):
            await agent._validate_output(run_context, output)

    @pytest.mark.asyncio
    async def test_empty_subject_filtered(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        output = self._make_output(subject="")
        result = await agent._validate_output(run_context, output)
        assert len(result.facts) == 0

    @pytest.mark.asyncio
    async def test_empty_predicate_filtered(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        output = self._make_output(predicate="")
        result = await agent._validate_output(run_context, output)
        assert len(result.facts) == 0

    @pytest.mark.asyncio
    async def test_empty_object_value_filtered(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        output = self._make_output(object_value="")
        result = await agent._validate_output(run_context, output)
        assert len(result.facts) == 0

    @pytest.mark.asyncio
    async def test_duplicate_fact_raises(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        fact = ExtractedFact(
            fact_type="character_state",
            subject="Anna",
            predicate="has eye color",
            object_value="green",
            chapter_id="ch-1",
            evidence_text="Anna's green eyes.",
            confidence=0.9,
        )
        output = FactExtractorOutput(facts=[fact, fact])
        with pytest.raises(ModelRetry, match="Duplicate fact"):
            await agent._validate_output(run_context, output)

    @pytest.mark.asyncio
    async def test_case_insensitive_duplicate_raises(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        fact1 = ExtractedFact(
            fact_type="character_state",
            subject="Anna",
            predicate="Has Eye Color",
            object_value="green",
            chapter_id="ch-1",
            evidence_text="Anna's eyes.",
            confidence=0.9,
        )
        fact2 = ExtractedFact(
            fact_type="character_state",
            subject="anna",
            predicate="has eye color",
            object_value="Green",
            chapter_id="ch-1",
            evidence_text="Her green eyes.",
            confidence=0.8,
        )
        output = FactExtractorOutput(facts=[fact1, fact2])
        with pytest.raises(ModelRetry, match="Duplicate fact"):
            await agent._validate_output(run_context, output)

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        valid = ExtractedFact(
            fact_type="event",
            subject="Anna",
            predicate="arrived at",
            object_value="the tower",
            chapter_id="ch-2",
            evidence_text="Anna arrived.",
            confidence=0.8,
        )
        invalid = ExtractedFact(
            fact_type="character_state",
            subject="",
            predicate="is",
            object_value="brave",
            chapter_id="ch-1",
            evidence_text="She was brave.",
            confidence=0.9,
        )
        output = FactExtractorOutput(facts=[invalid, valid])
        result = await agent._validate_output(run_context, output)
        assert len(result.facts) == 1
        assert result.facts[0].subject == "Anna"

    @pytest.mark.asyncio
    async def test_empty_facts_list_passes(
        self, agent: FactExtractorAgent, run_context: RunContext[FactExtractorDeps]
    ) -> None:
        output = FactExtractorOutput()
        result = await agent._validate_output(run_context, output)
        assert result.facts == []
