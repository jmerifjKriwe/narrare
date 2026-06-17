"""Tests for scripts/check_registry_drift.py — drift reporting & severity.

Split from ``test_check_registry_drift_modes.py`` for RULE-04 (file-size
limit). This module covers the *reporting* surface: ``DriftReport`` exit-code
semantics, finding-sort order, and schema-failure severity. The drift
*detection* behaviour (alignment, missing prompts, unregistered files) lives
in ``test_check_registry_drift_modes.py``.

See: ADR-041 Decision 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Project root for `scripts.*` imports.
_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Same-directory imports for shared fixtures.
_DIR = str(Path(__file__).resolve().parent)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from scripts.check_registry_drift import (  # noqa: E402
    DriftFinding,
    DriftReport,
    check_registry_drift,
    validate_registry_schema,
)
from test_check_registry_drift import (  # noqa: E402
    _make_prompt_file,
    _make_registry,
    _write_env,
    _write_schema_only,
)


class TestDriftFindingSeverity:
    """Critical findings cause non-zero exit code; reporting invariants hold."""

    def test_critical_produces_exit_1(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "missing": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        report = DriftReport(findings=findings)
        assert report.has_critical

    def test_warnings_only_exit_0(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "draft": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "draft")
        _make_prompt_file(prompts_dir, "writing", "orphan")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        report = DriftReport(findings=findings)
        assert not report.has_critical
        assert report.has_warnings

    def test_schema_failure_returns_critical(self, tmp_path: Path) -> None:
        bad_reg: dict[str, object] = {"version": "bad", "features": "not_a_dict"}
        findings = validate_registry_schema(bad_reg, _write_schema_only(tmp_path))
        assert any(f.severity == "critical" for f in findings)

    def test_drift_findings_sorted_by_severity(self, tmp_path: Path) -> None:
        """check_registry_drift returns findings sorted: critical -> warning -> info."""
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "draft": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "draft")
        _make_prompt_file(prompts_dir, "writing", "orphan")
        _make_prompt_file(prompts_dir, "unknown_cat", "mode")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        severities = [f.severity for f in findings]
        # All warnings should come before any info.
        if "warning" in severities and "info" in severities:
            warn_idx = severities.index("warning")
            info_idx = severities.index("info")
            assert warn_idx < info_idx

    def test_report_summary_counts(self) -> None:
        findings = [
            DriftFinding(severity="critical", category="a", mode="", message="c"),
            DriftFinding(severity="warning", category="b", mode="", message="w"),
            DriftFinding(severity="info", category="c", mode="", message="i"),
        ]
        report = DriftReport(findings=findings)
        assert "1 critical" in report.summary()
        assert "1 warnings" in report.summary()
        assert "1 info" in report.summary()

    def test_report_no_critical(self) -> None:
        findings = [
            DriftFinding(severity="warning", category="b", mode="", message="w"),
            DriftFinding(severity="info", category="c", mode="", message="i"),
        ]
        report = DriftReport(findings=findings)
        assert not report.has_critical
        assert report.has_warnings
