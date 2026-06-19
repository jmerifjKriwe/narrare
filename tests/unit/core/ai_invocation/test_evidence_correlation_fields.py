"""Tests for ADR-045 Phase 3 correlation fields populated by build_invocation_evidence.

Split from ``test_evidence_serialization.py`` to respect RULE-04.

Covers:
1. ``invocation_id`` is preserved when present, generated when absent.
2. ``streaming`` reflects the invocation context.
3. ``prepared_context_fingerprint`` is populated (keys/counts only).
4. ``prompt_fingerprint`` is populated when a prompt is supplied.
5. ``budget_decision_fingerprint`` is populated when a budget is present.
6. Privacy: raw prompt text, dynamic-input values, and budget rationale
   never appear in the serialized evidence.

See: ADR-045, CONSTRAINTS.md RULE-04/RULE-20.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation._evidence import build_invocation_evidence
from narrare_core.ai_invocation.budgets._types import (
    OutputBudget,
    OutputBudgetDecision,
)
from narrare_core.ai_invocation.models import PromptInvocationContext, ValidationResult
from narrare_core.ai_invocation.pipeline import PreparedInvocation
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt


def _ctx(**overrides: object) -> PromptInvocationContext:
    """Minimal invocation context with optional overrides."""
    defaults: dict[str, object] = {
        "feature_id": "writing/extend",
        "intent": LLMIntent.EXTEND,
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


def _passing_validation() -> ValidationResult:
    return ValidationResult(status=ValidationStatus.PASS)


def _budget_decision(profile: str = "balanced", max_tokens: int = 4096) -> OutputBudgetDecision:
    return OutputBudgetDecision(
        budget=OutputBudget(max_tokens=max_tokens, profile=profile),
        source="intent_profile",
        reason="Secret rationale that must NOT leak into evidence.",
    )


class TestCorrelationFieldsPopulated:
    """build_invocation_evidence must populate the ADR-045 correlation fields."""

    def test_invocation_id_preserved_when_present(self) -> None:
        ident = uuid4()
        prepared = PreparedInvocation(
            context=_ctx(invocation_id=ident), validation=_passing_validation()
        )

        evidence = build_invocation_evidence(
            context=_ctx(invocation_id=ident),
            prepared=prepared,
            final_validation=_passing_validation(),
            final_validator_ran=True,
        )

        assert evidence.invocation_id == ident

    def test_invocation_id_generated_when_absent(self) -> None:
        evidence = build_invocation_evidence(
            context=_ctx(),
            prepared=None,
            final_validation=_passing_validation(),
            final_validator_ran=True,
        )

        assert evidence.invocation_id is not None
        assert isinstance(evidence.invocation_id, UUID)

    def test_streaming_reflects_context(self) -> None:
        evidence = build_invocation_evidence(
            context=_ctx(streaming=True),
            prepared=None,
            final_validation=_passing_validation(),
            final_validator_ran=False,
        )

        assert evidence.streaming is True

    def test_prepared_context_fingerprint_populated(self) -> None:
        prepared = PreparedInvocation(
            context=_ctx(dynamic_inputs={"user_preferences": "secret-value"}),
            validation=_passing_validation(),
        )

        evidence = build_invocation_evidence(
            context=_ctx(),
            prepared=prepared,
            final_validation=_passing_validation(),
            final_validator_ran=False,
        )

        assert evidence.prepared_context_fingerprint is not None
        # 64-char sha256 hex digest
        assert len(evidence.prepared_context_fingerprint) == 64

    def test_prompt_fingerprint_populated_when_prompt_given(self) -> None:
        prompt = ComposedPrompt(system="secret system prose", user="secret user prose")

        evidence = build_invocation_evidence(
            context=_ctx(),
            prepared=None,
            final_validation=_passing_validation(),
            final_validator_ran=False,
            prompt=prompt,
        )

        assert evidence.prompt_fingerprint is not None
        assert len(evidence.prompt_fingerprint) == 64

    def test_prompt_fingerprint_none_when_no_prompt(self) -> None:
        evidence = build_invocation_evidence(
            context=_ctx(),
            prepared=None,
            final_validation=_passing_validation(),
            final_validator_ran=False,
        )

        assert evidence.prompt_fingerprint is None

    def test_budget_decision_fingerprint_populated_when_budget_present(self) -> None:
        prepared = PreparedInvocation(
            context=_ctx(),
            validation=_passing_validation(),
            budget=_budget_decision(profile="comprehensive", max_tokens=16000),
        )

        evidence = build_invocation_evidence(
            context=_ctx(),
            prepared=prepared,
            final_validation=_passing_validation(),
            final_validator_ran=False,
        )

        assert evidence.budget_decision_fingerprint is not None
        assert len(evidence.budget_decision_fingerprint) == 64

    def test_budget_decision_fingerprint_none_without_budget(self) -> None:
        prepared = PreparedInvocation(context=_ctx(), validation=_passing_validation())

        evidence = build_invocation_evidence(
            context=_ctx(),
            prepared=prepared,
            final_validation=_passing_validation(),
            final_validator_ran=False,
        )

        assert evidence.budget_decision_fingerprint is None


class TestCorrelationFieldsPrivacy:
    """Correlation fingerprints must never leak raw prompt text or user prose."""

    def test_raw_prompt_text_absent_from_serialized_evidence(self) -> None:
        prompt = ComposedPrompt(
            system="HIGHLY CONFIDENTIAL SYSTEM PROSE",
            user="HIGHLY CONFIDENTIAL USER PROSE",
        )

        evidence = build_invocation_evidence(
            context=_ctx(),
            prepared=None,
            final_validation=_passing_validation(),
            final_validator_ran=False,
            prompt=prompt,
        )

        dumped = evidence.model_dump_json()
        assert "CONFIDENTIAL" not in dumped

    def test_raw_dynamic_input_value_absent_from_serialized_evidence(self) -> None:
        prepared = PreparedInvocation(
            context=_ctx(dynamic_inputs={"user_preferences": "NEVER LEAK THIS SENTENCE"}),
            validation=_passing_validation(),
        )

        evidence = build_invocation_evidence(
            context=_ctx(),
            prepared=prepared,
            final_validation=_passing_validation(),
            final_validator_ran=False,
        )

        dumped = evidence.model_dump_json()
        assert "NEVER LEAK THIS SENTENCE" not in dumped

    def test_budget_reason_absent_from_serialized_evidence(self) -> None:
        prepared = PreparedInvocation(
            context=_ctx(),
            validation=_passing_validation(),
            budget=_budget_decision(),
        )

        evidence = build_invocation_evidence(
            context=_ctx(),
            prepared=prepared,
            final_validation=_passing_validation(),
            final_validator_ran=False,
        )

        dumped = evidence.model_dump_json()
        assert "Secret rationale" not in dumped
