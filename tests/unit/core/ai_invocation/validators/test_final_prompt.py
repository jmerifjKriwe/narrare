"""Tests for FinalPromptValidatorImpl.

Covers all 10 mandatory test cases:
1. Happy path — clean prompt with no {{...}} → PASS.
2. Unresolved {{variable}} in system prompt → FAIL with variable name.
3. Unresolved {{variable}} in user prompt → FAIL.
4. Multiple unresolved variables → single FAIL with all listed.
5. Empty system prompt → FAIL.
6. Empty user prompt → PASS with warning.
7. first_message set → PASS with warning.
8. No unresolved vars, non-empty prompts → PASS.
9. Protocol conformance.
10. Whitespace-only system prompt → FAIL.

See: ADR-038, INFRA-013, CONSTRAINTS.md RULE-10.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import (
    PromptInvocationContext,
    ValidationResult,
)
from narrare_core.ai_invocation.validators.final_prompt import (
    FinalPromptValidatorImpl,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare_core.ai_invocation.contracts import FinalPromptValidator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides: object) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext for tests."""
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


def _make_prompt(
    *,
    system: str = "You are a helpful assistant.",
    user: str = "Write a story.",
    first_message: str | None = None,
) -> ComposedPrompt:
    """Create a ComposedPrompt for tests."""
    return ComposedPrompt(
        system=system,
        user=user,
        first_message=first_message,
    )


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Clean prompt with no {{...}} → PASS."""

    def test_clean_prompt_passes(self) -> None:
        """No unresolved variables and non-empty prompts → PASS."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt()
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.PASS
        assert result.is_valid is True
        assert result.errors == ()
        assert result.warnings == ()


# ---------------------------------------------------------------------------
# 2. Unresolved {{variable}} in system prompt → FAIL with variable name
# ---------------------------------------------------------------------------


class TestUnresolvedSystemVars:
    """Unresolved variables in system prompt block the invocation."""

    def test_single_unresolved_system_var(self) -> None:
        """FAIL with variable name when system prompt has {{project_title}}."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(system="Title: {{project_title}}")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("{{project_title}}" in e for e in result.errors)
        assert any("system prompt" in e for e in result.errors)

    def test_unresolved_var_in_error_message(self) -> None:
        """Error message contains the exact unresolved variable name."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(system="Language: {{language}}, Role: {{role}}")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.FAIL
        error_text = " ".join(result.errors)
        assert "{{language}}" in error_text
        assert "{{role}}" in error_text


# ---------------------------------------------------------------------------
# 3. Unresolved {{variable}} in user prompt → FAIL
# ---------------------------------------------------------------------------


class TestUnresolvedUserVars:
    """Unresolved variables in user prompt block the invocation."""

    def test_single_unresolved_user_var(self) -> None:
        """FAIL with variable name when user prompt has {{chapter_title}}."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(user="Continue: {{chapter_title}}")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("{{chapter_title}}" in e for e in result.errors)
        assert any("user prompt" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 4. Multiple unresolved variables → single FAIL with all listed
# ---------------------------------------------------------------------------


class TestMultipleUnresolvedVars:
    """Multiple unresolved variables produce separate errors for system/user."""

    def test_vars_in_both_prompts(self) -> None:
        """Two errors: one for system vars, one for user vars."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(
            system="Title: {{project_title}}, Lang: {{language}}",
            user="Content: {{chapter_title}}, Scene: {{scene}}",
        )
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.FAIL
        assert len(result.errors) == 2
        system_errors = [e for e in result.errors if "system prompt" in e]
        user_errors = [e for e in result.errors if "user prompt" in e]
        assert len(system_errors) == 1
        assert len(user_errors) == 1

    def test_deduplicated_same_var(self) -> None:
        """Same variable appearing multiple times is listed once."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(system="{{language}} and {{language}}")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.FAIL
        system_errors = [e for e in result.errors if "system prompt" in e]
        assert len(system_errors) == 1
        # Should only mention {{language}} once
        error_text = system_errors[0]
        assert error_text.count("{{language}}") == 1


# ---------------------------------------------------------------------------
# 5. Empty system prompt → FAIL
# ---------------------------------------------------------------------------


class TestEmptySystemPrompt:
    """Empty system prompt blocks the invocation."""

    def test_empty_system_fails(self) -> None:
        """FAIL when system prompt is empty string."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(system="")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("System prompt is empty" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 6. Empty user prompt → PASS with warning
