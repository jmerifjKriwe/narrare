"""
Property-based tests for prompts/variable_engine.py using Hypothesis.

Verifies that variable extraction, substitution, and validation
handle arbitrary inputs correctly and obey algebraic properties.
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from narrare_core.prompts.variable_engine import (
    VariableInfo,
    extract_variables,
    substitute,
    validate_variables,
)
from narrare_core.shared.errors import PromptVariableError

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Variable names: word characters only (what \w+ matches)
variable_name = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=("_")),
)

# A template string with no variables (plain text)
plain_text = st.text(min_size=0, max_size=200)


# A template string with embedded {{variable}} placeholders
@st.composite
def template_with_vars(draw: st.DrawFn) -> tuple[str, list[str]]:
    """Generate a template with variables and return (template, variable_names)."""
    parts: list[str] = []
    var_names: list[str] = []
    n_parts = draw(st.integers(min_value=1, max_value=10))

    for _ in range(n_parts):
        # Randomly insert plain text or a variable
        kind = draw(st.sampled_from(["text", "var"]))
        if kind == "text":
            parts.append(draw(st.text(min_size=0, max_size=40)))
        else:
            name = draw(variable_name)
            parts.append("{{" + name + "}}")
            var_names.append(name)

    template = "".join(parts)
    return template, var_names


# Variables dict: maps variable names to string values
variables_dict = st.dictionaries(
    keys=variable_name,
    values=st.text(min_size=0, max_size=100),
    max_size=15,
)


# ---------------------------------------------------------------------------
# Tests: extract_variables — no-crash property
# ---------------------------------------------------------------------------


class TestExtractVariablesNoCrash:
    @given(st.text())
    @settings(max_examples=200, deadline=None)
    def test_extract_variables_never_crashes(self, template: str) -> None:
        """extract_variables handles any string without raising."""
        result = extract_variables(template)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, VariableInfo)
            assert isinstance(item.name, str)
            assert item.required is True  # currently always True


# ---------------------------------------------------------------------------
# Tests: extract_variables — structural properties
# ---------------------------------------------------------------------------


class TestExtractVariablesStructural:
    @given(st.text())
    @settings(max_examples=200, deadline=None)
    def test_variable_names_are_unique(self, template: str) -> None:
        """extract_variables never returns duplicate names."""
        result = extract_variables(template)
        names = [v.name for v in result]
        assert len(names) == len(set(names))

    @given(template_with_vars())
    @settings(max_examples=200, deadline=None)
    def test_all_embedded_variables_found(self, data: tuple[str, list[str]]) -> None:
        """All {{var}} placeholders in the template are found."""
        template, embedded = data
        result = extract_variables(template)
        found_names = {v.name for v in result}
        for name in embedded:
            assert name in found_names


# ---------------------------------------------------------------------------
# Tests: substitute — identity property
# ---------------------------------------------------------------------------


class TestSubstituteIdentity:
    @given(plain_text)
    @settings(max_examples=200, deadline=None)
    def test_no_variables_returns_same_string(self, template: str) -> None:
        """Template with no {{var}} placeholders is returned unchanged."""
        # Ensure template has no {{...}} patterns
        assume_no_vars = re.sub(r"\{\{\w+\}\}", "", template)
        result = substitute(assume_no_vars, {}, strict=True)
        assert result == assume_no_vars

    @given(plain_text)
    @settings(max_examples=200, deadline=None)
    def test_empty_variables_dict_preserves_template_without_vars(self, template: str) -> None:
        """Empty variables dict with no-var template returns same template."""
        assume_no_vars = re.sub(r"\{\{\w+\}\}", "", template)
        result = substitute(assume_no_vars, {})
        assert result == assume_no_vars


# ---------------------------------------------------------------------------
# Tests: substitute — substitution property
# ---------------------------------------------------------------------------


class TestSubstituteSubstitution:
    @given(template_with_vars(), variables_dict)
    @settings(max_examples=200, deadline=None)
    def test_provided_values_appear_in_output(
        self, data: tuple[str, list[str]], variables: dict[str, str]
    ) -> None:
        """When a variable placeholder is provided, its value appears in the output."""
        template, _ = data
        # Use non-strict mode to avoid PromptVariableError
        result = substitute(template, variables, strict=False)
        for name, value in variables.items():
            placeholder = "{{" + name + "}}"
            if placeholder in template:
                assert value in result, f"Value for {name!r} not found in output"

    @given(variable_name, st.text(min_size=0, max_size=100))
    @settings(max_examples=200, deadline=None)
    def test_single_variable_substitution(self, name: str, value: str) -> None:
        """A template with a single {{var}} is fully replaced."""
        template = "Hello {{name}}, welcome!"
        result = substitute(template, {"name": value})
        assert result == f"Hello {value}, welcome!"


# ---------------------------------------------------------------------------
# Tests: substitute — no-crash property (non-strict)
# ---------------------------------------------------------------------------


class TestSubstituteNoCrash:
    @given(st.text(), variables_dict)
    @settings(max_examples=200, deadline=None)
    def test_non_strict_never_crashes(self, template: str, variables: dict[str, str]) -> None:
        """substitute with strict=False handles any template+variables without raising."""
        result = substitute(template, variables, strict=False)
        assert isinstance(result, str)

    @given(
        st.text(),
        st.dictionaries(keys=variable_name, values=st.text(min_size=1, max_size=50), max_size=5),
    )
    @settings(max_examples=200, deadline=None)
    def test_strict_only_raises_on_missing(self, template: str, variables: dict[str, str]) -> None:
        """substitute with strict=True either succeeds or raises PromptVariableError."""
        try:
            result = substitute(template, variables, strict=True)
            assert isinstance(result, str)
        except PromptVariableError:
            pass  # Expected when a variable is missing


# ---------------------------------------------------------------------------
# Tests: substitute — placeholder preservation (non-strict)
# ---------------------------------------------------------------------------


class TestSubstitutePlaceholderPreservation:
    @given(
        st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=("_")),
        )
    )
    @settings(max_examples=200, deadline=None)
    def test_missing_var_keeps_placeholder(self, name: str) -> None:
        """In non-strict mode, missing variables keep their {{name}} placeholder."""
        template = "Hello {{name}}!"
        result = substitute(template, {}, strict=False)
        assert result == "Hello {{name}}!"

    @given(variable_name, st.text(min_size=1, max_size=100))
    @settings(max_examples=200, deadline=None)
    def test_provided_var_replaces_placeholder(self, name: str, value: str) -> None:
        """A provided variable fully replaces its {{name}} placeholder."""
        template = "prefix {{" + name + "}} suffix"
        result = substitute(template, {name: value}, strict=False)
        assert "{{" + name + "}}" not in result
        assert value in result


# ---------------------------------------------------------------------------
# Tests: validate_variables — consistency with extract_variables
# ---------------------------------------------------------------------------


class TestValidateVariablesConsistency:
    @given(st.text(), variables_dict)
    @settings(max_examples=200, deadline=None)
    def test_missing_vars_are_subset_of_extracted(
        self, template: str, variables: dict[str, str]
    ) -> None:
        """validate_variables returns a subset of variables found by extract_variables."""
        extracted = {v.name for v in extract_variables(template)}
        missing = validate_variables(template, variables)
        assert set(missing).issubset(extracted)

    @given(st.text(), variables_dict)
    @settings(max_examples=200, deadline=None)
    def test_no_missing_when_all_provided(self, template: str, variables: dict[str, str]) -> None:
        """When variables dict includes all extracted vars, validate returns empty."""
        # Build a variables dict that includes all extracted variables
        extracted = extract_variables(template)
        full_vars = dict(variables)
        for v in extracted:
            if v.name not in full_vars:
                full_vars[v.name] = "filled"
        missing = validate_variables(template, full_vars)
        assert missing == []

    @given(st.text())
    @settings(max_examples=200, deadline=None)
    def test_empty_vars_returns_all_extracted(self, template: str) -> None:
        """With empty variables dict, all extracted vars are reported missing."""
        extracted = {v.name for v in extract_variables(template)}
        missing = validate_variables(template, {})
        assert set(missing) == extracted
