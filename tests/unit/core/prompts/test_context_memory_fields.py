"""Tests for PromptContext memory/preference fields.

Covers tasks 3.1-3.3 from generation-prompt-memory-foundation:
- New fields (user_preferences, avoidance_patterns, style_constraints) with defaults
- as_variables() includes new fields
- Values reflect in as_variables() output
"""

from __future__ import annotations

from narrare_core.prompts.context import PromptContext


class TestMemoryFieldDefaults:
    """Task 3.1: New memory fields exist with empty-string defaults."""

    def test_user_preferences_default(self) -> None:
        ctx = PromptContext()
        assert ctx.user_preferences == ""

    def test_avoidance_patterns_default(self) -> None:
        ctx = PromptContext()
        assert ctx.avoidance_patterns == ""

    def test_style_constraints_default(self) -> None:
        ctx = PromptContext()
        assert ctx.style_constraints == ""


class TestMemoryFieldsInAsVariables:
    """Task 3.2: as_variables() includes new memory fields."""

    def test_user_preferences_in_variables(self) -> None:
        ctx = PromptContext()
        variables = ctx.as_variables()
        assert "user_preferences" in variables
        assert variables["user_preferences"] == ""

    def test_avoidance_patterns_in_variables(self) -> None:
        ctx = PromptContext()
        variables = ctx.as_variables()
        assert "avoidance_patterns" in variables
        assert variables["avoidance_patterns"] == ""

    def test_style_constraints_in_variables(self) -> None:
        ctx = PromptContext()
        variables = ctx.as_variables()
        assert "style_constraints" in variables
        assert variables["style_constraints"] == ""


class TestMemoryFieldValuesReflect:
    """Task 3.3: Setting values on new fields reflects in as_variables()."""

    def test_user_preferences_value_reflects(self) -> None:
        ctx = PromptContext(user_preferences="Prefers dark themes and complex characters")
        variables = ctx.as_variables()
        assert variables["user_preferences"] == "Prefers dark themes and complex characters"

    def test_avoidance_patterns_value_reflects(self) -> None:
        ctx = PromptContext(avoidance_patterns="No cliffhangers, no explicit violence")
        variables = ctx.as_variables()
        assert variables["avoidance_patterns"] == "No cliffhangers, no explicit violence"

    def test_style_constraints_value_reflects(self) -> None:
        ctx = PromptContext(style_constraints="Use third-person limited POV")
        variables = ctx.as_variables()
        assert variables["style_constraints"] == "Use third-person limited POV"

    def test_all_three_set_simultaneously(self) -> None:
        ctx = PromptContext(
            user_preferences="Likes short chapters",
            avoidance_patterns="No romance subplots",
            style_constraints="Minimalist prose",
        )
        variables = ctx.as_variables()
        assert variables["user_preferences"] == "Likes short chapters"
        assert variables["avoidance_patterns"] == "No romance subplots"
        assert variables["style_constraints"] == "Minimalist prose"

    def test_memory_fields_do_not_leak_into_other_fields(self) -> None:
        """Setting memory fields should not affect other context fields."""
        ctx = PromptContext(
            user_preferences="Prefers fantasy",
            language="de",
            project_title="Test Novel",
        )
        variables = ctx.as_variables()
        assert variables["language"] == "de"
        assert variables["project_title"] == "Test Novel"
        assert variables["user_preferences"] == "Prefers fantasy"


class TestCrossSessionContextField:
    """PromptContext.cross_session_context — cross-session mem0 memories.

    Mirrors user_preferences / avoidance_patterns (memory-layer fields that
    surface cross-session writing memories to the prompt cascade).
    """

    def test_default_is_empty_string(self) -> None:
        ctx = PromptContext()
        assert ctx.cross_session_context == ""

    def test_value_reflects_in_as_variables(self) -> None:
        ctx = PromptContext(cross_session_context="- Author likes short chapters.")
        variables = ctx.as_variables()
        assert variables["cross_session_context"] == "- Author likes short chapters."

    def test_empty_default_reflects_in_as_variables(self) -> None:
        ctx = PromptContext()
        variables = ctx.as_variables()
        assert variables["cross_session_context"] == ""


class TestWritingLanguageFallback:
    """writing_language falls back to language when not explicitly set."""

    def test_writing_language_defaults_to_language(self) -> None:
        ctx = PromptContext(language="de")
        variables = ctx.as_variables()
        assert variables["writing_language"] == "de"

    def test_writing_language_defaults_to_en_when_language_missing(self) -> None:
        ctx = PromptContext()
        variables = ctx.as_variables()
        assert variables["writing_language"] == "en"

    def test_writing_language_explicit_overrides_fallback(self) -> None:
        ctx = PromptContext(language="de", writing_language="Schweizerdeutsch")
        variables = ctx.as_variables()
        assert variables["writing_language"] == "Schweizerdeutsch"
        assert variables["language"] == "de"

    def test_writing_language_preserves_language_field(self) -> None:
        """language field stays unchanged — only writing_language gets the fallback."""
        ctx = PromptContext(language="fr")
        variables = ctx.as_variables()
        assert variables["language"] == "fr"
        assert variables["writing_language"] == "fr"