# ---------------------------------------------------------------------------


class TestEmptyUserPrompt:
    """Empty user prompt is a warning, not an error."""

    def test_empty_user_passes_with_warning(self) -> None:
        """PASS with warning when user prompt is empty string."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(user="")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.PASS
        assert result.is_valid is True
        assert len(result.warnings) >= 1
        warning_codes = [w.code for w in result.warnings]
        assert "empty_user_prompt" in warning_codes


# ---------------------------------------------------------------------------
# 7. first_message set → PASS with warning
# ---------------------------------------------------------------------------


class TestFirstMessageSet:
    """Non-empty first_message produces a warning."""

    def test_first_message_set_passes_with_warning(self) -> None:
        """PASS with warning when first_message is set."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(first_message="Hello! I'm your AI assistant.")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.PASS
        assert result.is_valid is True
        warning_codes = [w.code for w in result.warnings]
        assert "first_message_set" in warning_codes

    def test_none_first_message_no_warning(self) -> None:
        """No warning when first_message is None."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(first_message=None)
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.PASS
        warning_codes = [w.code for w in result.warnings]
        assert "first_message_set" not in warning_codes

    def test_empty_string_first_message_no_warning(self) -> None:
        """No warning when first_message is empty string."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(first_message="")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.PASS
        warning_codes = [w.code for w in result.warnings]
        assert "first_message_set" not in warning_codes


# ---------------------------------------------------------------------------
# 8. No unresolved vars, non-empty prompts → PASS
# ---------------------------------------------------------------------------


class TestCleanPrompt:
    """Valid prompt with no issues."""

    def test_no_vars_no_issues(self) -> None:
        """PASS with no warnings for a clean prompt."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt()
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.PASS
        assert result.errors == ()
        assert result.warnings == ()

    def test_text_with_braces_not_template(self) -> None:
        """Single braces { } are not template variables."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(
            system="Use {variable} for formatting",
            user='JSON: {"key": "value"}',
        )
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.PASS


# ---------------------------------------------------------------------------
# 9. Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """FinalPromptValidatorImpl satisfies FinalPromptValidator."""

    def test_has_validate_method(self) -> None:
        """Validator has the required validate method."""
        validator = FinalPromptValidatorImpl()
        assert hasattr(validator, "validate")
        assert callable(validator.validate)

    def test_validate_returns_validation_result(self) -> None:
        """Validate method returns ValidationResult."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt()
        ctx = _make_context()
        result = validator.validate(prompt, ctx)
        assert isinstance(result, ValidationResult)

    def test_satisfies_protocol_structurally(self) -> None:
        """FinalPromptValidatorImpl is structurally compatible with Protocol."""

        def _accepts_validator(validator: FinalPromptValidator) -> None:
            pass

        # Should not raise a type error at runtime
        _accepts_validator(FinalPromptValidatorImpl())


# ---------------------------------------------------------------------------
# 10. Whitespace-only system prompt → FAIL
# ---------------------------------------------------------------------------


class TestWhitespaceSystemPrompt:
    """Whitespace-only system prompt is treated as empty."""

    def test_whitespace_only_system_fails(self) -> None:
        """FAIL when system prompt contains only whitespace."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(system="   \n\t  ")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("System prompt is empty" in e for e in result.errors)

    def test_newlines_only_system_fails(self) -> None:
        """FAIL when system prompt contains only newlines."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(system="\n\n\n")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.FAIL
        assert any("System prompt is empty" in e for e in result.errors)

    def test_tabs_only_system_fails(self) -> None:
        """FAIL when system prompt contains only tabs."""
        validator = FinalPromptValidatorImpl()
        prompt = _make_prompt(system="\t\t")
        ctx = _make_context()
        result = validator.validate(prompt, ctx)

        assert result.status == ValidationStatus.FAIL
