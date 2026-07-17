"""Unit tests for scripts/doc_drift/stub_variable_checks.py.

The §7 stub-variable detector flags the "documented ≠ implemented"
anti-pattern: a service builds a var-building dict (``extra=`` /
``variables=``) where a *registered* prompt variable is assigned a literal
empty string ``""`` at runtime — the template declares the slot but the
runtime never feeds it. It is **CI-BLOCKING (critical)** with a ratcheted
(file, var) allowlist in ``stub_variable_allowlist.py`` (the §7 work list):
the current tree starts clean (zero findings — the 7 RULE-11 entries are
absorbed, no §7 GAPs remain), and any *new* unallowlisted stub is a
critical finding that fails CI (prevents regression).

Conditional fallbacks (``x or ""``, ``str(x) if x else ""``) and
non-registered keys are NOT stubs and must not be flagged.

Note: loads the module dynamically like the other ``scripts/doc_drift`` tests
(``test_removed_governance_refs_checks.py`` …); tests are excluded from
pyright's CI ``include`` (see pyproject.toml ``[tool.pyright]``).
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def _load_module():
    """Load stub_variable_checks via the doc_drift import path."""
    sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        # Force a fresh import so REPO_ROOT resolves correctly.
        for name in [
            "doc_drift",
            "doc_drift.stub_variable_allowlist",
            "doc_drift.stub_variable_checks",
        ]:
            sys.modules.pop(name, None)
        import doc_drift.stub_variable_checks as mod  # type: ignore[import-not-found]

        return mod
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(_SCRIPTS_DIR))


@pytest.fixture()
def checker():
    return _load_module()


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# A registered var (present in narrare_core prompt variable_registry) and a
# non-registered key, used to assert detection precision.
_REGISTERED_VAR = "culture_guidelines"
_NON_REGISTERED_KEY = "definitely_not_a_registered_var"


# ── Clean baseline against the real repo tree ──────────────────


def test_clean_baseline_against_real_repo(checker) -> None:
    """The current tree must produce zero §7 findings.

    This is the ratchet assertion: every legitimate stub is allowlisted
    (the 7 RULE-11 entries are absorbed), so a future new stub — now a
    *critical* finding that blocks CI — breaks this test, forcing an
    explicit baseline decision (wire the source, or add an allowlist entry
    with a reason).
    """
    findings = checker.check_stub_variables()
    assert findings == [], (
        "§7 stub-variable guard has new findings against the real tree. "
        "Either wire the real value source, or add an allowlist entry in "
        "stub_variable_allowlist.py tagged 'RULE-11' (legit) or '§7 GAP' "
        "(remediation). Findings: "
        f"{[(f.file, f.message) for f in findings]}"
    )


def test_inventory_matches_allowlist_size(checker) -> None:
    """The full inventory and the allowlist must be in lock-step.

    Every current occurrence is allowlisted (no new), and every allowlist
    entry corresponds to a real occurrence (no stale entries lying about
    work that is already done). This keeps the work list honest.
    """
    occurrences = checker.collect_stub_variable_occurrences()
    baseline = checker.allowlist_pairs()
    scanned_pairs = {(o.file, o.var) for o in occurrences}
    assert scanned_pairs == baseline, (
        "§7 inventory / allowlist drift:\n"
        f"  NEW (in tree, not allowlisted): {sorted(scanned_pairs - baseline)}\n"
        f"  STALE (allowlisted, not in tree): {sorted(baseline - scanned_pairs)}"
    )


# ── Behavioural tests against a controlled tmp tree ────────────


def test_new_stub_in_unallowlisted_file_is_critical(checker, tmp_path: Path) -> None:
    """A new unallowlisted stub is a *critical* finding that blocks CI."""
    _write(
        tmp_path,
        "services/shiny_service.py",
        f'ctx = PromptContext(extra={{"{_REGISTERED_VAR}": ""}})\n',
    )
    findings = checker.check_stub_variables(scan_root=tmp_path)
    stub_findings = [f for f in findings if "[STUB-VARIABLE]" in f.message]
    assert len(stub_findings) == 1
    assert stub_findings[0].severity == "critical", (
        "The detector is CI-blocking: a new unallowlisted stub must be "
        "critical so check_doc_drift exits non-zero (prevents regression)."
    )
    assert _REGISTERED_VAR in stub_findings[0].message
    assert "shiny_service.py" in stub_findings[0].file


def test_variables_keyword_is_also_detected(checker, tmp_path: Path) -> None:
    """The ``variables=`` var-building keyword is scanned too, not just extra=."""
    _write(
        tmp_path,
        "services/vars_service.py",
        f'build(variables={{{_REGISTERED_VAR!r}: ""}})\n',
    )
    findings = [
        f
        for f in checker.check_stub_variables(scan_root=tmp_path)
        if "[STUB-VARIABLE]" in f.message
    ]
    assert len(findings) == 1
    assert findings[0].severity == "critical"


def test_conditional_fallback_is_not_a_stub(checker, tmp_path: Path) -> None:
    """``x or ""`` / ``str(x) if x else ""`` are NOT literal stubs."""
    _write(
        tmp_path,
        "services/fallback_service.py",
        "ctx = PromptContext(\n"
        f"    extra={{\n"
        f'        "{_REGISTERED_VAR}": novel.culture or "",\n'
        f'        "chapter_outline": str(x) if x else "",\n'
        "    },\n"
        ")\n",
    )
    findings = [
        f
        for f in checker.check_stub_variables(scan_root=tmp_path)
        if "[STUB-VARIABLE]" in f.message
    ]
    assert findings == [], (
        f"conditional fallbacks must not be flagged as stubs: {[f.message for f in findings]}"
    )


def test_non_registered_key_is_not_flagged(checker, tmp_path: Path) -> None:
    """An empty string under a non-registered key is not a §7 stub."""
    _write(
        tmp_path,
        "services/other.py",
        f'ctx = PromptContext(extra={{"{_NON_REGISTERED_KEY}": ""}})\n',
    )
    findings = [
        f
        for f in checker.check_stub_variables(scan_root=tmp_path)
        if "[STUB-VARIABLE]" in f.message
    ]
    assert findings == []


def test_empty_string_default_outside_var_dict_is_not_flagged(checker, tmp_path: Path) -> None:
    """A bare ``""`` not inside an extra=/variables= dict is out of scope."""
    _write(
        tmp_path,
        "services/unrelated.py",
        f'defaults = {{"{_NON_REGISTERED_KEY}": ""}}\nname = ""\n',
    )
    findings = [
        f
        for f in checker.check_stub_variables(scan_root=tmp_path)
        if "[STUB-VARIABLE]" in f.message
    ]
    assert findings == []


def test_allowlisted_pair_is_absorbed(checker, tmp_path: Path) -> None:
    """A stub whose (file, var) is in the baseline produces no warning."""
    # Reconstruct an allowlisted repo-relative path under tmp so the
    # computed rel path matches the baseline entry exactly. Uses the
    # story-suggest chapter_outline pair (RULE-11: legitimately empty when
    # no chapter_id is targeted — a confirmed-optional var, not a §7 GAP).
    _write(
        tmp_path,
        "apps/api/narrare/writing/story_suggest_service.py",
        'ctx = PromptContext(extra={"chapter_outline": ""})\n',
    )
    findings = [
        f
        for f in checker.check_stub_variables(scan_root=tmp_path)
        if "[STUB-VARIABLE]" in f.message
    ]
    assert findings == [], (
        "an allowlisted (file, var) pair must be absorbed by the baseline: "
        f"{[f.message for f in findings]}"
    )


def test_test_files_are_not_scanned(checker, tmp_path: Path) -> None:
    """Test files (test_*.py / *_test.py) are excluded from the scan."""
    _write(
        tmp_path,
        "test_services.py",
        f'ctx = PromptContext(extra={{"{_REGISTERED_VAR}": ""}})\n',
    )
    _write(
        tmp_path,
        "services_test.py",
        f'ctx = PromptContext(extra={{"{_REGISTERED_VAR}": ""}})\n',
    )
    findings = [
        f
        for f in checker.check_stub_variables(scan_root=tmp_path)
        if "[STUB-VARIABLE]" in f.message
    ]
    assert findings == []


def test_missing_scan_root_is_not_silent(checker, tmp_path: Path) -> None:
    """RULE-11: an unreadable scan root must surface (fail closed), not pass.

    The detector is CI-blocking: when it cannot scan, it emits a *critical*
    finding so the gate fails closed rather than silently passing.
    """
    bogus = tmp_path / "does-not-exist"
    findings = checker.check_stub_variables(scan_root=bogus)
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert "does-not-exist" in findings[0].message


def test_all_stub_findings_are_critical_severity(checker, tmp_path: Path) -> None:
    """The guard is CI-BLOCKING: it emits *critical* (not warning) findings.

    A new unallowlisted stub must be critical so ``check_doc_drift`` exits
    non-zero and blocks CI/pre-commit (the final enforcement after the §7
    inventory reached 0 gaps).
    """
    _write(
        tmp_path,
        "services/spam.py",
        f'ctx = PromptContext(extra={{"{_REGISTERED_VAR}": ""}})\n',
    )
    findings = checker.check_stub_variables(scan_root=tmp_path)
    assert findings, "expected at least one finding"
    assert all(f.severity == "critical" for f in findings), (
        "every §7 stub-variable finding must be critical (CI-blocking)."
    )


def test_occurrences_sorted_and_carry_line_and_target(checker, tmp_path: Path) -> None:
    """Each occurrence records its file, line, var, and enclosing call."""
    _write(
        tmp_path,
        "services/a.py",
        "ctx = PromptContext(\n"
        f"    extra={{\n"
        f'        "{_REGISTERED_VAR}": "",\n'
        f'        "chapter_outline": "",\n'
        "    },\n"
        ")\n",
    )
    occs = checker.collect_stub_variable_occurrences(scan_root=tmp_path)
    assert len(occs) == 2
    # sorted by (file, lineno, var)
    assert occs[0].var == _REGISTERED_VAR
    assert occs[1].var == "chapter_outline"
    assert occs[0].lineno < occs[1].lineno
    assert all(o.call_target == "PromptContext" for o in occs)
    assert all(o.file.endswith("services/a.py") for o in occs)
