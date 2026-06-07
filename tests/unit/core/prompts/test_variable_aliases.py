"""Tests for CR-AUFG-04-03: Variable naming canonical aliases.

Covers:
1. resolve_canonical_variable() with canonical names (identity)
2. resolve_canonical_variable() with aliased names (resolves to canonical)
3. VARIABLE_ALIASES values all exist in the main registries
"""

from __future__ import annotations

from narrare_core.prompts.variable_registry import (
    FEATURE_DYNAMIC_VARS,
    SYSTEM_VARS,
    VARIABLE_ALIASES,
    VARIABLE_CLASSIFICATIONS,
    resolve_canonical_variable,
)


class TestResolveCanonicalVariableIdentity:
    """Canonical names are returned unchanged."""

    def test_writing_language_identity(self) -> None:
        assert resolve_canonical_variable("writing_language") == "writing_language"

    def test_explanation_language_identity(self) -> None:
        assert resolve_canonical_variable("explanation_language") == "explanation_language"

    def test_genre_identity(self) -> None:
        assert resolve_canonical_variable("genre") == "genre"

    def test_mode_identity(self) -> None:
        assert resolve_canonical_variable("mode") == "mode"


class TestResolveCanonicalVariableAliases:
    """Deprecated/aliased names resolve to their canonical form."""

    def test_language_resolves_to_writing_language(self) -> None:
        assert resolve_canonical_variable("language") == "writing_language"


class TestResolveCanonicalVariableUnknown:
    """Unknown variable names are returned unchanged."""

    def test_unknown_name_returned_as_is(self) -> None:
        assert resolve_canonical_variable("totally_unknown_var") == "totally_unknown_var"

    def test_empty_string_returned_as_is(self) -> None:
        assert resolve_canonical_variable("") == ""


class TestVariableAliasesValuesRegistered:
    """All VARIABLE_ALIASES target values must exist in the main registries."""

    def test_alias_targets_exist_in_registries(self) -> None:
        """Every alias target is a registered variable."""
        all_registered = VARIABLE_CLASSIFICATIONS.keys()
        for alias_name, canonical_name in VARIABLE_ALIASES.items():
            assert canonical_name in all_registered, (
                f"Alias '{alias_name}' maps to '{canonical_name}' "
                f"which is not in any variable registry"
            )

    def test_alias_sources_exist_in_registries(self) -> None:
        """Deprecated alias names also remain in the registries for compat."""
        all_registered = VARIABLE_CLASSIFICATIONS.keys()
        for alias_name in VARIABLE_ALIASES:
            assert alias_name in all_registered, (
                f"Deprecated alias '{alias_name}' is not in any variable registry. "
                f"It must remain registered for backward compatibility."
            )

    def test_no_self_aliases(self) -> None:
        """No alias should map a name to itself."""
        for alias_name, canonical_name in VARIABLE_ALIASES.items():
            assert alias_name != canonical_name, (
                f"Self-alias detected: '{alias_name}' -> '{canonical_name}'"
            )

    def test_writing_language_is_system_var(self) -> None:
        """The canonical 'writing_language' is in SYSTEM_VARS."""
        assert "writing_language" in SYSTEM_VARS

    def test_explanation_language_is_feature_dynamic(self) -> None:
        """'explanation_language' is in FEATURE_DYNAMIC_VARS (not aliased)."""
        assert "explanation_language" in FEATURE_DYNAMIC_VARS
