"""Tests for prompts/variable_engine.py"""

from __future__ import annotations

import pytest

from narrare_core.prompts.variable_engine import (
    extract_variables,
    substitute,
    validate_variables,
)
from narrare_core.shared.errors import PromptVariableError


class TestExtractVariables:
    def test_finds_variables(self) -> None:
        template = "Hello {{name}}, you are writing {{genre}}."
        vars_ = extract_variables(template)
        names = {v.name for v in vars_}
        assert names == {"name", "genre"}

    def test_no_variables(self) -> None:
        assert extract_variables("No variables here.") == []

    def test_deduplicates(self) -> None:
        template = "{{name}} and {{name}} again."
        vars_ = extract_variables(template)
        assert len(vars_) == 1


class TestSubstitute:
    def test_replaces_variables(self) -> None:
        result = substitute("Hello {{name}}!", {"name": "Anna"})
        assert result == "Hello Anna!"

    def test_raises_on_missing_strict(self) -> None:
        with pytest.raises(PromptVariableError, match="missing_var"):
            substitute("{{missing_var}}", {}, strict=True)

    def test_leaves_missing_unchanged_non_strict(self) -> None:
        result = substitute("{{missing}}", {}, strict=False)
        assert result == "{{missing}}"

    def test_multiple_replacements(self) -> None:
        result = substitute(
            "{{a}} and {{b}}",
            {"a": "foo", "b": "bar"},
        )
        assert result == "foo and bar"


class TestValidateVariables:
    def test_returns_empty_when_all_present(self) -> None:
        missing = validate_variables("{{a}} {{b}}", {"a": "1", "b": "2"})
        assert missing == []

    def test_returns_missing_variables(self) -> None:
        missing = validate_variables("{{a}} {{b}} {{c}}", {"a": "1"})
        assert set(missing) == {"b", "c"}
