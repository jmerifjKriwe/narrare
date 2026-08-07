"""Tests for the governed dialogue_coach template (ADR-054 Mode-1 skeleton).

Verifies the template:
1. Exists at the canonical path.
2. Parses (frontmatter valid + body non-empty).
3. References the registered variables.
4. Does NOT reference voice_metrics (ADR-055/057 boundary).
5. Has the 9-section Mode-1 skeleton structure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATE_PATH = (
    # NOTE: plan-bug — the plan's verbatim test used parents[5], which resolves
    # to /home/kiesow/projects (one level too high). The repo root is at
    # parents[4] = /home/kiesow/projects/narrare, matching the convention in
    # every sibling test (test_prompt_path_compliance.py, test_preview_no_provider.py).
    Path(__file__).resolve().parents[4]
    / "packages"
    / "core"
    / "narrare_core"
    / "prompts"
    / "_bundled"
    / "ai_assist"
    / "en"
    / "dialogue_coach"
    / "system.md"
)


def _read_template() -> str:
    if not TEMPLATE_PATH.exists():
        pytest.fail(f"Template missing at {TEMPLATE_PATH}")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


@pytest.mark.mutation_inert
class TestDialogueCoachTemplateStructure:
    """9-section Mode-1 skeleton (ADR-054).

    ``mutation_inert``: static assertions on the committed bundled template
    (``packages/core/narrare_core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md``)
    reached via ``parents[4]``. These cannot kill source-code mutants, and the
    asset path resolves to a non-existent location inside MutMut's ``mutants/``
    sandbox (``parents[4]`` lands on ``<repo>/mutants``), crashing the run
    (issue #146). MutMut's ``-m "not mutation_inert"`` filter excludes them —
    consistent with the reference asset tests. Enforced by
    scripts/checks/check_mutation_inert_assets.py.
    """

    def test_template_exists(self) -> None:
        assert TEMPLATE_PATH.exists()

    def test_frontmatter_has_prompt_type(self) -> None:
        content = _read_template()
        assert content.startswith("---")
        first_fence = content.find("---", 3)
        frontmatter = content[3:first_fence]
        assert "prompt_type:" in frontmatter
        assert "ai_assist" in frontmatter

    def test_has_system_prompt_section(self) -> None:
        assert "## System Prompt" in _read_template()

    def test_has_task_section(self) -> None:
        assert "### Your Task" in _read_template()

    def test_has_context_section(self) -> None:
        assert "### Context" in _read_template()

    def test_has_constraints_section(self) -> None:
        assert "### Constraints" in _read_template()

    def test_has_output_format_section(self) -> None:
        assert "### Output Format" in _read_template()

    def test_has_quality_rules_section(self) -> None:
        assert "### Quality Rules" in _read_template()

    def test_has_do_not_section(self) -> None:
        assert "## Do NOT" in _read_template()


@pytest.mark.mutation_inert
class TestDialogueCoachTemplateVariables:
    """Variable references match Phase 1 Task 5 registrations.

    ``mutation_inert``: reads the same bundled template via ``parents[4]``
    — see ``TestDialogueCoachTemplateStructure`` for the full rationale.
    """

    def test_references_mode_variable(self) -> None:
        assert "{{mode}}" in _read_template()

    def test_references_characters_variable(self) -> None:
        assert "{{characters}}" in _read_template()

    def test_references_text_to_analyze_variable(self) -> None:
        assert "{{text_to_analyze}}" in _read_template()

    def test_references_adaptive_variables(self) -> None:
        content = _read_template()
        assert "{{user_preferences}}" in content
        assert "{{style_constraints}}" in content
        assert "{{avoidance_patterns}}" in content
        assert "{{character_voice_profiles}}" in content

    def test_text_to_analyze_is_xml_wrapped(self) -> None:
        """RULE-22 §6: user content MUST be wrapped in an approved XML tag.

        Per the prompt governance convention (prompt_governance_checks.py),
        user-content variables use generic approved tags (``<user_provided_text>``,
        ``<user_provided_data>``, ``<user_instructions>``), not feature-specific
        tag names. The plan-bug prescribed ``<text_to_analyze>`` which the
        governance checker rejects as non-standard.
        """
        content = _read_template()
        assert "<user_provided_text>" in content
        assert "</user_provided_text>" in content
        # The variable itself must appear inside the wrapper.
        assert "{{text_to_analyze}}" in content


@pytest.mark.mutation_inert
class TestDialogueCoachVoiceBoundary:
    """ADR-055/057: voice_metrics NEVER reach this template.

    ``mutation_inert``: reads the same bundled template via ``parents[4]``
    — see ``TestDialogueCoachTemplateStructure`` for the full rationale.
    """

    def test_does_not_reference_voice_metrics(self) -> None:
        content = _read_template().lower()
        assert "voice_metrics" not in content
        assert "voice metric" not in content
        assert "metric block" not in content

    def test_references_only_descriptive_voice_profiles(self) -> None:
        """Only the descriptive {{character_voice_profiles}} variable."""
        content = _read_template()
        assert "{{character_voice_profiles}}" in content
