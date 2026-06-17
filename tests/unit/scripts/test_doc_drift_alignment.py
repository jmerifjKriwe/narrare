"""Tests for scripts/doc_drift/ — spec/RULE-XX and terminology checks.

Validates spec/RULE-XX alignment and terminology checks using tmp_path
with mock files for isolation.

See: ADR-041 Decision 2.
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


from doc_drift.spec_checks import (  # noqa: E402
    _extract_rule_numbers,
    _extract_rule_refs_from_text,
    check_spec_references,
)
from doc_drift.terminology_checks import (  # noqa: E402
    _load_registry_categories,
    check_terminology_alignment,
)

# ── Spec/RULE-XX Checks ───────────────────────────────────────


def _make_constraints_file(tmp_path: Path, rules: list[str]) -> Path:
    """Create a mock CONSTRAINTS.md with RULE entries."""
    lines = ["# Constraints\n"]
    for rule in rules:
        lines.append(f"### RULE-{rule} · Some rule description\n")
    p = tmp_path / "CONSTRAINTS.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _make_spec_file(
    tmp_path: Path,
    filename: str,
    content: str,
) -> Path:
    """Create a mock spec file."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir(exist_ok=True)
    p = spec_dir / filename
    p.write_text(content, encoding="utf-8")
    return p


class TestExtractRuleNumbers:
    """Test RULE extraction from CONSTRAINTS.md."""

    def test_extracts_numbered_rules(self) -> None:
        content = "### RULE-01b · First\n### RULE-02 · Second\n### RULE-15 · Middleware\n"
        rules = _extract_rule_numbers(content)
        assert rules == {"01b", "02", "15"}

    def test_extracts_letter_suffix(self) -> None:
        content = "### RULE-01b · Variant\n### RULE-02a · Another\n"
        rules = _extract_rule_numbers(content)
        assert rules == {"01b", "02a"}


class TestSpecRULEValid:
    """RULE-XX with invalid number = warning."""

    def test_invalid_rule_number_warning(self, tmp_path: Path) -> None:
        constraints = _make_constraints_file(tmp_path, ["01b", "02", "03"])
        _make_spec_file(
            tmp_path,
            "test-spec.md",
            "This spec references RULE-99 and RULE-01b.\n",
        )
        spec_dir = tmp_path / "specs"

        findings = check_spec_references(
            specs_dir=spec_dir,
            constraints_path=constraints,
            adr_dir=tmp_path,
        )
        assert any(f.severity == "warning" and "RULE-99" in f.message for f in findings)

    def test_valid_rule_no_finding(self, tmp_path: Path) -> None:
        constraints = _make_constraints_file(tmp_path, ["01b", "02", "22"])
        _make_spec_file(
            tmp_path,
            "test-spec.md",
            "This spec references RULE-01b and RULE-22.\n",
        )
        spec_dir = tmp_path / "specs"

        findings = check_spec_references(
            specs_dir=spec_dir,
            constraints_path=constraints,
            adr_dir=tmp_path,
        )
        rule_findings = [f for f in findings if "does not exist in CONSTRAINTS" in f.message]
        assert len(rule_findings) == 0

    def test_legacy_rule_01_without_suffix_warns(self, tmp_path: Path) -> None:
        """Regression: after RULE-01 → RULE-01b migration, bare 'RULE-01' is invalid.

        The canonical identifier is RULE-01b. A spec referencing the legacy
        'RULE-01' (without the 'b' suffix) must produce a warning because
        RULE-01 no longer exists as a header in CONSTRAINTS.md.
        """
        constraints = _make_constraints_file(tmp_path, ["01b", "02", "22"])
        _make_spec_file(
            tmp_path,
            "test-spec.md",
            "This spec references RULE-01 and RULE-01b.\n",
        )
        spec_dir = tmp_path / "specs"

        findings = check_spec_references(
            specs_dir=spec_dir,
            constraints_path=constraints,
            adr_dir=tmp_path,
        )
        rule_findings = [f for f in findings if "does not exist in CONSTRAINTS" in f.message]
        # RULE-01 (legacy, without 'b') must warn; RULE-01b must not.
        assert any(
            "RULE-01 " in f.message or f.message.endswith("RULE-01 which does not exist")
            for f in rule_findings
        ), f"Expected warning for legacy RULE-01 reference, got: {rule_findings}"
        assert not any("RULE-01b" in f.message for f in rule_findings), (
            f"RULE-01b should be valid, but got warning: {rule_findings}"
        )


class TestSpecADRReferences:
    """Spec ADR references must point to existing files."""

    def test_broken_adr_reference_critical(self, tmp_path: Path) -> None:
        constraints = _make_constraints_file(tmp_path, ["01"])
        _make_spec_file(
            tmp_path,
            "test-spec.md",
            "See ADR-999 for details.\n",
        )
        spec_dir = tmp_path / "specs"

        findings = check_spec_references(
            specs_dir=spec_dir,
            constraints_path=constraints,
            adr_dir=tmp_path,
        )
        assert any(f.severity == "critical" and "ADR-999" in f.message for f in findings)

    def test_valid_adr_reference_ok(self, tmp_path: Path) -> None:
        constraints = _make_constraints_file(tmp_path, ["01"])
        (tmp_path / "001-some-decision.md").write_text("# ADR-001\n", encoding="utf-8")
        _make_spec_file(
            tmp_path,
            "test-spec.md",
            "See ADR-001 for details.\n",
        )
        spec_dir = tmp_path / "specs"

        findings = check_spec_references(
            specs_dir=spec_dir,
            constraints_path=constraints,
            adr_dir=tmp_path,
        )
        adr_findings = [
            f for f in findings if "ADR-001" in f.message and "does not exist" in f.message
        ]
        assert len(adr_findings) == 0


