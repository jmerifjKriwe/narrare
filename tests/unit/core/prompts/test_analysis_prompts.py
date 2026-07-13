"""Tests for bundled analysis prompt governance."""

from __future__ import annotations

import re

from tests.unit.core._bundled import bundled_prompts_root

_BUNDLED_ROOT = bundled_prompts_root()


def _consistency_prompt() -> str:
    return (_BUNDLED_ROOT / "analysis" / "en" / "consistency" / "system.md").read_text()


def test_consistency_prompt_contains_false_positive_controls() -> None:
    """Consistency prompt must reduce CR-01 false positives without schema drift."""
    content = _consistency_prompt()
    lowered = content.lower()

    assert "false positive" in lowered
    assert "do not flag" in lowered
    assert "unreliable narration" in lowered
    assert "intentional ambiguity" in lowered


# --- FIND-001 / CR-AUFG-03-01: relationship-aware consistency checking ---


class TestConsistencyPromptRelationships:
    """The consistency prompt must surface and instruct on relationship checking.

    FIND-001: ConsistencyDeps gained a ``kb_relationships`` field so the agent
    can cross-reference the KB relationship graph against chapter events. The
    bundled template must (a) expose the variable, (b) broaden the ``world``
    check type to include character relationships, and (c) instruct the model
    to cross-reference relationships.
    """

    def test_exposes_kb_relationships_variable(self) -> None:
        """Template must surface {{kb_relationships}} in the input context."""
        content = _consistency_prompt()
        assert "{{kb_relationships}}" in content

    def test_world_check_type_mentions_relationships(self) -> None:
        """The 'world' check type must include character relationships."""
        content = _consistency_prompt()
        # The world bullet must reference relationships (broadened from
        # "faction relationships" to "faction/character relationships").
        assert re.search(r"\*\*world\*\*.*faction/character relationships", content)

    def test_includes_relationship_cross_reference_instruction(self) -> None:
        """Task section must instruct cross-referencing KB relationships vs events.

        Asserts on the phrase unique to the new instruction (``relationship
        graph``), which is absent from the pre-2.1.0 template.
        """
        content = _consistency_prompt()
        lowered = content.lower()
        assert "cross-reference" in lowered
        assert "relationship graph" in lowered
        assert "allies, enemies, family" in lowered

    def test_prompt_version_bumped_to_minor_feature(self) -> None:
        """Version must be bumped to 2.1.0 (minor feature: relationship awareness)."""
        content = _consistency_prompt()
        match = re.search(r'prompt_version:\s*"([^"]+)"', content)
        assert match is not None, "prompt_version frontmatter missing"
        assert match.group(1) == "2.1.0"
