import json
import subprocess
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def run_merge(
    tmp_path: Path,
    base: dict[str, Any],
    ours: dict[str, Any],
    theirs: dict[str, Any],
) -> subprocess.CompletedProcess[str]:
    base_path = tmp_path / "base.json"
    ours_path = tmp_path / "ours.json"
    theirs_path = tmp_path / "theirs.json"
    base_path.write_text(json.dumps(base), encoding="utf-8")
    ours_path.write_text(json.dumps(ours), encoding="utf-8")
    theirs_path.write_text(json.dumps(theirs), encoding="utf-8")
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "scripts/merge_json.py",
            "--base",
            str(base_path),
            "--ours",
            str(ours_path),
            "--theirs",
            str(theirs_path),
        ],
        capture_output=True,
        text=True,
    )


def test_merge_non_overlapping_keys(tmp_path: Path) -> None:
    result = run_merge(tmp_path, {"x": 1}, {"x": 1, "a": 2}, {"x": 1, "b": 3})
    assert result.returncode == 0, result.stderr
    merged: dict[str, Any] = json.loads((tmp_path / "ours.json").read_text(encoding="utf-8"))
    assert merged == {"a": 2, "b": 3, "x": 1}


def test_merge_conflicting_key_exits_1(tmp_path: Path) -> None:
    result = run_merge(tmp_path, {"x": 1}, {"x": 2}, {"x": 3})
    assert result.returncode == 1
    assert "x" in (result.stdout + result.stderr)


def test_invalid_json_exits_1(tmp_path: Path) -> None:
    base_path = tmp_path / "base.json"
    ours_path = tmp_path / "ours.json"
    theirs_path = tmp_path / "theirs.json"
    base_path.write_text("{", encoding="utf-8")
    ours_path.write_text("{}", encoding="utf-8")
    theirs_path.write_text("{}", encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "scripts/merge_json.py",
            "--base",
            str(base_path),
            "--ours",
            str(ours_path),
            "--theirs",
            str(theirs_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_deep_merge_nested_keys(tmp_path: Path) -> None:
    result = run_merge(
        tmp_path,
        {"n": {"a": 1}},
        {"n": {"a": 1, "b": 2}},
        {"n": {"a": 1, "c": 3}},
    )
    assert result.returncode == 0, result.stderr
    merged: dict[str, Any] = json.loads((tmp_path / "ours.json").read_text(encoding="utf-8"))
    assert merged == {"n": {"a": 1, "b": 2, "c": 3}}


def test_arrays_are_replaced_not_concatenated(tmp_path: Path) -> None:
    result = run_merge(tmp_path, {"a": [1]}, {"a": [1, 2]}, {"a": [1, 3]})
    assert result.returncode == 1
    result2 = run_merge(tmp_path, {"a": [1]}, {"a": [2]}, {"a": [1]})
    assert result2.returncode == 0
    merged: dict[str, Any] = json.loads((tmp_path / "ours.json").read_text(encoding="utf-8"))
    assert merged == {"a": [2]}
