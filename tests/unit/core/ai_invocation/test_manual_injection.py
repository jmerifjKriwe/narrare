"""Tests for ManualInjectionDeclaration (ADR-048 Contract 1).

Validates the frozen Pydantic model that declares agent-internal prompt
composition (ADR-045 Decision 3 Option C).

See: ADR-048, ADR-045 Decision 3, CONSTRAINTS.md RULE-03.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration


class TestManualInjectionDeclarationFields:
    """Required fields and defaults."""

    def test_valid_declaration_with_all_fields(self) -> None:
        decl = ManualInjectionDeclaration(
            reason="KBConsistencyAnalyzer composes prompts internally from deps.",
            variables=("entity_summaries", "template_structures"),
            injection_mechanism="agent_deps",
        )
        assert decl.reason.startswith("KBConsistencyAnalyzer")
        assert decl.variables == ("entity_summaries", "template_structures")
        assert decl.injection_mechanism == "agent_deps"

    def test_default_precedence_level(self) -> None:
        decl = ManualInjectionDeclaration(
            reason="Agent owns composition from internal deps.",
            variables=("entity_summaries",),
            injection_mechanism="agent_deps",
        )
        assert decl.precedence_level == "generated_suggestion"

    def test_custom_precedence_level(self) -> None:
        decl = ManualInjectionDeclaration(
            reason="Agent owns composition from internal deps.",
            variables=("entity_summaries",),
            injection_mechanism="agent_deps",
            precedence_level="curated_kb",
        )
        assert decl.precedence_level == "curated_kb"


class TestManualInjectionDeclarationValidation:
    """Pydantic field validators."""

    def test_reason_min_length_enforced(self) -> None:
        with pytest.raises(ValidationError, match="reason"):
            ManualInjectionDeclaration(
                reason="too short",
                variables=("entity_summaries",),
                injection_mechanism="agent_deps",
            )

    def test_variables_requires_at_least_one(self) -> None:
        with pytest.raises(ValidationError, match="variables"):
            ManualInjectionDeclaration(
                reason="Agent owns composition from internal deps.",
                variables=(),
                injection_mechanism="agent_deps",
            )

    def test_missing_reason_raises(self) -> None:
        with pytest.raises(ValidationError, match="reason"):
            ManualInjectionDeclaration(
                variables=("entity_summaries",),
                injection_mechanism="agent_deps",
            )  # type: ignore[call-arg]

    def test_missing_variables_raises(self) -> None:
        with pytest.raises(ValidationError, match="variables"):
            ManualInjectionDeclaration(
                reason="Agent owns composition from internal deps.",
                injection_mechanism="agent_deps",
            )  # type: ignore[call-arg]

    def test_missing_injection_mechanism_raises(self) -> None:
        with pytest.raises(ValidationError, match="injection_mechanism"):
            ManualInjectionDeclaration(
                reason="Agent owns composition from internal deps.",
                variables=("entity_summaries",),
            )  # type: ignore[call-arg]

    def test_variables_accepts_tuple_type(self) -> None:
        decl = ManualInjectionDeclaration(
            reason="Agent owns composition from internal deps.",
            variables=("a", "b", "c"),
            injection_mechanism="agent_deps",
        )
        assert isinstance(decl.variables, tuple)
        assert decl.variables == ("a", "b", "c")


class TestManualInjectionDeclarationImmutability:
    """Frozen model cannot be mutated."""

    def test_frozen_model_rejects_assignment(self) -> None:
        decl = ManualInjectionDeclaration(
            reason="Agent owns composition from internal deps.",
            variables=("entity_summaries",),
            injection_mechanism="agent_deps",
        )
        with pytest.raises(ValidationError):
            decl.reason = "changed"  # type: ignore[misc]

    def test_frozen_model_rejects_new_field(self) -> None:
        decl = ManualInjectionDeclaration(
            reason="Agent owns composition from internal deps.",
            variables=("entity_summaries",),
            injection_mechanism="agent_deps",
        )
        with pytest.raises(ValidationError):
            decl.extra_field = "value"  # type: ignore[attr-defined]

    def test_model_copy_produces_new_instance(self) -> None:
        decl = ManualInjectionDeclaration(
            reason="Agent owns composition from internal deps.",
            variables=("entity_summaries",),
            injection_mechanism="agent_deps",
        )
        clone = decl.model_copy()
        assert clone == decl
        assert clone is not decl
