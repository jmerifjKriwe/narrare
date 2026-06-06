"""Tests for RuntimeVariableValidatorImpl.

10 mandatory test cases:
1. Happy path → PASS.
2. Missing user_preferences when REQUIRED → FAIL.
3. Missing kb_suggested when PROVIDED → FAIL.
4. Preference NOT_APPLICABLE → PASS.
5. No adoption policy → PASS.
6. Language too short → FAIL.
7. output_language None → PASS with warning.
8. Empty dynamic_inputs when not required → PASS.
9. Protocol conformance.
10. Multiple failures → multiple errors.

See: ADR-038, INFRA-013, CONSTRAINTS.md RULE-10.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.ai_invocation._enums import (
    KBSuggestedRequirement,
    PreferenceRequirement,
    ValidationStatus,
)
from narrare_core.ai_invocation.models import (
    AdoptionPolicy,
    PromptInvocationContext,
    ValidationResult,
)
from narrare_core.ai_invocation.validators.runtime import (
    RuntimeVariableValidatorImpl,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare_core.ai_invocation.contracts import RuntimeVariableValidator


def _make_context(**overrides: object) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext for tests."""
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
        "language": "en",
        "output_language": "en",
        "dynamic_inputs": {"user_preferences": "some prefs"},
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


def _make_context_unsafe(**overrides: object) -> PromptInvocationContext:
    """Create context bypassing Pydantic validation via model_construct().

    Needed to test validator defense-in-depth for conditions Pydantic
    normally prevents (e.g. language shorter than min_length=2).
    """
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
        "language": "en",
        "output_language": "en",
        "dynamic_inputs": {"user_preferences": "some prefs"},
    }
    defaults.update(overrides)
    return PromptInvocationContext.model_construct(**defaults)  # type: ignore[arg-type]


def _make_policy(**overrides: object) -> AdoptionPolicy:
    """Create an AdoptionPolicy for tests."""
    defaults: dict[str, object] = {
        "preference_requirement": PreferenceRequirement.NOT_APPLICABLE,
        "kb_suggested_requirement": KBSuggestedRequirement.NOT_APPLICABLE,
    }
    defaults.update(overrides)
    return AdoptionPolicy(**defaults)  # type: ignore[arg-type]


# 1. Happy path


