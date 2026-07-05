"""Tests for ``scripts/_coverage_model.py`` — ModuleCoverage.status logic.

The RULE-10 target is the hard floor: coverage below the target is always
a failure (blocking in --fail mode). The ratcheted baseline is a soft
warning: coverage below the baseline (but still above target) is a
non-blocking regression warning. See docs/_shared/CONSTRAINTS.md (RULE-10).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is on sys.path for the ``_coverage_model`` import.
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import _coverage_model  # noqa: E402  # type: ignore[import-untyped]
from _coverage_model import (  # noqa: E402  # type: ignore[import-untyped]
    STATUS_BELOW_TARGET,
    STATUS_MEETS_TARGET,
    STATUS_REGRESSION,
    BaselineShrinkError,
    ModuleCoverage,
    save_baselines,
)


def _module(line_rate: float, baseline: float, target: int) -> ModuleCoverage:
    """Build a ModuleCoverage with a fixed package name for readability."""
    return ModuleCoverage(
        package="test_pkg",
        line_rate=line_rate,
        baseline=baseline,
        target=target,
    )


class TestStatusMeetsTarget:
    """Coverage at or above both baseline and target."""

    def test_above_both_returns_meets_target(self) -> None:
        m = _module(line_rate=0.95, baseline=80.0, target=90)
        assert m.status == STATUS_MEETS_TARGET

    def test_exactly_equals_target_returns_meets_target(self) -> None:
        """Edge case: coverage exactly equals target → meets target."""
        m = _module(line_rate=0.90, baseline=85.0, target=90)
        assert m.status == STATUS_MEETS_TARGET


class TestStatusRegression:
    """Coverage below baseline but above target — a non-blocking warning."""

    def test_above_target_but_below_baseline_is_regression(self) -> None:
        """85% coverage, target=80, baseline=88.

        The module beats its RULE-10 target (80%) yet sits below its
        ratcheted baseline (88%). This is a regression WARNING, not a
        hard failure — the target is met.
        """
        m = _module(line_rate=0.85, baseline=88.0, target=80)
        assert m.status == STATUS_REGRESSION

    def test_exactly_one_below_baseline_still_regression(self) -> None:
        """Edge case: coverage 87.9% vs baseline 88.0, target 80 → regression."""
        m = _module(line_rate=0.879, baseline=88.0, target=80)
        assert m.status == STATUS_REGRESSION


class TestStatusBelowTarget:
    """Coverage below the RULE-10 target — a blocking failure."""

    def test_below_both_baseline_and_target_is_below_target(self) -> None:
        """70% coverage, baseline=75, target=80 → below target (hard fail)."""
        m = _module(line_rate=0.70, baseline=75.0, target=80)
        assert m.status == STATUS_BELOW_TARGET

    def test_above_baseline_but_below_target_returns_below_target(self) -> None:
        m = _module(line_rate=0.82, baseline=78.0, target=90)
        assert m.status == STATUS_BELOW_TARGET

    def test_exactly_equals_baseline_is_not_regression(self) -> None:
        """Edge case: coverage exactly equals baseline → not a regression (>=)."""
        m = _module(line_rate=0.88, baseline=88.0, target=90)
        assert m.status == STATUS_BELOW_TARGET


class TestHelperProperties:
    """Derived helper properties stay consistent with status."""

    def test_meets_target_flag_matches_status(self) -> None:
        m = _module(line_rate=0.95, baseline=80.0, target=90)
        assert m.meets_target is True

    def test_at_baseline_flag_true_when_at_or_above(self) -> None:
        m = _module(line_rate=0.88, baseline=88.0, target=90)
        assert m.at_baseline is True


class TestSaveBaselinesSubsetGuard:
    """``save_baselines`` must refuse to shrink the tracked package set.

    Regression guard for the incident in commit 1a5a833b, where a
    ``--update-baselines`` run against a reduced-scope coverage.xml silently
    dropped the ratchet protection for 48 of 49 modules. See review-02-testing
    AUFG-02-05.
    """

    def test_save_rejects_strict_subset_of_existing_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline_file = tmp_path / "coverage_baselines.json"
        monkeypatch.setattr(_coverage_model, "BASELINES_FILE", baseline_file)

        # Seed an established baseline with 3 modules.
        save_baselines({"a": 90.0, "b": 80.0, "c": 70.0})

        # A reduced-scope run that only sees one of the three must be rejected.
        with pytest.raises(BaselineShrinkError) as exc:
            save_baselines({"a": 92.0})
        assert "strict subset" in str(exc.value)
        # Original baselines must remain untouched on disk.
        assert _coverage_model.load_baselines() == {"a": 90.0, "b": 80.0, "c": 70.0}

    def test_save_allows_equal_key_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline_file = tmp_path / "coverage_baselines.json"
        monkeypatch.setattr(_coverage_model, "BASELINES_FILE", baseline_file)

        save_baselines({"a": 90.0, "b": 80.0})
        # Same keys (even with different values) is fine — that's the normal
        # ratchet update path.
        save_baselines({"a": 92.0, "b": 82.0})
        assert _coverage_model.load_baselines() == {"a": 92.0, "b": 82.0}

    def test_save_allows_superset_of_existing_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline_file = tmp_path / "coverage_baselines.json"
        monkeypatch.setattr(_coverage_model, "BASELINES_FILE", baseline_file)

        save_baselines({"a": 90.0})
        # Adding a new module is legitimate growth, not shrinkage.
        save_baselines({"a": 90.0, "b": 80.0})
        assert _coverage_model.load_baselines() == {"a": 90.0, "b": 80.0}

    def test_save_allows_first_run_with_no_existing_baselines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline_file = tmp_path / "coverage_baselines.json"
        monkeypatch.setattr(_coverage_model, "BASELINES_FILE", baseline_file)

        # No prior baseline file → any package set is acceptable.
        save_baselines({"only": 50.0})
        assert _coverage_model.load_baselines() == {"only": 50.0}
