"""Tests for ADR-048 Mode 2 declaration validation and placeholder evidence.

Tests that:
1. Mode 2 declarations are validated (required fields, valid mechanisms).
2. >5 declarations trigger an audit hint.
3. Placeholder evidence records are detected and rejected.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from adoption.mode2_validation import (  # noqa: E402
    _PLACEHOLDER_FINGERPRINT,
    _PLACEHOLDER_SYSTEM,
    _PLACEHOLDER_USER,
    Mode2ValidationFinding,
    Mode2ValidationReport,
    check_placeholder_evidence,
    validate_adoption_mode2,
    validate_mode2_declarations,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_declaration(
    reason: str = "Agent composes prompt from deps and capabilities internally.",
    variables: list[str] | None = None,
    mechanism: str = "agent_deps",
) -> dict[str, object]:
    return {
        "reason": reason,
        "variables": variables if variables is not None else ["chapter_text", "project_title"],
        "injection_mechanism": mechanism,
    }


def _critical_codes(findings: list[Mode2ValidationFinding]) -> set[str]:
    return {f.code for f in findings if f.severity == "critical"}


def _warning_codes(findings: list[Mode2ValidationFinding]) -> set[str]:
    return {f.code for f in findings if f.severity == "warning"}


# ---------------------------------------------------------------------------
# validate_mode2_declarations — valid cases
# ---------------------------------------------------------------------------


def test_validate_mode2_no_declarations_returns_empty() -> None:
    """No declarations → no findings."""
    registry: dict[str, object] = {}
    findings = validate_mode2_declarations(registry)
    assert findings == []


def test_validate_mode2_valid_declaration_no_findings() -> None:
    """A properly formed declaration produces no findings."""
    registry = {
        "manual_injection_declarations": {
            "analysis/beta_reader": _make_valid_declaration(),
        }
    }
    findings = validate_mode2_declarations(registry)
    assert findings == []


def test_validate_mode2_multiple_valid_declarations_no_findings() -> None:
    """Multiple valid declarations (under threshold) → no findings."""
    decls = {}
    for i in range(5):
        decls[f"analysis/mode_{i}"] = _make_valid_declaration()
    registry = {"manual_injection_declarations": decls}
    findings = validate_mode2_declarations(registry)
    assert findings == []


# ---------------------------------------------------------------------------
# validate_mode2_declarations — invalid cases
# ---------------------------------------------------------------------------


def test_validate_mode2_missing_reason_is_critical() -> None:
    """Declaration with missing/short reason → critical finding."""
    registry = {
        "manual_injection_declarations": {
            "analysis/beta_reader": _make_valid_declaration(reason="short"),
        }
    }
    findings = validate_mode2_declarations(registry)
    assert "MODE2_MISSING_REASON" in _critical_codes(findings)


def test_validate_mode2_missing_variables_is_critical() -> None:
    """Declaration with empty variables → critical finding."""
    registry = {
        "manual_injection_declarations": {
            "analysis/beta_reader": _make_valid_declaration(variables=[]),
        }
    }
    findings = validate_mode2_declarations(registry)
    assert "MODE2_MISSING_VARIABLES" in _critical_codes(findings)


def test_validate_mode2_invalid_mechanism_is_critical() -> None:
    """Declaration with unknown injection_mechanism → critical finding."""
    registry = {
        "manual_injection_declarations": {
            "analysis/beta_reader": _make_valid_declaration(mechanism="unknown_thing"),
        }
    }
    findings = validate_mode2_declarations(registry)
    assert "MODE2_INVALID_MECHANISM" in _critical_codes(findings)


def test_validate_mode2_non_dict_declaration_is_critical() -> None:
    """Non-mapping declaration → critical finding."""
    registry = {
        "manual_injection_declarations": {
            "analysis/beta_reader": "not a dict",
        }
    }
    findings = validate_mode2_declarations(registry)
    assert "MODE2_INVALID_DECLARATION" in _critical_codes(findings)


# ---------------------------------------------------------------------------
# validate_mode2_declarations — audit threshold
# ---------------------------------------------------------------------------


def test_validate_mode2_over_threshold_triggers_audit_hint() -> None:
    """>5 declarations → warning audit hint."""
    decls = {}
    for i in range(6):
        decls[f"analysis/mode_{i}"] = _make_valid_declaration()
    registry = {"manual_injection_declarations": decls}
    findings = validate_mode2_declarations(registry)
    assert "MODE2_AUDIT_THRESHOLD_EXCEEDED" in _warning_codes(findings)
    # No critical findings — all declarations are valid.
    assert _critical_codes(findings) == set()


def test_validate_mode2_exactly_at_threshold_no_hint() -> None:
    """Exactly 5 declarations → no audit hint."""
    decls = {}
    for i in range(5):
        decls[f"analysis/mode_{i}"] = _make_valid_declaration()
    registry = {"manual_injection_declarations": decls}
    findings = validate_mode2_declarations(registry)
    assert "MODE2_AUDIT_THRESHOLD_EXCEEDED" not in _warning_codes(findings)


# ---------------------------------------------------------------------------
# check_placeholder_evidence
# ---------------------------------------------------------------------------


def test_placeholder_evidence_no_dir_returns_empty() -> None:
    """No evidence dir → no findings."""
    findings = check_placeholder_evidence(None)
    assert findings == []


def test_placeholder_evidence_no_file_returns_empty(tmp_path: Path) -> None:
    """Evidence dir without invocations.jsonl → no findings."""
    findings = check_placeholder_evidence(tmp_path)
    assert findings == []


def test_placeholder_evidence_detects_fingerprint(tmp_path: Path) -> None:
    """Evidence record with placeholder fingerprint → critical finding."""
    evidence_file = tmp_path / "invocations.jsonl"
    record = {
        "feature_id": "analysis",
        "mode": "beta_reader",
        "prompt_fingerprint": _PLACEHOLDER_FINGERPRINT,
    }
    evidence_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

    findings = check_placeholder_evidence(tmp_path)

    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert findings[0].code == "PLACEHOLDER_EVIDENCE_FOUND"


def test_placeholder_evidence_detects_raw_prompt(tmp_path: Path) -> None:
    """Evidence record with raw placeholder system/user → critical finding."""
    evidence_file = tmp_path / "invocations.jsonl"
    record = {
        "feature_id": "kb",
        "mode": "assist",
        "system": _PLACEHOLDER_SYSTEM,
        "user": _PLACEHOLDER_USER,
    }
    evidence_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

    findings = check_placeholder_evidence(tmp_path)

    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert findings[0].code == "PLACEHOLDER_EVIDENCE_FOUND"


def test_placeholder_evidence_clean_record_no_findings(tmp_path: Path) -> None:
    """Evidence record with real fingerprint → no findings."""
    evidence_file = tmp_path / "invocations.jsonl"
    record = {
        "feature_id": "writing",
        "mode": "new_chapter",
        "prompt_fingerprint": "a" * 64,  # not the placeholder
    }
    evidence_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

    findings = check_placeholder_evidence(tmp_path)

    assert findings == []


def test_placeholder_evidence_multiple_records_counts_all(tmp_path: Path) -> None:
    """Multiple placeholder records → single finding with count."""
    evidence_file = tmp_path / "invocations.jsonl"
    records = [
        {"feature_id": "a", "mode": "x", "prompt_fingerprint": _PLACEHOLDER_FINGERPRINT},
        {"feature_id": "b", "mode": "y", "prompt_fingerprint": _PLACEHOLDER_FINGERPRINT},
    ]
    evidence_file.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    findings = check_placeholder_evidence(tmp_path)

    assert len(findings) == 1
    assert "2 evidence record(s)" in findings[0].message


# ---------------------------------------------------------------------------
# validate_adoption_mode2 — integration
# ---------------------------------------------------------------------------


def test_validate_adoption_mode2_combines_both_checks(tmp_path: Path) -> None:
    """validate_adoption_mode2 combines declaration + placeholder checks."""
    evidence_file = tmp_path / "invocations.jsonl"
    record = {
        "feature_id": "a",
        "mode": "x",
        "prompt_fingerprint": _PLACEHOLDER_FINGERPRINT,
    }
    evidence_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

    registry = {
        "manual_injection_declarations": {
            "analysis/bad": _make_valid_declaration(reason="short"),
        }
    }

    report = validate_adoption_mode2(registry, evidence_dir=tmp_path)

    assert report.has_critical
    assert report.critical_count == 2  # 1 from declarations, 1 from placeholder


def test_validate_adoption_mode2_no_issues() -> None:
    """Clean registry + no evidence dir → no findings."""
    registry: dict[str, object] = {}
    report = validate_adoption_mode2(registry, evidence_dir=None)
    assert not report.has_critical
    assert not report.has_warnings
    assert report.findings == []


# ---------------------------------------------------------------------------
# Mode2ValidationReport properties
# ---------------------------------------------------------------------------


def test_report_has_critical_property() -> None:
    """has_critical is True when any critical finding exists."""
    report = Mode2ValidationReport(findings=[Mode2ValidationFinding("warning", "W", "warn")])
    assert not report.has_critical

    report = Mode2ValidationReport(findings=[Mode2ValidationFinding("critical", "C", "crit")])
    assert report.has_critical


def test_report_counts() -> None:
    """critical_count and warning_count are correct."""
    report = Mode2ValidationReport(
        findings=[
            Mode2ValidationFinding("critical", "C1", "c1"),
            Mode2ValidationFinding("critical", "C2", "c2"),
            Mode2ValidationFinding("warning", "W1", "w1"),
        ]
    )
    assert report.critical_count == 2
    assert report.warning_count == 1
