"""Tests for writing/style_variants.py — style variant taxonomy (CR-AUFG-07-22).

Covers:
1. StyleVariant enum has exactly the 6 approved values
2. Each variant maps (via the public helper) to a non-empty instruction string
3. get_style_variant_instructions returns distinct, keyword-bearing text per variant
4. get_style_variant_instructions(None) returns empty string (backward compat)
5. StyleVariant serialises to its string value (StrEnum)
6. The rewrite_selection template declares the ``{{style_variant_instructions}}``
   injection point (governance — RULE-02/02a/02b: variant direction is a Cascade
   variable, not an inline f-string).

The instruction dict is module-private (``_STYLE_VARIANT_INSTRUCTIONS``) by
convention, matching ``_REWRITE_MODE_INSTRUCTIONS`` in ``pipeline_rewrite.py``.
These tests exercise the public ``get_style_variant_instructions`` helper and
the enum so they do not depend on the private dict's export surface.
"""

from __future__ import annotations

import pytest

from narrare_core.writing.style_variants import (
    StyleVariant,
    get_style_variant_instructions,
)
from tests.unit.core._bundled import bundled_prompts_root

_REWRITE_TEMPLATE = bundled_prompts_root() / "writing" / "en" / "rewrite_selection" / "system.md"


class TestStyleVariantEnum:
    def test_has_exactly_six_members(self) -> None:
        members = list(StyleVariant)
        assert len(members) == 6

    def test_member_values(self) -> None:
        assert StyleVariant.LEANER.value == "leaner"
        assert StyleVariant.MORE_LYRICAL.value == "more_lyrical"
        assert StyleVariant.MORE_TENSE.value == "more_tense"
        assert StyleVariant.MORE_INTIMATE.value == "more_intimate"
        assert StyleVariant.MORE_DIALOGUE.value == "more_dialogue"
        assert StyleVariant.MORE_SENSORY.value == "more_sensory"

    def test_strenum_serialises_to_value(self) -> None:
        assert str(StyleVariant.LEANER) == "leaner"
        assert StyleVariant.MORE_LYRICAL == "more_lyrical"


class TestStyleVariantInstructions:
    def test_every_variant_has_nonempty_instruction(self) -> None:
        for variant in StyleVariant:
            instruction = get_style_variant_instructions(variant)
            assert instruction.strip() != "", f"Variant {variant} has empty instruction"

    def test_instructions_are_distinct(self) -> None:
        instructions = {get_style_variant_instructions(v) for v in StyleVariant}
        assert len(instructions) == len(list(StyleVariant))

    @pytest.mark.parametrize(
        ("variant", "keyword"),
        [
            (StyleVariant.LEANER, "leaner"),
            (StyleVariant.MORE_LYRICAL, "lyrical"),
            (StyleVariant.MORE_TENSE, "tense"),
            (StyleVariant.MORE_INTIMATE, "intimate"),
            (StyleVariant.MORE_DIALOGUE, "dialogue"),
            (StyleVariant.MORE_SENSORY, "sensory"),
        ],
    )
    def test_instruction_contains_keyword(self, variant: StyleVariant, keyword: str) -> None:
        assert keyword in get_style_variant_instructions(variant).lower()

    def test_none_returns_empty(self) -> None:
        assert get_style_variant_instructions(None) == ""

    def test_default_fallback_is_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default must return "" — downstream code does string operations
        (concatenation, template rendering). None or other values would break.

        This kills the 3 MutMut surviving mutants that change the .get() default.
        """
        monkeypatch.setattr(
            "narrare_core.writing.style_variants._STYLE_VARIANT_INSTRUCTIONS",
            {},
        )
        result = get_style_variant_instructions(StyleVariant.LEANER)
        assert result == ""


class TestTemplateVariable:
    def test_template_contains_style_variant_variable(self) -> None:
        """The rewrite_selection template must declare the injection point."""
        content = _REWRITE_TEMPLATE.read_text(encoding="utf-8")
        assert "{{style_variant_instructions}}" in content
