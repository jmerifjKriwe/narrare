"""Regression test: injection defense lives only in NarrareUniversalRules.

CR-AUFG-02-08: The XML-tagged content injection defense was duplicated in both
NarrareMeta (``meta/{en,de,fr}/system.md``) and NarrareUniversalRules
(``universal/{en,de,fr}/system.md``). It is now the sole responsibility of
NarrareUniversalRules (ADR-026).

This test verifies:
- Meta prompts (all 3 locales) do NOT contain the injection defense marker.
- Universal Rules prompts (all 3 locales) DO contain the injection defense marker.
- Meta prompt version is ``"3.1.0"`` (bumped after defense removal).
- Universal Rules prompt version is ``"1.0.0"`` (unchanged).

The injection defense is identified by the presence of the XML tag
``<user_provided_text>``. This marker is locale-agnostic (the tags are
identical in EN, DE, and FR) and appears only in the defense instruction.
Checking for the English phrase "XML-tagged" would be vacuously true for
DE (``XML-getaggte``) and FR (``balisé XML``) even before the fix.
"""

from __future__ import annotations

import pytest

from narrare_core.agents.capabilities.meta import _load_meta_prompt
from narrare_core.agents.capabilities.universal_rules import (
    _find_bundled_root,
    _load_universal_rules,
)
from narrare_core.shared.frontmatter import parse_frontmatter

_LOCALES = ("en", "de", "fr")

# The XML tag used in the injection defense instruction. Locale-agnostic —
# appears only in the defense line. If absent from Meta and present in
# Universal, the defense has been correctly consolidated.
_INJECTION_DEFENSE_MARKER = "<user_provided_text>"


class TestInjectionDefenseSeparation:
    """Verify injection defense appears only in Universal Rules, not Meta."""

    @pytest.mark.parametrize("locale", _LOCALES)
    def test_meta_prompt_does_not_contain_injection_defense(self, locale: str) -> None:
        """Meta prompts must NOT contain the XML injection defense.

        The defense is the sole responsibility of NarrareUniversalRules
        (ADR-026). Its presence in Meta is a duplicate that causes
        ~30 token overhead and drift risk.
        """
        meta = _load_meta_prompt(locale)
        assert meta, f"Meta prompt for {locale} should not be empty"
        assert _INJECTION_DEFENSE_MARKER not in meta, (
            f"Meta prompt ({locale}) must not contain injection defense — "
            "that is the sole responsibility of NarrareUniversalRules"
        )

    @pytest.mark.parametrize("locale", _LOCALES)
    def test_universal_rules_contain_injection_defense(self, locale: str) -> None:
        """Universal Rules must contain the XML injection defense."""
        rules = _load_universal_rules(locale)
        assert rules, f"Universal rules for {locale} should not be empty"
        assert _INJECTION_DEFENSE_MARKER in rules, (
            f"Universal rules ({locale}) must contain injection defense"
        )

    @pytest.mark.parametrize("locale", _LOCALES)
    def test_meta_prompt_version_bumped(self, locale: str) -> None:
        """Meta prompt version is 3.1.0 after injection defense removal."""
        root = _find_bundled_root()
        raw = (root / "meta" / locale / "system.md").read_text(encoding="utf-8")
        parsed = parse_frontmatter(raw)
        version = parsed.metadata.get("prompt_version")
        assert version == "3.1.0", (
            f"Meta prompt ({locale}) version should be '3.1.0', got {version!r}"
        )

    @pytest.mark.parametrize("locale", _LOCALES)
    def test_universal_rules_version_unchanged(self, locale: str) -> None:
        """Universal Rules version is 1.0.0 (unchanged)."""
        root = _find_bundled_root()
        raw = (root / "universal" / locale / "system.md").read_text(encoding="utf-8")
        parsed = parse_frontmatter(raw)
        version = parsed.metadata.get("prompt_version")
        assert version == "1.0.0", (
            f"Universal rules ({locale}) version should be '1.0.0', got {version!r}"
        )
