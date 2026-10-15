"""Unit tests for the eval_drift P0 priority gating (AUFG-02-09).

Covers:
- ``Priorities`` manifest loading + missing-file tolerance + ``is_p0``.
- ``DriftReport.has_p0_drift`` / ``p0_drift_count`` semantics.
- ``--fail-on-priority P0`` exit-code behaviour via ``main()``:
    * a P0 regression  -> exit 1
    * a non-P0 regression -> exit 0 (WARNING only)
- back-compat: without ``--fail-on-priority`` any drift still exits 1.

The scripts/ tree is not on the pytest ``pythonpath``, so the package is
loaded via sys.path insertion (same pattern as test_quality_joiner.py).
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_REAL_MANIFEST = _REPO_ROOT / "evals" / "p0_priorities.json"


def _load_eval_drift() -> dict[str, ModuleType]:
    """Import the eval_drift package on a clean sys.path entry."""
    sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        # Pop the WHOLE eval_drift family — popping only selected submodules
        # would orphan the siblings in sys.modules while the fresh parent
        # package loses their attributes.
        for name in [
            n for n in list(sys.modules) if n == "eval_drift" or n.startswith("eval_drift.")
        ]:
            sys.modules.pop(name, None)
        import eval_drift.__main__ as main_mod  # type: ignore[import-not-found]
        import eval_drift.comparison as comparison  # type: ignore[import-not-found]
        import eval_drift.parser as parser  # type: ignore[import-not-found]
        import eval_drift.priorities as priorities  # type: ignore[import-not-found]

        return {
            "comparison": comparison,
            "parser": parser,
            "priorities": priorities,
            "main": main_mod,
        }
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(_SCRIPTS_DIR))


@pytest.fixture()
def mods() -> dict[str, ModuleType]:
    return _load_eval_drift()


# ── Priorities manifest ──────────────────────────────────────────


def test_real_manifest_marks_guardrail_as_p0(mods: dict[str, ModuleType]) -> None:
    priorities = mods["priorities"]
    p = priorities.Priorities.from_manifest(_REAL_MANIFEST)
    assert p.is_p0("writing_prose", "guardrail-veiled-disclaimer-trap") is True


def test_real_manifest_does_not_mark_arbitrary_case(mods: dict[str, ModuleType]) -> None:
    priorities = mods["priorities"]
    p = priorities.Priorities.from_manifest(_REAL_MANIFEST)
    assert p.is_p0("writing_prose", "extend-battle-climax") is False
    assert p.is_p0("other_suite", "guardrail-veiled-disclaimer-trap") is False


def test_missing_manifest_tolerated_as_no_p0(mods: dict[str, ModuleType], tmp_path: Path) -> None:
    priorities = mods["priorities"]
    p = priorities.Priorities.from_manifest(tmp_path / "does-not-exist.json")
    assert p.p0_keys == set()
    assert p.is_p0("writing_prose", "guardrail-veiled-disclaimer-trap") is False


def test_unparseable_manifest_tolerated(mods: dict[str, ModuleType], tmp_path: Path) -> None:
    priorities = mods["priorities"]
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    p = priorities.Priorities.from_manifest(bad)
    assert p.p0_keys == set()


def test_manifest_ignores_comment_keys(mods: dict[str, ModuleType], tmp_path: Path) -> None:
    priorities = mods["priorities"]
    manifest = tmp_path / "p.json"
    manifest.write_text(
        json.dumps(
            {
                "_comment": "should be ignored",
                "writing_prose": ["guardrail-veiled-disclaimer-trap"],
            }
        ),
        encoding="utf-8",
    )
    p = priorities.Priorities.from_manifest(manifest)
    assert p.p0_keys == {"writing_prose::guardrail-veiled-disclaimer-trap"}


def test_manifest_rejects_non_list_entries(mods: dict[str, ModuleType], tmp_path: Path) -> None:
    priorities = mods["priorities"]
    manifest = tmp_path / "p.json"
    manifest.write_text(
        json.dumps({"writing_prose": "not-a-list"}),
        encoding="utf-8",
    )
    p = priorities.Priorities.from_manifest(manifest)
    assert p.p0_keys == set()


# ── DriftReport P0 semantics ─────────────────────────────────────


def _baseline(tmp_path: Path, source: str, cases: dict[str, float]) -> Path:
    """Write a minimal baseline file the comparison logic can read."""
    baselines = tmp_path / "baselines"
    baselines.mkdir(exist_ok=True)
    data: dict[str, Any] = {
        "version": 1,
        "test_cases": {
            name: {"avg_score": score, "success_rate": 1.0, "run_count": 1}
            for name, score in cases.items()
        },
    }
    (baselines / f"{source}-baseline.json").write_text(json.dumps(data), encoding="utf-8")
    return baselines


def _result(mods: dict[str, ModuleType], source: str, case_scores: dict[str, float]):
    """Build an EvalResultFile with controlled per-case average scores."""
    parser = mods["parser"]
    test_cases = []
    for name, score in case_scores.items():
        tc = parser.TestCaseScore(name=name)
        tc.scores.append(score)
        tc.successes.append(True)
        test_cases.append(tc)
    return parser.EvalResultFile(source=source, test_cases=test_cases)


def test_p0_regression_sets_has_p0_drift(mods: dict[str, ModuleType], tmp_path: Path) -> None:
    comparison, priorities = mods["comparison"], mods["priorities"]
    baselines = _baseline(tmp_path, "writing_prose", {"guardrail-veiled-disclaimer-trap": 1.0})
    result = _result(mods, "writing_prose", {"guardrail-veiled-disclaimer-trap": 0.5})
    p = priorities.Priorities.from_manifest(_REAL_MANIFEST)

    report = comparison.compare_against_baselines([result], baselines, 0.05, p)

    assert report.has_drift is True
    assert report.has_p0_drift is True
    assert report.p0_drift_count == 1
    assert report.drift_count == 1


def test_non_p0_regression_does_not_set_has_p0_drift(
    mods: dict[str, ModuleType], tmp_path: Path
) -> None:
    comparison, priorities = mods["comparison"], mods["priorities"]
    # Only a non-P0 case regresses.
    baselines = _baseline(tmp_path, "writing_prose", {"extend-battle-climax": 1.0})
    result = _result(mods, "writing_prose", {"extend-battle-climax": 0.5})
    p = priorities.Priorities.from_manifest(_REAL_MANIFEST)

    report = comparison.compare_against_baselines([result], baselines, 0.05, p)

    assert report.has_drift is True  # there IS drift ...
    assert report.has_p0_drift is False  # ... but not on a P0 case
    assert report.p0_drift_count == 0
    assert report.drift_count == 1


def test_no_priorities_keeps_legacy_drift_behaviour(
    mods: dict[str, ModuleType], tmp_path: Path
) -> None:
    comparison = mods["comparison"]
    baselines = _baseline(tmp_path, "writing_prose", {"extend-battle-climax": 1.0})
    result = _result(mods, "writing_prose", {"extend-battle-climax": 0.5})

    # priorities=None -> back-compat: is_p0 always False, has_p0_drift False.
    report = comparison.compare_against_baselines([result], baselines, 0.05, None)

    assert report.has_drift is True
    assert report.has_p0_drift is False
    assert all(c.is_p0 is False for c in report.comparisons)


def test_within_threshold_p0_case_does_not_drift(
    mods: dict[str, ModuleType], tmp_path: Path
) -> None:
    comparison, priorities = mods["comparison"], mods["priorities"]
    # P0 case drops only 3% (< 5% threshold) -> no drift at all.
    baselines = _baseline(tmp_path, "writing_prose", {"guardrail-veiled-disclaimer-trap": 1.0})
    result = _result(mods, "writing_prose", {"guardrail-veiled-disclaimer-trap": 0.97})
    p = priorities.Priorities.from_manifest(_REAL_MANIFEST)

    report = comparison.compare_against_baselines([result], baselines, 0.05, p)

    assert report.has_drift is False
    assert report.has_p0_drift is False
    assert report.p0_drift_count == 0


# ── CLI exit-code behaviour (main) ────────────────────────────────


def _write_result_file(dir_path: Path, source: str, case_scores: dict[str, float]) -> None:
    """Write a result JSON the parser understands (scores dict averaging)."""
    dir_path.mkdir(parents=True, exist_ok=True)
    cases = [
        {"name": name, "scores": {"Quality": score}, "assertions": {"ok": True}}
        for name, score in case_scores.items()
    ]
    (dir_path / f"{source}.json").write_text(json.dumps({"cases": cases}), encoding="utf-8")


def _write_manifest(dir_path: Path) -> Path:
    manifest = dir_path / "p0_priorities.json"
    manifest.write_text(
        json.dumps({"writing_prose": ["guardrail-veiled-disclaimer-trap"]}),
        encoding="utf-8",
    )
    return manifest


def test_fail_on_priority_p0_blocks_on_p0_regression(
    mods: dict[str, ModuleType], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main_mod = mods["main"]
    results = tmp_path / "results"
    baselines = tmp_path / "baselines"
    baselines.mkdir()
    _baseline(tmp_path, "writing_prose", {"guardrail-veiled-disclaimer-trap": 1.0})
    _write_result_file(results, "writing_prose", {"guardrail-veiled-disclaimer-trap": 0.5})
    manifest = _write_manifest(tmp_path)

    rc = main_mod.main(
        [
            "--results-dir",
            str(results),
            "--baselines-dir",
            str(baselines),
            "--priorities",
            str(manifest),
            "--fail-on-priority",
            "P0",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 1
    assert "P0-FAIL" in out
    assert "guardrail-veiled-disclaimer-trap" in out


def test_fail_on_priority_p0_allows_non_p0_regression(
    mods: dict[str, ModuleType], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main_mod = mods["main"]
    results = tmp_path / "results"
    baselines = tmp_path / "baselines"
    baselines.mkdir()
    _baseline(tmp_path, "writing_prose", {"extend-battle-climax": 1.0})
    _write_result_file(results, "writing_prose", {"extend-battle-climax": 0.5})
    manifest = _write_manifest(tmp_path)

    rc = main_mod.main(
        [
            "--results-dir",
            str(results),
            "--baselines-dir",
            str(baselines),
            "--priorities",
            str(manifest),
            "--fail-on-priority",
            "P0",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 0  # non-P0 drift is non-blocking ...
    assert "non-P0" in out  # ... but still surfaced as a WARNING
    assert "extend-battle-climax" in out


def test_legacy_mode_any_drift_blocks(mods: dict[str, ModuleType], tmp_path: Path) -> None:
    """Without --fail-on-priority, ANY drift (incl. non-P0) exits 1 (back-compat)."""
    main_mod = mods["main"]
    results = tmp_path / "results"
    baselines = tmp_path / "baselines"
    baselines.mkdir()
    _baseline(tmp_path, "writing_prose", {"extend-battle-climax": 1.0})
    _write_result_file(results, "writing_prose", {"extend-battle-climax": 0.5})
    manifest = _write_manifest(tmp_path)

    rc = main_mod.main(
        [
            "--results-dir",
            str(results),
            "--baselines-dir",
            str(baselines),
            "--priorities",
            str(manifest),
        ]
    )

    assert rc == 1


def test_p0_mode_no_drift_exits_zero(mods: dict[str, ModuleType], tmp_path: Path) -> None:
    main_mod = mods["main"]
    results = tmp_path / "results"
    baselines = tmp_path / "baselines"
    baselines.mkdir()
    _baseline(tmp_path, "writing_prose", {"guardrail-veiled-disclaimer-trap": 1.0})
    _write_result_file(results, "writing_prose", {"guardrail-veiled-disclaimer-trap": 1.0})
    manifest = _write_manifest(tmp_path)

    rc = main_mod.main(
        [
            "--results-dir",
            str(results),
            "--baselines-dir",
            str(baselines),
            "--priorities",
            str(manifest),
            "--fail-on-priority",
            "P0",
        ]
    )

    assert rc == 0
