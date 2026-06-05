"""Tests for bundled analysis prompt governance."""

from __future__ import annotations

from pathlib import Path

_BUNDLED_ROOT = Path(__file__).parents[4] / "packages/core/narrare_core/prompts/_bundled"


def test_consistency_prompt_contains_false_positive_controls() -> None:
    """Consistency prompt must reduce CR-01 false positives without schema drift."""
    content = (_BUNDLED_ROOT / "analysis" / "en" / "consistency" / "system.md").read_text()
    lowered = content.lower()

    assert "false positive" in lowered
    assert "do not flag" in lowered
    assert "unreliable narration" in lowered
    assert "intentional ambiguity" in lowered
