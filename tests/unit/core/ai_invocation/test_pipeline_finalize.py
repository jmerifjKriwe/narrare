"""Tests for InvocationPipeline.finalize() — post-composition phase.

11-20: mandatory finalize test cases plus evidence field edge cases.
See: ADR-038, INFRA-013, CONSTRAINTS.md RULE-04/RULE-10.
"""

from __future__ import annotations

import pytest

from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedRequirement,
    KBSuggestedStatus,
    PreferenceRequirement,
    PreferenceStatus,
    ValidationStatus,
)
from narrare_core.ai_invocation.budgets._types import (
    OutputBudget,
    OutputBudgetDecision,
)
from narrare_core.ai_invocation.models import ValidationResult
from narrare_core.ai_invocation.pipeline import (
    FinalizedInvocation,
    InvocationPipeline,
    PreparedInvocation,
)

from .conftest import (
    FailingEvidenceSink,
    FakeEvidenceSink,
    FakeFinalValidator,
    make_adoption_policy,
    make_composed_prompt,
    make_invocation_context,
)

# 11. Happy path


class TestFinalizeHappyPath:
    """11. Happy path — final validator passes, evidence recorded."""

    @pytest.mark.asyncio
    async def test_final_validation_passes_evidence_recorded(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(
            final_validator=FakeFinalValidator(),
            evidence_sink=sink,
        )

        result = await pipeline.finalize(make_composed_prompt(), make_invocation_context())

        assert isinstance(result, FinalizedInvocation)
        assert result.validation.is_valid
        assert result.evidence_recorded is True
        assert sink.records[0].feature_id == "test/feature"


# 12. No final validator


class TestFinalizeNoFinalValidator:
    """12. No final validator — skips validation, evidence still recorded."""

    @pytest.mark.asyncio
    async def test_evidence_recorded_without_final_validator(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)

        result = await pipeline.finalize(make_composed_prompt(), make_invocation_context())

        assert result.validation.status == ValidationStatus.PASS
        assert result.evidence_recorded is True
        assert len(sink.records) == 1


class TestFinalizeNoEvidenceSink:
    """13. No evidence sink — evidence_recorded is False."""

    @pytest.mark.asyncio
    async def test_evidence_recorded_false_without_sink(self) -> None:
        pipeline = InvocationPipeline()
        result = await pipeline.finalize(make_composed_prompt(), make_invocation_context())
        assert result.evidence_recorded is False


class TestFinalizeValidationFails:
    """14. Final validation fails — evidence still recorded (with BLOCKED state)."""

    @pytest.mark.asyncio
    async def test_evidence_recorded_on_validation_failure(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(
            final_validator=FakeFinalValidator(
                result=ValidationResult(
                    status=ValidationStatus.FAIL,
                    errors=("Missing output-language control",),
                )
            ),
            evidence_sink=sink,
        )

        result = await pipeline.finalize(make_composed_prompt(), make_invocation_context())

        assert not result.validation.is_valid
        assert result.evidence_recorded is True
        assert sink.records[0].audit_state == AuditState.BLOCKED


class TestFinalizeEvidenceSinkRaises:
    """15. Evidence sink raises — logged as warning, evidence_recorded=False, no crash."""

    @pytest.mark.asyncio
    async def test_no_crash_when_sink_raises(self) -> None:
        pipeline = InvocationPipeline(evidence_sink=FailingEvidenceSink())
        result = await pipeline.finalize(make_composed_prompt(), make_invocation_context())
        assert result.evidence_recorded is False


class TestFinalizePreferenceStatus:
    """16. Preference status — PROVIDED/MISSING/NOT_APPLICABLE."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("ctx_overrides", "expected"),
        [
            (
                {
                    "dynamic_inputs": {"user_preferences": "p"},
                    "adoption_policy": make_adoption_policy(
                        preference_requirement=PreferenceRequirement.REQUIRED
                    ),
                },
                PreferenceStatus.PROVIDED,
            ),
            (
                {
                    "adoption_policy": make_adoption_policy(
                        preference_requirement=PreferenceRequirement.REQUIRED
                    )
                },
                PreferenceStatus.MISSING,
            ),
            ({}, PreferenceStatus.NOT_APPLICABLE),
            (
                {
                    "adoption_policy": make_adoption_policy(
                        preference_requirement=PreferenceRequirement.NOT_APPLICABLE
                    )
                },
                PreferenceStatus.NOT_APPLICABLE,
            ),
            (
                {
                    "dynamic_inputs": {"user_preferences": ""},
                    "adoption_policy": make_adoption_policy(
                        preference_requirement=PreferenceRequirement.REQUIRED
                    ),
                },
                PreferenceStatus.MISSING,
            ),
        ],
        ids=["provided", "missing", "no-policy", "na-policy", "empty-string"],
    )
    async def test_preference_status(
        self,
        ctx_overrides: dict[str, object],
        expected: PreferenceStatus,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)
        ctx = make_invocation_context(**ctx_overrides)

        await pipeline.finalize(make_composed_prompt(), ctx)
        assert sink.records[0].preference_status == expected


class TestFinalizeKBSuggestedStatus:
    """17. KB suggested status — PROVIDED/MISSING/NOT_APPLICABLE."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("ctx_overrides", "expected"),
        [
            (
                {
                    "dynamic_inputs": {"kb_suggested": "kb"},
                    "adoption_policy": make_adoption_policy(
                        kb_suggested_requirement=KBSuggestedRequirement.PROVIDED
                    ),
                },
                KBSuggestedStatus.PROVIDED,
            ),
            (
                {
                    "adoption_policy": make_adoption_policy(
                        kb_suggested_requirement=KBSuggestedRequirement.PROVIDED
                    )
                },
                KBSuggestedStatus.MISSING,
            ),
            ({}, KBSuggestedStatus.NOT_APPLICABLE),
            (
                {
                    "adoption_policy": make_adoption_policy(
                        kb_suggested_requirement=KBSuggestedRequirement.NOT_APPLICABLE
                    )
                },
                KBSuggestedStatus.NOT_APPLICABLE,
            ),
        ],
        ids=["provided", "missing", "no-policy", "na-policy"],
    )
    async def test_kb_suggested_status(
        self,
        ctx_overrides: dict[str, object],
        expected: KBSuggestedStatus,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)
        ctx = make_invocation_context(**ctx_overrides)

        await pipeline.finalize(make_composed_prompt(), ctx)
        assert sink.records[0].kb_suggested_status == expected


class TestFinalizeAuditState:
    """18. Audit state — BLOCKED/RUNTIME_VERIFIED/STATIC_VERIFIED."""

    @pytest.mark.asyncio
    async def test_blocked_when_variable_validation_fails(self) -> None:
        sink = FakeEvidenceSink()
        fail_result = ValidationResult(
            status=ValidationStatus.FAIL,
            errors=("Missing variable",),
        )
        prepared = PreparedInvocation(
            context=make_invocation_context(),
            validation=fail_result,
        )
        pipeline = InvocationPipeline(evidence_sink=sink)

        await pipeline.finalize(
            make_composed_prompt(), make_invocation_context(), prepared=prepared
        )
        assert sink.records[0].audit_state == AuditState.BLOCKED

    @pytest.mark.asyncio
    async def test_blocked_when_final_validation_fails(self) -> None:
        sink = FakeEvidenceSink()
        validator = FakeFinalValidator(
            result=ValidationResult(
                status=ValidationStatus.FAIL,
                errors=("Missing output-language",),
            )
        )
        pipeline = InvocationPipeline(final_validator=validator, evidence_sink=sink)

        await pipeline.finalize(make_composed_prompt(), make_invocation_context())
        assert sink.records[0].audit_state == AuditState.BLOCKED

    @pytest.mark.asyncio
    async def test_runtime_verified_when_both_pass(self) -> None:
        sink = FakeEvidenceSink()
        prepared = PreparedInvocation(
            context=make_invocation_context(),
            validation=ValidationResult(status=ValidationStatus.PASS),
        )
        pipeline = InvocationPipeline(
            final_validator=FakeFinalValidator(),
            evidence_sink=sink,
        )

        await pipeline.finalize(
            make_composed_prompt(), make_invocation_context(), prepared=prepared
        )
        assert sink.records[0].audit_state == AuditState.RUNTIME_VERIFIED

    @pytest.mark.asyncio
    async def test_static_verified_when_no_final_validator(self) -> None:
        sink = FakeEvidenceSink()
        prepared = PreparedInvocation(
            context=make_invocation_context(),
            validation=ValidationResult(status=ValidationStatus.PASS),
        )
        pipeline = InvocationPipeline(evidence_sink=sink)

        await pipeline.finalize(
            make_composed_prompt(), make_invocation_context(), prepared=prepared
        )
        assert sink.records[0].audit_state == AuditState.STATIC_VERIFIED

    @pytest.mark.asyncio
    async def test_static_verified_when_no_validators_at_all(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)

        await pipeline.finalize(make_composed_prompt(), make_invocation_context(), prepared=None)
        assert sink.records[0].audit_state == AuditState.STATIC_VERIFIED


class TestFinalizePreparedNone:
    """19. prepared=None — budget profile is None in evidence."""

    @pytest.mark.asyncio
    async def test_budget_profile_none_when_no_prepared(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)
        await pipeline.finalize(make_composed_prompt(), make_invocation_context(), prepared=None)
        assert sink.records[0].output_budget_profile is None


class TestFinalizeCombinedErrors:
    """20. Validation errors from both variable and final validators combined."""

    @pytest.mark.asyncio
    async def test_errors_combined_from_both_phases(self) -> None:
        sink = FakeEvidenceSink()
        prepared = PreparedInvocation(
            context=make_invocation_context(),
            validation=ValidationResult(
                status=ValidationStatus.FAIL,
                errors=("Missing user_preferences",),
            ),
        )
        pipeline = InvocationPipeline(
            final_validator=FakeFinalValidator(
                result=ValidationResult(
                    status=ValidationStatus.FAIL,
                    errors=("Missing output-language control",),
                )
            ),
            evidence_sink=sink,
        )

        await pipeline.finalize(
            make_composed_prompt(), make_invocation_context(), prepared=prepared
        )
        evidence = sink.records[0]
        assert "Missing user_preferences" in evidence.validation_errors
        assert "Missing output-language control" in evidence.validation_errors
        assert len(evidence.validation_errors) == 2


class TestFinalizeEvidenceFields:
    """Verify evidence record fields are populated correctly."""

    @pytest.mark.asyncio
    async def test_prompt_route_with_mode(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)
        await pipeline.finalize(make_composed_prompt(), make_invocation_context(mode="interactive"))
        assert sink.records[0].prompt_route == "write/interactive"

    @pytest.mark.asyncio
    async def test_prompt_route_without_mode(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)
        await pipeline.finalize(make_composed_prompt(), make_invocation_context())
        assert sink.records[0].prompt_route == "write/default"

    @pytest.mark.asyncio
    async def test_final_prompt_validated_true(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(
            final_validator=FakeFinalValidator(),
            evidence_sink=sink,
        )
        await pipeline.finalize(make_composed_prompt(), make_invocation_context())
        assert sink.records[0].final_prompt_validated is True

    @pytest.mark.asyncio
    async def test_final_prompt_validated_false_when_no_validator(self) -> None:
        sink = FakeEvidenceSink()
        pipeline = InvocationPipeline(evidence_sink=sink)
        await pipeline.finalize(make_composed_prompt(), make_invocation_context())
        assert sink.records[0].final_prompt_validated is False

    @pytest.mark.asyncio
    async def test_budget_profile_from_prepared(self) -> None:
        sink = FakeEvidenceSink()
        prepared = PreparedInvocation(
            context=make_invocation_context(),
            validation=ValidationResult(status=ValidationStatus.PASS),
            budget=OutputBudgetDecision(
                budget=OutputBudget(max_tokens=2048, profile="quick"),
                source="test",
                reason="test budget",
            ),
        )
        pipeline = InvocationPipeline(evidence_sink=sink)
        await pipeline.finalize(
            make_composed_prompt(), make_invocation_context(), prepared=prepared
        )
        assert sink.records[0].output_budget_profile == "quick"
