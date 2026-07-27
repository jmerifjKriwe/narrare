"""Tests for ADR-046 D.5 — prompt-path compliance adoption metric.

Validates that ``check_prompt_path_adoption`` correctly detects:
- modes missing from ``prompt_path_compliance``,
- modes declared ``false``,
- non-boolean declarations,
- and drift (entries with no matching feature mode).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from adoption.prompt_path_adoption import check_prompt_path_adoption  # noqa: E402


def _registry(
    features: dict[str, object],
    compliance: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a minimal registry with the given features and compliance map."""
    reg: dict[str, object] = {"features": features}
    if compliance is not None:
        reg["prompt_path_compliance"] = compliance
    return reg


# =====================================================================
# All compliant
# =====================================================================


class TestAllCompliant:
    def test_no_findings_when_all_true(self) -> None:
        registry = _registry(
            features={"writing": {"modes": {"new_chapter": {}}}},
            compliance={"writing/new_chapter": True},
        )
        assert check_prompt_path_adoption(registry) == []

    def test_empty_features_no_findings(self) -> None:
        registry = _registry(features={}, compliance={})
        assert check_prompt_path_adoption(registry) == []

    def test_modeless_category_skipped(self) -> None:
        # chat uses modes: [] (modeless) — no compliance entries needed.
        registry = _registry(
            features={"chat": {"modes": []}},
            compliance={},
        )
        assert check_prompt_path_adoption(registry) == []


# =====================================================================
# Missing / false / invalid declarations
# =====================================================================


class TestMissingDeclaration:
    def test_missing_mode_is_critical(self) -> None:
        registry = _registry(
            features={"writing": {"modes": {"new_chapter": {}, "extend_chapter": {}}}},
            compliance={"writing/new_chapter": True},
        )
        findings = check_prompt_path_adoption(registry)
        assert len(findings) == 1
        assert findings[0].mode_key == "writing/extend_chapter"
        assert findings[0].severity == "critical"
        assert "missing" in findings[0].message

    def test_no_compliance_section_all_critical(self) -> None:
        registry = _registry(
            features={"planning": {"modes": {"outline": {}}}},
        )
        findings = check_prompt_path_adoption(registry)
        assert len(findings) == 1
        assert findings[0].severity == "critical"


class TestFalseDeclaration:
    def test_false_is_critical(self) -> None:
        registry = _registry(
            features={"kb": {"modes": {"improve": {}}}},
            compliance={"kb/improve": False},
        )
        findings = check_prompt_path_adoption(registry)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "false" in findings[0].message


class TestInvalidDeclaration:
    def test_non_boolean_is_critical(self) -> None:
        registry = _registry(
            features={"generation": {"modes": {"names": {}}}},
            compliance={"generation/names": "yes"},
        )
        findings = check_prompt_path_adoption(registry)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "boolean" in findings[0].message


# =====================================================================
# Drift detection
# =====================================================================


class TestDrift:
    def test_extra_entry_is_warning(self) -> None:
        registry = _registry(
            features={"analysis": {"modes": {"review": {}}}},
            compliance={
                "analysis/review": True,
                "writing/deleted_mode": True,  # no matching feature mode
            },
        )
        findings = check_prompt_path_adoption(registry)
        assert len(findings) == 1
        assert findings[0].mode_key == "writing/deleted_mode"
        assert findings[0].severity == "warning"


# =====================================================================
# Real registry sanity check
# =====================================================================


class TestRealRegistry:
    """The shipped adoption-registry.yaml must be fully compliant."""

    def test_real_registry_has_no_findings(self) -> None:
        import yaml

        registry_path = Path(_ROOT) / "scripts" / "architecture" / "adoption-registry.yaml"
        with registry_path.open("r", encoding="utf-8") as fh:
            registry = yaml.safe_load(fh)

        findings = check_prompt_path_adoption(registry)
        assert findings == [], (
            "adoption-registry.yaml has prompt-path-compliance findings: "
            + "; ".join(f"{f.mode_key}: {f.message}" for f in findings)
        )

    def test_real_registry_covers_all_feature_modes(self) -> None:
        import yaml

        registry_path = Path(_ROOT) / "scripts" / "architecture" / "adoption-registry.yaml"
        with registry_path.open("r", encoding="utf-8") as fh:
            registry = yaml.safe_load(fh)

        features = registry.get("features", {})
        mode_count = sum(
            len(cfg.get("modes", {}))
            for cfg in features.values()
            if isinstance(cfg.get("modes"), dict)
        )
        # Ratchet: the registry must cover all implemented feature modes.
        # When adding a mode, update this count. As of the CR-02 prompt-path
        # retrofit (ADR-046) the registry covered 29 modes (analysis gained
        # fact_extraction; planning gained temporal_consistency). ADR-055 D4
        # added analysis/character_voice (ANAL-008) → 30 modes. ADR-057 D3
        # added analysis/voice_check (WRITE-010) → 31 modes.
        # Eight further additions brought the total to 39: analysis/coreference
        # (ANAL-005), analysis/pov, analysis/readability, kb/merge,
        # planning/character_arc, planning/timeline, planning/timeline_extraction
        # (ADR-054), and ai_assist/dialogue_coach (ADR-069).
        # ADR-073 D3 added analysis/voice_drift (ANAL-009 Phase 1) → 40 modes.
        # ADR-074 / ANAL-007 added analysis/author_voice (the 4th VOICE mode) → 41 modes.
        assert mode_count == 41, f"expected 41 feature modes, got {mode_count}"
