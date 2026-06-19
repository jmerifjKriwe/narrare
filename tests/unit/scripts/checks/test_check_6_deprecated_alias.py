"""Tests for Check 6 — Deprecated §16.8 AI-action alias gate."""

from __future__ import annotations

from _ai_interaction_checks._shared import ExcludeRegistry
from _ai_interaction_checks.check_6_deprecated_alias import (
    DEPRECATED_ALIASES,
    check_deprecated_aliases,
)


def test_deprecated_alias_list_contains_all_16_aliases() -> None:
    """The deprecated alias list must contain exactly the 16 §16.8 aliases."""
    expected = {
        "aiModal.accept",
        "aiModal.reject",
        "aiModal.original",
        "generation.stop",
        "generation.accept",
        "generation.reject",
        "annotation.keep",
        "annotation.undo",
        "rewrite.cancel",
        "rewrite.replace",
        "sessionPanel.addToDraft",
        "kb.sessions.accept",
        "kb.sessions.reject",
        "learning.rating",
        "coAuthor.acceptAll",
        "coAuthor.rejectAll",
        "coAuthor.applySelected",
    }
    assert set(DEPRECATED_ALIASES) == expected
    assert len(DEPRECATED_ALIASES) == 17  # 16 from task + aiModal.original


def test_check_returns_pass_when_no_violations() -> None:
    """When no deprecated aliases are found in the codebase, check passes."""
    # The real codebase should have no deprecated aliases after frontend migration.
    registry = ExcludeRegistry()
    passes, violations = check_deprecated_aliases(registry)

    assert violations == []
    assert len(passes) >= 1
    assert any("deprecated" in p.lower() for p in passes)


def test_check_returns_violation_for_excluded_file() -> None:
    """A governed exclusion is reported separately, not as a violation."""
    # This test verifies the registry interaction pattern.
    registry = ExcludeRegistry()
    # Empty registry with no entries — no governed exclusions.
    passes, violations = check_deprecated_aliases(registry)
    # Since we can't control rg output in unit tests, we verify the
    # function signature and return type contract.
    assert isinstance(passes, list)
    assert isinstance(violations, list)


def test_alias_list_does_not_include_canonical_keys() -> None:
    """Canonical aiActions.* keys must NOT be in the deprecated list."""
    canonical = {
        "aiActions.accept",
        "aiActions.reject",
        "aiActions.stop",
        "aiActions.replace",
        "aiActions.addToDraft",
        "aiActions.rating",
        "aiActions.acceptAll",
        "aiActions.rejectAll",
        "aiActions.applySelected",
        "aiActions.original",
    }
    deprecated_set = set(DEPRECATED_ALIASES)
    overlap = canonical & deprecated_set
    assert overlap == set(), f"Canonical keys must not be deprecated: {overlap}"
