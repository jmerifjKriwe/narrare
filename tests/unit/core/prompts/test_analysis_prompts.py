"""Tests for bundled analysis prompt governance."""

from __future__ import annotations

from tests.unit.core._bundled import bundled_prompts_root

_BUNDLED_ROOT = bundled_prompts_root()


def test_consistency_prompt_contains_false_positive_controls() -> None:
    """Consistency prompt must reduce CR-01 false positives without schema drift."""
    content = (_BUNDLED_ROOT / "analysis" / "en" / "consistency" / "system.md").read_text()
    lowered = content.lower()

    assert "false positive" in lowered
    assert "do not flag" in lowered
    assert "unreliable narration" in lowered
    assert "intentional ambiguity" in lowered
