"""Tests for scripts/check_type_ignores/baseline.py — guarded baseline updates.

Covers the explicit-removal discipline (mirrors scripts/_coverage_model.py,
73bff8c2): disappearing ``files`` keys must be named one-for-one via
``allow_removed``; a value-identical update is a byte-level no-op.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
from scripts.check_type_ignores.baseline import (  # noqa: E402
    BaselineShrinkError,
    build_baseline_dict,
    compare_against_baseline,
    save_baseline,
)
from scripts.check_type_ignores.scanner import (  # noqa: E402
    ROOT,
    ScanResult,
    TypeIgnoreMatch,
    scan_text,
)


def _result_with(files: dict[str, str]) -> ScanResult:
    """Build a ScanResult by scanning synthetic file contents.

    *files* maps repo-relative paths to source text; ``scan_text`` fills
    the result's counters and per-file maps using the real categorization.
    """
    result = ScanResult()
    for rel, text in files.items():
        scan_text(text, ROOT / rel, result)
    return result


def _write_baseline(path: Path, result: ScanResult) -> None:
    save_baseline(result, path)


class TestSaveBaselineRemovalGuard:
    """--update-baseline refuses silent key removals."""

    def test_removal_without_allow_removed_is_refused(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "baseline.json"
        _write_baseline(
            baseline_file,
            _result_with(
                {
                    "tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n",
                    "tests/unit/b.py": "x = f()  # type: ignore[arg-type]\n",
                }
            ),
        )

        # New state: b.py's suppressions are gone (key disappears).
        new = _result_with({"tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n"})

        with pytest.raises(
            BaselineShrinkError, match=r"removed without approval: tests/unit/b\.py"
        ):
            save_baseline(new, baseline_file)

        # The baseline file must be untouched after the refusal.
        stored = json.loads(baseline_file.read_text(encoding="utf-8"))
        assert "tests/unit/b.py" in stored["files"]

    def test_removal_with_exact_allow_removed_succeeds(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "baseline.json"
        _write_baseline(
            baseline_file,
            _result_with(
                {
                    "tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n",
                    "tests/unit/b.py": "x = f()  # type: ignore[arg-type]\n",
                }
            ),
        )

        new = _result_with({"tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n"})
        wrote = save_baseline(new, baseline_file, allow_removed={"tests/unit/b.py"})

        assert wrote is True
        stored = json.loads(baseline_file.read_text(encoding="utf-8"))
        assert set(stored["files"]) == {"tests/unit/a.py"}

    def test_overstated_allow_removed_is_refused(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "baseline.json"
        _write_baseline(
            baseline_file,
            _result_with({"tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n"}),
        )

        # Same state — nothing disappears, but allow_removed names a key.
        same = _result_with({"tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n"})

        with pytest.raises(
            BaselineShrinkError,
            match=r"named in allow_removed but not actually removed",
        ):
            save_baseline(same, baseline_file, allow_removed={"tests/unit/a.py"})

    def test_mismatched_allow_removed_is_refused(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "baseline.json"
        _write_baseline(
            baseline_file,
            _result_with(
                {
                    "tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n",
                    "tests/unit/b.py": "x = f()  # type: ignore[arg-type]\n",
                }
            ),
        )

        # b.py disappears but the allowance names the wrong key.
        new = _result_with({"tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n"})
        with pytest.raises(BaselineShrinkError) as excinfo:
            save_baseline(new, baseline_file, allow_removed={"tests/unit/c.py"})
        msg = str(excinfo.value)
        assert "removed without approval: tests/unit/b.py" in msg
        assert "named in allow_removed but not actually removed: tests/unit/c.py" in msg


class TestSaveBaselineNoop:
    """Value-identical updates must not rewrite the file."""

    def test_identical_update_is_byte_level_noop(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "baseline.json"
        content = {
            "tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n",
        }
        _write_baseline(baseline_file, _result_with(content))
        before = baseline_file.read_bytes()

        wrote = save_baseline(_result_with(content), baseline_file)

        assert wrote is False
        assert baseline_file.read_bytes() == before

    def test_first_write_creates_file(self, tmp_path: Path) -> None:
        baseline_file = tmp_path / "nested" / "baseline.json"
        wrote = save_baseline(
            _result_with({"tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n"}),
            baseline_file,
        )
        assert wrote is True
        assert baseline_file.exists()


class TestCompareTestDelta:
    """The test budget is tracked independently of the total."""

    def test_test_delta_positive_when_test_budget_grows(self) -> None:
        result = _result_with(
            {
                "tests/unit/a.py": (
                    "x = f()  # type: ignore[arg-type]\ny = g()  # type: ignore[arg-type]\n"
                )
            }
        )
        baseline = build_baseline_dict(
            _result_with({"tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n"})
        )
        cmp = compare_against_baseline(result, baseline)
        assert cmp.test_delta == 1
        assert cmp.total_delta == 1
        assert cmp.production_delta == 0

    def test_test_delta_independent_of_production_drop(self) -> None:
        # Test +1 while production -1: total delta is 0, but the frozen
        # test budget must still surface the growth.
        result = _result_with(
            {
                "tests/unit/a.py": (
                    "x = f()  # type: ignore[arg-type]\ny = g()  # type: ignore[arg-type]\n"
                ),
            }
        )
        baseline = build_baseline_dict(
            _result_with({"tests/unit/a.py": "x = f()  # type: ignore[arg-type]\n"})
        )
        # Simulate one production suppression that existed in the baseline
        # and was removed (delta -1) without touching the test numbers.
        baseline["production_total"] = 1
        baseline["total_count"] = baseline["test_total"] + 1

        cmp = compare_against_baseline(result, baseline)
        assert cmp.total_delta == 0
        assert cmp.test_delta == 1
        assert cmp.production_delta == -1


class TestScanTextCategorization:
    """scan_text categorizes by path exactly like the full-tree scan."""

    def test_production_suppression_counted_and_flagged_uncommented(self) -> None:
        result = _result_with(
            {
                "apps/api/narrare/mod.py": "x = f()  # type: ignore[arg-type]\n",
            }
        )
        assert result.production_total == 1
        assert len(result.uncommented_ignores) == 1

    def test_production_suppression_with_reason_not_flagged(self) -> None:
        result = _result_with(
            {
                "apps/api/narrare/mod.py": ("x = f()  # type: ignore[arg-type]  # reason: stubs\n"),
            }
        )
        assert result.production_total == 1
        assert result.uncommented_ignores == []

    def test_naked_ignore_collected(self) -> None:
        result = _result_with({"tests/unit/a.py": "x = f()  # type: ignore\n"})
        assert result.test_total == 1
        assert len(result.naked_ignores) == 1
        assert isinstance(result.naked_ignores[0], TypeIgnoreMatch)