class TestSpecFilePathReferences:
    """File paths in specs must exist."""

    def test_broken_path_warning(self, tmp_path: Path) -> None:
        constraints = _make_constraints_file(tmp_path, ["01"])
        _make_spec_file(
            tmp_path,
            "test-spec.md",
            "See `nonexistent/path.py` for implementation.\n",
        )
        spec_dir = tmp_path / "specs"

        findings = check_spec_references(
            specs_dir=spec_dir,
            constraints_path=constraints,
            adr_dir=tmp_path,
        )
        assert any(f.severity == "warning" and "nonexistent/path.py" in f.message for f in findings)


class TestExtractRuleRefs:
    """Test RULE-XX extraction from arbitrary text."""

    def test_extracts_rules(self) -> None:
        text = "See RULE-01b and RULE-22 for details."
        assert _extract_rule_refs_from_text(text) == {"01b", "22"}

    def test_extracts_letter_suffix(self) -> None:
        text = "RULE-01b and RULE-02a are relevant."
        assert _extract_rule_refs_from_text(text) == {"01b", "02a"}

    def test_no_rules(self) -> None:
        assert _extract_rule_refs_from_text("no rules here") == set()


# ── Terminology Checks ────────────────────────────────────────


def _make_registry_yaml(tmp_path: Path, categories: dict[str, list[str]]) -> Path:
    """Create a minimal adoption-registry.yaml."""
    lines = ["version: '2.0.0'", "", "features:"]
    for cat, modes in sorted(categories.items()):
        lines.append(f"  {cat}:")
        lines.append("    modes:")
        for mode in modes:
            lines.append(f"      {mode}:")
            lines.append("        requires_runtime_evidence: true")
    p = tmp_path / "adoption-registry.yaml"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


class TestLoadRegistryCategories:
    """Test YAML category/mode parsing."""

    def test_parses_categories(self, tmp_path: Path) -> None:
        registry = _make_registry_yaml(
            tmp_path,
            {"writing": ["new_chapter", "extend_chapter"], "analysis": ["beta_reader"]},
        )
        cats = _load_registry_categories(registry)
        assert "writing" in cats
        assert "analysis" in cats
        assert "new_chapter" in cats["writing"]
        assert "beta_reader" in cats["analysis"]


class TestTerminologyMatch:
    """Checker uses correct terms."""

    def test_no_findings_with_valid_registry(self, tmp_path: Path) -> None:
        registry = _make_registry_yaml(
            tmp_path,
            {"writing": ["new_chapter"], "analysis": ["beta_reader"]},
        )
        findings = check_terminology_alignment(
            registry_path=registry,
            checker_scripts=[],
        )
        mode_findings = [f for f in findings if "duplicate mode" in f.message]
        assert len(mode_findings) == 0

    def test_duplicate_mode_critical(self, tmp_path: Path) -> None:
        content = (
            "version: '2.0.0'\n\nfeatures:\n"
            "  writing:\n    modes:\n"
            "      new_chapter:\n        requires_runtime_evidence: true\n"
            "      new_chapter:\n        requires_runtime_evidence: true\n"
        )
        p = tmp_path / "adoption-registry.yaml"
        p.write_text(content, encoding="utf-8")

        findings = check_terminology_alignment(
            registry_path=p,
            checker_scripts=[],
        )
        assert any(f.severity == "critical" and "duplicate mode" in f.message for f in findings)

    def test_audit_state_valid(self, tmp_path: Path) -> None:
        """Checker script using valid audit states produces no finding."""
        registry = _make_registry_yaml(tmp_path, {"writing": ["new_chapter"]})
        script = tmp_path / "fake_checker.py"
        script.write_text(
            'state = "identified"\nstate2 = "adopted"\n',
            encoding="utf-8",
        )

        findings = check_terminology_alignment(
            registry_path=registry,
            checker_scripts=[script],
        )
        invalid = [f for f in findings if "non-canonical" in f.message]
        assert len(invalid) == 0


# ── Integration: Real Repo Smoke Test ─────────────────────────


class TestRealRepoADRCheck:
    """Smoke test against the real repo ADR directory."""

    def test_adr_consistency_runs(self) -> None:
        """ADR consistency check completes without error on real repo."""
        from doc_drift.adr_checks import check_adr_consistency

        findings = check_adr_consistency()
        assert isinstance(findings, list)

    def test_spec_references_runs(self) -> None:
        """Spec references check completes without error on real repo."""
        findings = check_spec_references()
        assert isinstance(findings, list)

    def test_terminology_alignment_runs(self) -> None:
        """Terminology alignment check completes without error."""
        findings = check_terminology_alignment()
        assert isinstance(findings, list)
