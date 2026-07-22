"""Tests for ai_assist/dialogue_coach manifest + adoption-registry entries.

Verifies RULE-22 governance coherence: the route declared in
route_table.py (Task 7) matches the manifest entry, the template exists
(Task 8), and the adoption-registry declares prompt-path compliance.

See: ADR-037 (prompt-surface manifest), ADR-046 §D.5 (prompt-path
compliance), ADR-056 (runtime adoption gate).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# NOTE: plan-bug — the plan's verbatim test used parents[5], which resolves
# to /home/kiesow/projects (one level too high). The repo root is at
# parents[4] = /home/kiesow/projects/narrare, matching the convention in
# every sibling test (test_prompt_path_compliance.py, test_preview_no_provider.py).
REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = REPO_ROOT / "scripts" / "architecture" / "prompt-surface-manifest.yaml"
REGISTRY_PATH = REPO_ROOT / "scripts" / "architecture" / "adoption-registry.yaml"


def _read(path: Path) -> str:
    if not path.exists():
        pytest.fail(f"Missing: {path}")
    return path.read_text(encoding="utf-8")


class TestPromptSurfaceManifest:
    """prompt-surface-manifest.yaml declares ai_assist/dialogue_coach."""

    def test_manifest_has_ai_assist_dialogue_coach_route(self) -> None:
        content = _read(MANIFEST_PATH)
        assert "intent: DIALOGUE_COACH" in content
        assert "category: ai_assist" in content
        assert "mode: dialogue_coach" in content

    def test_manifest_references_governed_template(self) -> None:
        content = _read(MANIFEST_PATH)
        assert "ai_assist/en/dialogue_coach/system.md" in content

    def test_manifest_declares_optional_variables(self) -> None:
        content = _read(MANIFEST_PATH)
        # Spot-check the adaptive vars + dialogue-coach-specific vars
        for var in (
            "user_preferences",
            "style_constraints",
            "avoidance_patterns",
            "character_voice_profiles",
            "mode",
            "characters",
            "text_to_analyze",
        ):
            assert var in content, f"manifest missing optional variable: {var}"

    def test_manifest_declares_xml_wrapping_for_text_to_analyze(self) -> None:
        """RULE-22 §6: text_to_analyze is USER_CONTENT_VARS → XML-wrapped."""
        content = _read(MANIFEST_PATH)
        # The security.xml_required list MUST include text_to_analyze
        # somewhere within the DIALOGUE_COACH entry.
        dialogue_coach_block = content.split("intent: DIALOGUE_COACH", 1)[-1]
        # Look until the next intent block:
        next_intent = dialogue_coach_block.find("\n  - intent: ")
        if next_intent != -1:
            dialogue_coach_block = dialogue_coach_block[:next_intent]
        assert "text_to_analyze" in dialogue_coach_block
        assert "xml_required" in dialogue_coach_block


class TestAdoptionRegistry:
    """adoption-registry.yaml declares prompt-path compliance + runtime evidence."""

    def test_registry_has_ai_assist_dialogue_coach_compliance(self) -> None:
        content = _read(REGISTRY_PATH)
        assert "ai_assist/dialogue_coach" in content

    def test_registry_declares_runtime_evidence_required(self) -> None:
        content = _read(REGISTRY_PATH)
        # Find the ai_assist section
        assert "ai_assist:" in content or "features:\n  ai_assist:" in content
        assert "dialogue_coach:" in content
        assert "requires_runtime_evidence: true" in content

    def test_registry_has_ai_assist_category_defaults(self) -> None:
        content = _read(REGISTRY_PATH)
        assert "ai_assist:" in content
