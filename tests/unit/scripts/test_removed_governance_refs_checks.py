"""Unit tests for scripts/doc_drift/removed_governance_refs_checks.py.

The guard detects references to governance artifacts that were removed in the
``f8abb42c`` teardown (Configuration Adoption Matrix, ``check_configuration_matrix.py``,
``scripts/governance/``, the retired ``just check-configuration-matrix`` target, …)
but left dangling in docs. It is WARNING-ONLY with a ratcheted file-level
allowlist: the current post-cleanup state starts clean (zero new warnings), and
any reference to a removed artifact in a file that is NOT in the baseline
allowlist surfaces a warning for reviewer triage.

Allowlisted files are legitimate historical references (ADRs, implementation
plans, audit/review findings, and curated standards that annotate the removal).

Note: loads the module dynamically like the other ``scripts/doc_drift`` tests
(``test_lookup_drift_checks.py`` …); tests are excluded from pyright's CI
``include`` (see pyproject.toml ``[tool.pyright]``).
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def _load_module():
    """Load removed_governance_refs_checks via the doc_drift import path."""
    sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        # Force a fresh import so REPO_ROOT resolves correctly.
        # Pop the WHOLE doc_drift family (see test_agent_name_checks for the
        # orphaned-sys.modules rationale).
        for name in [
            n for n in list(sys.modules) if n == "doc_drift" or n.startswith("doc_drift.")
        ]:
            sys.modules.pop(name, None)
        import doc_drift.removed_governance_refs_checks as mod  # type: ignore[import-not-found]

        return mod
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(_SCRIPTS_DIR))


@pytest.fixture()
def checker():
    return _load_module()


# ── Clean baseline against the real repo tree ──────────────────


def test_clean_baseline_against_real_repo(checker) -> None:
    """The current post-cleanup tree must produce zero findings.

    This is the ratchet assertion: every existing reference is either
    allowlisted (historical) or absent. A future dangling reference will
    break this test, forcing an explicit baseline decision.
    """
    findings = checker.check_removed_governance_refs()
    assert findings == [], (
        "Removed-governance-reference guard has new findings against the real "
        "tree. Either reword the reference to be clearly historical, or add "
        "the file to the allowlist in removed_governance_refs_checks.py with a "
        f"one-line justification. Findings: {[f.message for f in findings]}"
    )


# ── Behavioural tests against a controlled tmp tree ────────────


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_new_reference_in_unallowlisted_file_warns(checker, tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/features/shiny-new-spec.md",
        "Run the matrix via `just check-configuration-matrix` before merge.\n",
    )
    findings = checker.check_removed_governance_refs(scan_root=tmp_path)
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "shiny-new-spec.md" in findings[0].file


def test_each_removed_token_is_detected(checker, tmp_path: Path) -> None:
    tokens = checker._REMOVED_TOKENS
    assert len(tokens) >= 8  # sanity: the catalog is populated
    for token in tokens:
        root = tmp_path / token.replace("/", "__")
        root.mkdir(parents=True, exist_ok=True)
        _write(root, "docs/live.md", f"see {token} for details\n")
        findings = checker.check_removed_governance_refs(scan_root=root)
        assert findings, f"token {token!r} was not detected"
        assert all(f.severity == "warning" for f in findings)


def test_allowlisted_adr_directory_no_warning(checker, tmp_path: Path) -> None:
    """References inside docs/architecture/decisions/ are historical (ADRs)."""
    _write(
        tmp_path,
        "docs/architecture/decisions/ADR-999-example.md",
        "The checker scripts/check_configuration_matrix.py enforced RULE-18b.\n",
    )
    assert checker.check_removed_governance_refs(scan_root=tmp_path) == []


def test_allowlisted_plans_directory_no_warning(checker, tmp_path: Path) -> None:
    """References inside docs/superpowers/plans/ are historical plans."""
    _write(
        tmp_path,
        "docs/superpowers/plans/2026-99-example.md",
        "Update docs/architecture/governance/aufg-registry.md after gates pass.\n",
    )
    assert checker.check_removed_governance_refs(scan_root=tmp_path) == []


def test_allowlisted_audit_directory_no_warning(checker, tmp_path: Path) -> None:
    """References inside _audit/ are historical review/finding files."""
    _write(
        tmp_path,
        "_audit/results/content-review/review-99-example.md",
        "scripts/governance/ was deleted in f8abb42c.\n",
    )
    assert checker.check_removed_governance_refs(scan_root=tmp_path) == []


def test_allowlisted_explicit_file_no_warning(checker, tmp_path: Path) -> None:
    """Curated standards that annotate the removal are allowlisted by path."""
    _write(
        tmp_path,
        "docs/_shared/CONSTRAINTS.md",
        "The check_configuration_matrix.py checker was removed in f8abb42c.\n",
    )
    assert checker.check_removed_governance_refs(scan_root=tmp_path) == []


def test_clean_file_without_tokens_no_warning(checker, tmp_path: Path) -> None:
    _write(tmp_path, "docs/feature.md", "Nothing relevant here.\n")
    assert checker.check_removed_governance_refs(scan_root=tmp_path) == []


def test_missing_scan_root_is_not_silent(checker, tmp_path: Path) -> None:
    """RULE-11: an unreadable scan root must surface, not fail silently."""
    bogus = tmp_path / "does-not-exist"
    findings = checker.check_removed_governance_refs(scan_root=bogus)
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "does-not-exist" in findings[0].message


def test_all_findings_are_warning_severity(checker, tmp_path: Path) -> None:
    """The guard is WARNING-ONLY: it never emits critical findings."""
    _write(
        tmp_path,
        "docs/live.md",
        "configuration-adoption-matrix.yaml and scripts/governance/ live here.\n",
    )
    findings = checker.check_removed_governance_refs(scan_root=tmp_path)
    assert findings, "expected at least one finding"
    assert all(f.severity == "warning" for f in findings)
