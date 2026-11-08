from __future__ import annotations

import json
import os
import subprocess  # nosec B404
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
    return subprocess.run(  # noqa: S603  # nosec B603
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
    assert merged == {"x": 1, "a": 2, "b": 3}


def test_merge_conflicting_key_exits_1(tmp_path: Path) -> None:
    result = run_merge(tmp_path, {"x": 1}, {"x": 2}, {"x": 3})
    assert result.returncode == 1
    assert "x" in (result.stdout + result.stderr)


def test_delete_vs_modify_conflicts(tmp_path: Path) -> None:
    result = run_merge(tmp_path, {"b": 2}, {}, {"b": 3})
    assert result.returncode == 1
    assert "b" in (result.stdout + result.stderr)


def test_delete_vs_unchanged_keeps_the_deletion(tmp_path: Path) -> None:
    result = run_merge(tmp_path, {"b": 2}, {}, {"b": 2})
    assert result.returncode == 0, result.stderr
    merged: dict[str, Any] = json.loads((tmp_path / "ours.json").read_text(encoding="utf-8"))
    assert merged == {}


def test_invalid_json_exits_1(tmp_path: Path) -> None:
    base_path = tmp_path / "base.json"
    ours_path = tmp_path / "ours.json"
    theirs_path = tmp_path / "theirs.json"
    base_path.write_text("{", encoding="utf-8")
    ours_path.write_text("{}", encoding="utf-8")
    theirs_path.write_text("{}", encoding="utf-8")
    result = subprocess.run(  # noqa: S603  # nosec B603
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


def test_generated_mode_writes_regenerated_content_to_ours(tmp_path: Path) -> None:
    generated = tmp_path / "web" / "lib" / "generated"
    generated.mkdir(parents=True)
    source = generated / "routes.ts"
    source.write_text("stale\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    just = bin_dir / "just"
    just.write_text(
        '#!/bin/sh\nprintf "regenerated\\n" > web/lib/generated/routes.ts\n',
        encoding="utf-8",
    )
    just.chmod(0o755)

    ours = tmp_path / "ours.ts"
    ours.write_text("ours\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603  # nosec B603
        [
            sys.executable,
            "scripts/merge_json.py",
            "--generated",
            "--path",
            "web/lib/generated/routes.ts",
            "--root",
            str(tmp_path),
            "--base",
            str(ours),
            "--ours",
            str(ours),
            "--theirs",
            str(ours),
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
    )

    assert result.returncode == 0, result.stderr
    assert ours.read_text(encoding="utf-8") == "regenerated\n"


def test_generated_mode_does_not_require_json_inputs(tmp_path: Path) -> None:
    generated = tmp_path / "web" / "lib" / "generated"
    generated.mkdir(parents=True)
    (generated / "routes.ts").write_text("stale\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    just = bin_dir / "just"
    just.write_text(
        '#!/bin/sh\nprintf "regenerated\\n" > web/lib/generated/routes.ts\n',
        encoding="utf-8",
    )
    just.chmod(0o755)

    ours = tmp_path / "ours.ts"
    ours.write_text("ours\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603  # nosec B603
        [
            sys.executable,
            "scripts/merge_json.py",
            "--generated",
            "--path",
            "web/lib/generated/routes.ts",
            "--root",
            str(tmp_path),
            "--base",
            "/does/not/exist",
            "--ours",
            str(ours),
            "--theirs",
            "/does/not/exist",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
    )

    assert result.returncode == 0, result.stderr
    assert ours.read_text(encoding="utf-8") == "regenerated\n"
