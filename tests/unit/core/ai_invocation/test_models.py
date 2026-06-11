"""Tests for ai_invocation/models.py — value objects and data models.

Covers:
1. PromptInvocationContext — required fields, empty feature_id invalid,
   accepts existing PromptContext reference.
2. AdoptionPolicy — defaults and construction.
3. InvocationWarning — construction and immutability.
4. ValidationResult — pass/fail status and is_valid property.
5. ContextEnrichmentResult — construction and fields.
6. Enums — all values match ADR-038.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare_core.ai_invocation.models import (
    AdoptionPolicy,
    AuditState,
    ContextEnrichmentResult,
    InvocationWarning,
    KBSuggestedRequirement,
    KBSuggestedStatus,
    PreferenceRequirement,
    PreferenceStatus,
    PromptInvocationContext,
    ValidationResult,
    ValidationStatus,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

# ---------------------------------------------------------------------------
# PromptInvocationContext
# ---------------------------------------------------------------------------


class TestPromptInvocationContext:
    """PromptInvocationContext construction and validation."""

    def test_minimal_required_fields(self) -> None:
        ctx = PromptInvocationContext(
            feature_id="writing/new_chapter",
            intent=LLMIntent.WRITE,
        )
        assert ctx.feature_id == "writing/new_chapter"
        assert ctx.intent == LLMIntent.WRITE
        assert ctx.mode is None
        assert ctx.language == "en"
        assert ctx.streaming is False
        assert ctx.required_features == frozenset()
        assert ctx.dynamic_inputs == {}
        assert ctx.adoption_policy is None
        assert ctx.prompt_context is None

    def test_empty_feature_id_invalid(self) -> None:
        with pytest.raises(ValidationError, match="feature_id"):
            PromptInvocationContext(feature_id="", intent=LLMIntent.WRITE)

    def test_blank_feature_id_accepted_by_min_length(self) -> None:
        """Pydantic min_length counts whitespace; trimming is caller-level."""
        ctx = PromptInvocationContext(feature_id="  ", intent=LLMIntent.WRITE)
        assert ctx.feature_id == "  "

    def test_accepts_all_fields(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        policy = AdoptionPolicy(
            preference_requirement=PreferenceRequirement.REQUIRED,
            kb_suggested_requirement=KBSuggestedRequirement.PROVIDED,
        )
        ctx = PromptInvocationContext(
            feature_id="writing/extend",
            intent=LLMIntent.EXTEND,
            mode="extend",
            user_id=user_id,
            project_id=project_id,
            language="de",
            output_language="Schweizerdeutsch",
            streaming=True,
            required_features=frozenset({"preferences", "kb_context"}),
            optional_features=frozenset({"voice_profiles"}),
            dynamic_inputs={"chapter_outline": "Outline text"},
            adoption_policy=policy,
        )
        assert ctx.user_id == user_id
        assert ctx.project_id == project_id
        assert ctx.language == "de"
        assert ctx.output_language == "Schweizerdeutsch"
        assert ctx.streaming is True
        assert ctx.required_features == frozenset({"preferences", "kb_context"})
        assert ctx.optional_features == frozenset({"voice_profiles"})
        assert ctx.dynamic_inputs == {"chapter_outline": "Outline text"}
        assert ctx.adoption_policy is not None
        assert ctx.adoption_policy.preference_requirement == PreferenceRequirement.REQUIRED

    def test_accepts_prompt_context_reference(self) -> None:
        prompt_ctx = PromptContext(language="en", project_title="Test Novel", mode="new_chapter")
        ctx = PromptInvocationContext(
            feature_id="writing/new_chapter",
            intent=LLMIntent.WRITE,
            prompt_context=prompt_ctx,
        )
        assert ctx.prompt_context is not None
        assert ctx.prompt_context.project_title == "Test Novel"

    def test_language_validation(self) -> None:
        with pytest.raises(ValidationError, match="language"):
            PromptInvocationContext(feature_id="test", intent=LLMIntent.WRITE, language="x")
        with pytest.raises(ValidationError, match="language"):
            PromptInvocationContext(feature_id="test", intent=LLMIntent.WRITE, language="english")

    def test_frozen_immutability(self) -> None:
        ctx = PromptInvocationContext(feature_id="test", intent=LLMIntent.WRITE)
        with pytest.raises(ValidationError, match="frozen"):
            cast("Any", ctx).feature_id = "changed"

    def test_model_copy_returns_new_instance(self) -> None:
        ctx = PromptInvocationContext(feature_id="test", intent=LLMIntent.WRITE)
        enriched = ctx.model_copy(update={"dynamic_inputs": {"user_preferences": "pref text"}})
        assert enriched.dynamic_inputs == {"user_preferences": "pref text"}
        assert ctx.dynamic_inputs == {}

    def test_intent_serialized_as_string(self) -> None:
        ctx = PromptInvocationContext(feature_id="test", intent=LLMIntent.SUMMARIZE)
        assert ctx.model_dump()["intent"] == "summarize"

    def test_missing_feature_id_fails(self) -> None:
        with pytest.raises(ValidationError, match="feature_id"):
            cast("Any", PromptInvocationContext)(intent=LLMIntent.WRITE)


# ---------------------------------------------------------------------------
# AdoptionPolicy
# ---------------------------------------------------------------------------


class TestAdoptionPolicy:
    """AdoptionPolicy defaults and construction."""

    def test_default_values(self) -> None:
        policy = AdoptionPolicy()
        assert policy.preference_requirement == PreferenceRequirement.NOT_APPLICABLE
        assert policy.kb_suggested_requirement == KBSuggestedRequirement.NOT_APPLICABLE
        assert policy.requires_output_budget is True
        assert policy.requires_final_validation is True

    def test_custom_values(self) -> None:
        policy = AdoptionPolicy(
            preference_requirement=PreferenceRequirement.REQUIRED,
            kb_suggested_requirement=KBSuggestedRequirement.PROVIDED,
            requires_output_budget=False,
            requires_final_validation=False,
        )
        assert policy.preference_requirement == PreferenceRequirement.REQUIRED
        assert policy.requires_output_budget is False

    def test_frozen(self) -> None:
        policy = AdoptionPolicy()
        with pytest.raises(ValidationError, match="frozen"):
            cast("Any", policy).preference_requirement = PreferenceRequirement.REQUIRED


# ---------------------------------------------------------------------------
# InvocationWarning
# ---------------------------------------------------------------------------


class TestInvocationWarning:
    """InvocationWarning construction and validation."""

    def test_basic_construction(self) -> None:
        warning = InvocationWarning(code="missing_preference", message="Not loaded")
        assert warning.code == "missing_preference"
        assert warning.field is None

    def test_with_field(self) -> None:
        warning = InvocationWarning(code="empty_var", message="Empty", field="preferences")
        assert warning.field == "preferences"

    def test_empty_code_invalid(self) -> None:
        with pytest.raises(ValidationError, match="code"):
            InvocationWarning(code="", message="msg")

    def test_empty_message_invalid(self) -> None:
        with pytest.raises(ValidationError, match="message"):
            InvocationWarning(code="code", message="")

    def test_frozen(self) -> None:
        warning = InvocationWarning(code="test", message="msg")
        with pytest.raises(ValidationError, match="frozen"):
            cast("Any", warning).code = "changed"


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    """ValidationResult status and warnings."""

    def test_pass_result(self) -> None:
        result = ValidationResult(status=ValidationStatus.PASS)
        assert result.is_valid is True
        assert result.errors == ()
        assert result.warnings == ()

    def test_fail_result(self) -> None:
        assert ValidationResult(status=ValidationStatus.FAIL).is_valid is False

    def test_with_errors(self) -> None:
        result = ValidationResult(
            status=ValidationStatus.FAIL,
            errors=("Missing required variable", "Unsafe content boundary"),
        )
        assert len(result.errors) == 2

    def test_with_warnings(self) -> None:
        result = ValidationResult(
            status=ValidationStatus.PASS,
            warnings=(InvocationWarning(code="partial", message="Partial"),),
        )
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "partial"

    def test_pass_with_warnings(self) -> None:
        result = ValidationResult(
            status=ValidationStatus.PASS,
            warnings=(InvocationWarning(code="optional", message="Optional missing"),),
        )
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# ContextEnrichmentResult
# ---------------------------------------------------------------------------


class TestContextEnrichmentResult:
    """ContextEnrichmentResult construction and fields."""

    def test_default_empty(self) -> None:
        result = ContextEnrichmentResult()
        assert result.enriched_fields == frozenset()
        assert result.enrichment_sources == ()

    def test_with_enriched_fields(self) -> None:
        result = ContextEnrichmentResult(
            enriched_fields=frozenset({"user_preferences", "kb_context"}),
            enrichment_sources=(
                ("user_preferences", "mem0"),
                ("kb_context", "context_assembler"),
            ),
        )
        assert "user_preferences" in result.enriched_fields
        assert len(result.enrichment_sources) == 2

    def test_with_warnings(self) -> None:
        result = ContextEnrichmentResult(
            enriched_fields=frozenset({"user_preferences"}),
            warnings=(InvocationWarning(code="partial", message="Partial"),),
        )
        assert len(result.warnings) == 1


# ---------------------------------------------------------------------------
# Enums — match ADR-038 definitions
# ---------------------------------------------------------------------------


class TestAuditStates:
    """Audit lifecycle states from ADR-038."""

    def test_all_states_defined(self) -> None:
        expected = {
            "identified",
            "specified",
            "static_verified",
            "runtime_verified",
            "adopted",
            "ratcheted_debt",
            "blocked",
        }
        assert {s.value for s in AuditState} == expected


class TestPreferenceStatuses:
    def test_all_statuses_defined(self) -> None:
        assert {s.value for s in PreferenceStatus} == {
            "provided",
            "manual",
            "not_applicable",
            "missing",
        }


class TestKBSuggestedStatuses:
    def test_all_statuses_defined(self) -> None:
        assert {s.value for s in KBSuggestedStatus} == {
            "provided",
            "budget_rejected",
            "not_applicable",
            "missing",
        }


class TestValidationStatuses:
    def test_all_statuses_defined(self) -> None:
        assert {s.value for s in ValidationStatus} == {"pass", "fail"}
