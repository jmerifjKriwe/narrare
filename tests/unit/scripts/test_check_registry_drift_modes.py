"""Tests for scripts/check_registry_drift.py — mode-prompt alignment & drift.

Validates mode-prompt alignment, missing prompts, unregistered prompt files,
drift finding severity, and reporting per ADR-041 Decision 1.
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

# ── TestModePromptAlignment ────────────────────────────────────────────


class TestModePromptAlignment:
    """Registered modes with matching prompt files produce no critical findings."""

    def test_aligned_modes_no_critical(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "new_chapter": {"requires_runtime_evidence": True},
                        "extend_chapter": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "new_chapter")
        _make_prompt_file(prompts_dir, "writing", "extend_chapter")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert criticals == []

    def test_aligned_modes_produce_info(self, tmp_path: Path) -> None:
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

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        infos = [f for f in findings if f.severity == "info"]
        assert len(infos) >= 1
        assert any("writing" in f.message for f in infos)

    def test_modeless_category_aligned(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "chat": {
                    "modes": [],
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "chat", "")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert criticals == []


# ── TestMissingPromptForMode ───────────────────────────────────────────


class TestMissingPromptForMode:
    """Mode in registry but no prompt file = critical finding."""

    def test_missing_prompt_critical(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "ghost_mode": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        # Don't create any prompt file for ghost_mode.

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert len(criticals) == 1
        assert "ghost_mode" in criticals[0].message
        assert criticals[0].category == "writing"

    def test_missing_modeless_prompt_critical(self, tmp_path: Path) -> None:
        reg = _make_registry(
            features={
                "chat": {
                    "modes": [],
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        # No chat/en/system.md created.

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert len(criticals) == 1
        assert "modeless" in criticals[0].message.lower()

    def test_partial_missing_prompts(self, tmp_path: Path) -> None:
        """Two modes registered, one missing prompt -> only that one critical."""
        reg = _make_registry(
            features={
                "writing": {
                    "modes": {
                        "present": {"requires_runtime_evidence": True},
                        "absent": {"requires_runtime_evidence": True},
                    },
                    "required_infrastructure": {"prompt_composer": "required"},
                    "context_variables": {"must": [], "should": []},
                },
            }
        )
        reg_path, prompts_dir = _write_env(tmp_path, reg)
        _make_prompt_file(prompts_dir, "writing", "present")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        criticals = [f for f in findings if f.severity == "critical"]
        assert len(criticals) == 1
        assert "absent" in criticals[0].message


# ── TestUnregisteredPromptFile ─────────────────────────────────────────


class TestUnregisteredPromptFile:
    """Prompt file not in registry = warning."""

    def test_unregistered_mode_warning(self, tmp_path: Path) -> None:
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
        _make_prompt_file(prompts_dir, "writing", "unregistered_extra")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        warnings = [f for f in findings if f.severity == "warning"]
        assert len(warnings) == 1
        assert "unregistered_extra" in warnings[0].message

    def test_unregistered_category_warning(self, tmp_path: Path) -> None:
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
        _make_prompt_file(prompts_dir, "unknown_cat", "some_mode")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        warnings = [f for f in findings if f.severity == "warning"]
        assert any("unknown_cat" in f.message for f in warnings)

    def test_skip_infrastructure_categories(self, tmp_path: Path) -> None:
        """meta/ and universal/ prompt files should not produce warnings."""
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
        # Create infrastructure prompts -- should be ignored.
        _make_prompt_file(prompts_dir, "meta", "")
        _make_prompt_file(prompts_dir, "universal", "")

        findings = check_registry_drift(
            registry_path=reg_path,
            prompts_dir=prompts_dir,
        )
        warnings = [f for f in findings if f.severity == "warning"]
        assert not any("meta" in f.message for f in warnings)
        assert not any("universal" in f.message for f in warnings)


# ── TestDriftFindingSeverity ───────────────────────────────────────────


class TestDriftFindingSeverity:
    """Critical findings cause non-zero exit code."""

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
