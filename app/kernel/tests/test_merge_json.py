from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import pytest

from scripts import merge_json

if TYPE_CHECKING:
    from pathlib import Path


def test_merge_non_overlapping_keys() -> None:
    merged = merge_json.deep_merge({"x": 1}, {"x": 1, "a": 2}, {"x": 1, "b": 3})
    assert merged == {"x": 1, "a": 2, "b": 3}


def test_merge_conflicting_key_raises() -> None:
    with pytest.raises(merge_json.MergeConflictError, match="x"):
        merge_json.deep_merge({"x": 1}, {"x": 2}, {"x": 3})


def test_delete_vs_modify_conflicts() -> None:
    with pytest.raises(merge_json.MergeConflictError, match="b"):
        merge_json.deep_merge({"b": 2}, {}, {"b": 3})


def test_delete_vs_unchanged_keeps_the_deletion() -> None:
    assert merge_json.deep_merge({"b": 2}, {}, {"b": 2}) == {}


def test_deep_merge_nested_keys() -> None:
    merged = merge_json.deep_merge(
        {"n": {"a": 1}},
        {"n": {"a": 1, "b": 2}},
        {"n": {"a": 1, "c": 3}},
    )
    assert merged == {"n": {"a": 1, "b": 2, "c": 3}}


def test_arrays_are_replaced_not_concatenated() -> None:
    with pytest.raises(merge_json.MergeConflictError):
        merge_json.deep_merge({"a": [1]}, {"a": [1, 2]}, {"a": [1, 3]})
    assert merge_json.deep_merge({"a": [1]}, {"a": [2]}, {"a": [1]}) == {"a": [2]}


def test_invalid_json_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_path = tmp_path / "base.json"
    ours_path = tmp_path / "ours.json"
    theirs_path = tmp_path / "theirs.json"
    base_path.write_text("{", encoding="utf-8")
    ours_path.write_text("{}", encoding="utf-8")
    theirs_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "merge_json.py",
            "--base",
            str(base_path),
            "--ours",
            str(ours_path),
            "--theirs",
            str(theirs_path),
        ],
    )
    assert merge_json.main() == 1


def test_generated_mode_writes_regenerated_content_to_ours(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ours = tmp_path / "ours.ts"
    ours.write_text("stale\n", encoding="utf-8")

    def fake_regenerate(root: Path, path: str, target: Path) -> None:
        target.write_text("regenerated\n", encoding="utf-8")

    monkeypatch.setattr(merge_json, "_regenerate", fake_regenerate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "merge_json.py",
            "--generated",
            "--path",
            "web/lib/generated/routes.ts",
            "--base",
            str(ours),
            "--ours",
            str(ours),
            "--theirs",
            str(ours),
        ],
    )
    assert merge_json.main() == 0
    assert ours.read_text(encoding="utf-8") == "regenerated\n"


def test_generated_mode_does_not_require_json_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ours = tmp_path / "ours.ts"
    ours.write_text("stale\n", encoding="utf-8")

    def fake_regenerate(root: Path, path: str, target: Path) -> None:
        target.write_text("regenerated\n", encoding="utf-8")

    monkeypatch.setattr(merge_json, "_regenerate", fake_regenerate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "merge_json.py",
            "--generated",
            "--path",
            "web/lib/generated/routes.ts",
            "--base",
            "/does/not/exist",
            "--ours",
            str(ours),
            "--theirs",
            "/does/not/exist",
        ],
    )
    assert merge_json.main() == 0
    assert ours.read_text(encoding="utf-8") == "regenerated\n"


def test_json_output_keeps_utf8_and_existing_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "base.json"
    ours = tmp_path / "ours.json"
    theirs = tmp_path / "theirs.json"
    base.write_text(json.dumps({"b": 1, "a": 1}), encoding="utf-8")
    ours.write_text(json.dumps({"b": 1, "a": 1}), encoding="utf-8")
    theirs.write_text(json.dumps({"b": 1, "a": 1, "c": "ä"}), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "merge_json.py",
            "--base",
            str(base),
            "--ours",
            str(ours),
            "--theirs",
            str(theirs),
        ],
    )
    assert merge_json.main() == 0
    text = ours.read_text(encoding="utf-8")
    assert '"ä"' in text
    assert text.index('"b"') < text.index('"a"') < text.index('"c"')


def test_generated_regeneration_failure_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ours = tmp_path / "ours.ts"
    ours.write_text("stale\n", encoding="utf-8")

    def fail_regenerate(root: Path, path: str, target: Path) -> None:
        raise RuntimeError("generator failed")

    monkeypatch.setattr(merge_json, "_regenerate", fail_regenerate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "merge_json.py",
            "--generated",
            "--path",
            "web/lib/generated/routes.ts",
            "--ours",
            str(ours),
            "--base",
            "/does/not/exist",
            "--theirs",
            "/does/not/exist",
        ],
    )
    assert merge_json.main() == 1


def test_generated_paths_are_allowlisted() -> None:
    assert merge_json.allowed_generated_path("web/lib/generated/routes.ts")
    assert merge_json.allowed_generated_path("web/lib/api/openapi.json")
    assert not merge_json.allowed_generated_path("../etc/passwd")
    assert not merge_json.allowed_generated_path("web/lib/api/other.json")
