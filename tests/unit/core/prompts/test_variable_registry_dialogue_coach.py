"""Tests for the new DIALOGUE_COACH template variables.

ADR-069 Decision 10 requires {{characters}} and {{text_to_analyze}}
to be registered before the dialogue_coach template (Phase 4) can
reference them. This task registers both — Phase 4 wires them into
the template.

See: ADR-069 Decision 10, CONSTRAINTS.md RULE-22 §4.
"""

from __future__ import annotations

from narrare_core.prompts.variable_registry import (
    SYSTEM_VARS,
    USER_CONTENT_VARS,
    get_variable_classification,
    is_registered_variable,
)


class TestCharactersVariable:
    """{{characters}} — system-generated list of speaker names."""

    def test_registered_in_system_vars(self) -> None:
        assert "characters" in SYSTEM_VARS

    def test_is_registered_variable(self) -> None:
        assert is_registered_variable("characters")

    def test_classification_exists(self) -> None:
        c = get_variable_classification("characters")
        assert c is not None


class TestTextToAnalyzeVariable:
    """{{text_to_analyze}} — user-authored selection from the editor."""

    def test_registered_in_user_content_vars(self) -> None:
        """Per ADR-069 Decision 10: text_to_analyze is user content
        (must be XML-tag-wrapped in the Phase 4 template per RULE-22 §6)."""
        assert "text_to_analyze" in USER_CONTENT_VARS

    def test_is_registered_variable(self) -> None:
        assert is_registered_variable("text_to_analyze")

    def test_classification_exists(self) -> None:
        c = get_variable_classification("text_to_analyze")
        assert c is not None