class TestHappyPath:
    """All required inputs present → PASS."""

    def test_all_inputs_present_returns_pass(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        ctx = _make_context()
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.PASS
        assert result.is_valid is True
        assert result.errors == ()

    def test_all_inputs_with_policy_required(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        policy = _make_policy(
            preference_requirement=PreferenceRequirement.REQUIRED,
            kb_suggested_requirement=KBSuggestedRequirement.PROVIDED,
        )
        ctx = _make_context(
            adoption_policy=policy,
            dynamic_inputs={
                "user_preferences": "style: concise",
                "kb_suggested": "character: Anna",
            },
        )
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.PASS
        assert result.is_valid is True


# 2. Missing user_preferences when REQUIRED → FAIL


class TestMissingPreferences:
    """Preference REQUIRED but user_preferences missing."""

    def test_missing_user_preferences_fails(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        policy = _make_policy(
            preference_requirement=PreferenceRequirement.REQUIRED,
        )
        ctx = _make_context(adoption_policy=policy, dynamic_inputs={})
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("user_preferences" in e for e in result.errors)

    def test_empty_user_preferences_fails(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        policy = _make_policy(
            preference_requirement=PreferenceRequirement.REQUIRED,
        )
        ctx = _make_context(
            adoption_policy=policy,
            dynamic_inputs={"user_preferences": ""},
        )
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("user_preferences" in e for e in result.errors)


# 3. Missing kb_suggested when PROVIDED → FAIL


class TestMissingKBSuggested:
    """KB-suggested PROVIDED but kb_suggested missing."""

    def test_missing_kb_suggested_fails(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        policy = _make_policy(
            kb_suggested_requirement=KBSuggestedRequirement.PROVIDED,
        )
        ctx = _make_context(adoption_policy=policy, dynamic_inputs={})
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("kb_suggested" in e for e in result.errors)

    def test_empty_kb_suggested_fails(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        policy = _make_policy(
            kb_suggested_requirement=KBSuggestedRequirement.PROVIDED,
        )
        ctx = _make_context(
            adoption_policy=policy,
            dynamic_inputs={"kb_suggested": ""},
        )
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("kb_suggested" in e for e in result.errors)


# 4. Preference NOT_APPLICABLE → PASS


class TestPreferenceNotApplicable:
    """NOT_APPLICABLE means no preference check."""

    def test_not_applicable_passes_without_preferences(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        policy = _make_policy(
            preference_requirement=PreferenceRequirement.NOT_APPLICABLE,
        )
        ctx = _make_context(adoption_policy=policy, dynamic_inputs={})
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.PASS


# 5. No adoption policy → PASS


class TestNoAdoptionPolicy:
    """No adoption policy → no preference/KB checks."""

    def test_none_policy_passes(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        ctx = _make_context(adoption_policy=None, dynamic_inputs={})
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.PASS


# 6. Language too short → FAIL


class TestLanguageTooShort:
    """Language must be ≥ 2 characters.

    Uses model_construct() to bypass Pydantic's min_length=2 so the
    validator's own defense-in-depth is exercised.
    """

    def test_single_char_language_fails(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        ctx = _make_context_unsafe(language="e")
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("language" in e for e in result.errors)

    def test_empty_language_fails(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        ctx = _make_context_unsafe(language="")
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("language" in e for e in result.errors)

    def test_two_char_language_passes(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        ctx = _make_context(language="en")
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.PASS


# 7. output_language None → PASS with warning


class TestOutputLanguageUnset:
    """Missing output_language is a warning, not an error."""

    def test_output_language_none_passes_with_warning(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        ctx = _make_context(output_language=None)
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.PASS
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "output_language_unset"
        assert result.warnings[0].field == "output_language"

    def test_output_language_set_no_warning(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        ctx = _make_context(output_language="de")
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.PASS
        assert len(result.warnings) == 0


# 8. Empty dynamic_inputs when not required → PASS


class TestEmptyDynamicInputs:
    """Empty dynamic_inputs valid when no policy requires them."""

    def test_empty_inputs_no_policy_passes(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        ctx = _make_context(adoption_policy=None, dynamic_inputs={})
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.PASS
        assert result.is_valid is True


# 9. Protocol conformance


class TestProtocolConformance:
    """RuntimeVariableValidatorImpl satisfies RuntimeVariableValidator."""

    def test_has_validate_method(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        assert hasattr(validator, "validate")
        assert callable(validator.validate)

    def test_validate_returns_validation_result(self) -> None:
        validator = RuntimeVariableValidatorImpl()
        ctx = _make_context()
        result = validator.validate(ctx)
        assert isinstance(result, ValidationResult)

    def test_satisfies_protocol_structurally(self) -> None:
        def _accepts_validator(validator: RuntimeVariableValidator) -> None:
            pass

        _accepts_validator(RuntimeVariableValidatorImpl())


# 10. Multiple failures → multiple errors


class TestMultipleFailures:
    """Multiple failures produce multiple errors in tuple."""

    def test_missing_prefs_and_short_language(self) -> None:
        """Two independent failures produce two errors."""
        validator = RuntimeVariableValidatorImpl()
        policy = _make_policy(
            preference_requirement=PreferenceRequirement.REQUIRED,
        )
        ctx = _make_context_unsafe(
            adoption_policy=policy,
            dynamic_inputs={},
            language="x",
        )
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.FAIL
        assert len(result.errors) == 2

    def test_all_required_missing_produces_multiple_errors(self) -> None:
        """Preference + KB + language all missing → 3 errors."""
        validator = RuntimeVariableValidatorImpl()
        policy = _make_policy(
            preference_requirement=PreferenceRequirement.REQUIRED,
            kb_suggested_requirement=KBSuggestedRequirement.PROVIDED,
        )
        ctx = _make_context_unsafe(
            adoption_policy=policy,
            dynamic_inputs={},
            language="x",
        )
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.FAIL
        assert len(result.errors) == 3
        error_texts = " ".join(result.errors)
        assert "user_preferences" in error_texts
        assert "kb_suggested" in error_texts
        assert "language" in error_texts

    def test_failures_include_warnings(self) -> None:
        """FAIL with errors can also include warnings."""
        validator = RuntimeVariableValidatorImpl()
        policy = _make_policy(
            preference_requirement=PreferenceRequirement.REQUIRED,
        )
        ctx = _make_context(
            adoption_policy=policy,
            dynamic_inputs={},
            language="en",
            output_language=None,
        )
        result = validator.validate(ctx)

        assert result.status == ValidationStatus.FAIL
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "output_language_unset"
