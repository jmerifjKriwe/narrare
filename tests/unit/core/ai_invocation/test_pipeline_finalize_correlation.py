"""Tests for ADR-045 Phase 3 correlation fields recorded by finalize().

Split from ``test_pipeline_finalize.py`` to respect RULE-04.

Verifies the full pipeline path ``finalize()`` → ``_record_evidence()`` →
``build_invocation_evidence(prompt=...)`` populates the correlation fields
(prompt fingerprint, prepared-context fingerprint, budget fingerprint,
invocation_id, streaming) in the recorded evidence.

See: ADR-045, CONSTRAINTS.md RULE-04/RULE-10.
"""

from __future__ import annotations

import pytest

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.budgets._types import (
    OutputBudget,
    OutputBudgetDecision,
)
from narrare_core.ai_invocation.models import ValidationResult
from narrare_core.ai_invocation.pipeline import (
    InvocationPipeline,
    PreparedInvocation,
)

from .conftest import (
    FakeEvidenceSink,
    make_composed_prompt,
    make_invocation_context,
)


class TestFinalizeCorrelationFields:
    """ADR-045 Phase 3: finalize() threads the prompt so evidence carries
    correlation fields (prompt fingerprint, prepared-context fingerprint,
    budget fingerprint, invocation_id, streaming)."""

    @pytest.mark.asyncio
    async def test_recorded_evidence_has_prompt_fingerprint(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)

        await pipeline.finalize(make_composed_prompt(), make_invocation_context())

        evidence = sink.records[0]
        assert evidence.prompt_fingerprint is not None
        assert len(evidence.prompt_fingerprint) == 64

    @pytest.mark.asyncio
    async def test_recorded_evidence_has_prepared_context_fingerprint(self) -> None:
        sink = FakeEvidenceSink()
        prepared = PreparedInvocation(
            context=make_invocation_context(),
            validation=ValidationResult(status=ValidationStatus.PASS),
        )
        pipeline = InvocationPipeline(evidence_sink=sink)

        await pipeline.finalize(
            make_composed_prompt(), make_invocation_context(), prepared=prepared
        )

        evidence = sink.records[0]
        assert evidence.prepared_context_fingerprint is not None
        assert len(evidence.prepared_context_fingerprint) == 64

    @pytest.mark.asyncio
    async def test_recorded_evidence_has_budget_fingerprint_when_budget_set(self) -> None:
        sink = FakeEvidenceSink()
        prepared = PreparedInvocation(
            context=make_invocation_context(),
            validation=ValidationResult(status=ValidationStatus.PASS),
            budget=OutputBudgetDecision(
                budget=OutputBudget(max_tokens=8192, profile="long_texts"),
                source="intent_profile",
                reason="secret reason",
            ),
        )
        pipeline = InvocationPipeline(evidence_sink=sink)

        await pipeline.finalize(
            make_composed_prompt(), make_invocation_context(), prepared=prepared
        )

        evidence = sink.records[0]
        assert evidence.budget_decision_fingerprint is not None
        assert len(evidence.budget_decision_fingerprint) == 64
        assert "secret reason" not in evidence.model_dump_json()

    @pytest.mark.asyncio
    async def test_recorded_evidence_has_invocation_id_and_streaming(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)
        ctx = make_invocation_context(streaming=True)

        await pipeline.finalize(make_composed_prompt(), ctx)

        evidence = sink.records[0]
        assert evidence.invocation_id is not None
        assert evidence.streaming is True
