#!/usr/bin/env python3
"""Merge driver for JSON files and generated artefacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast


class MergeConflictError(Exception):
    def __init__(self, path: str):
        super().__init__(path)
        self.path = path


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return cast("dict[str, object]", {})


def deep_merge(base: object, ours: object, theirs: object, prefix: str = "") -> Any:
    if isinstance(ours, dict) and isinstance(theirs, dict):
        base_dict = _as_dict(base)
        ours_dict = cast("dict[str, object]", ours)
        theirs_dict = cast("dict[str, object]", theirs)
        result: dict[str, object] = {}
        keys = set(ours_dict) | set(theirs_dict)
        for key in sorted(keys):
            child_prefix = f"{prefix}.{key}" if prefix else key
            base_has = key in base_dict
            ours_has = key in ours_dict
            theirs_has = key in theirs_dict
            base_value = base_dict.get(key) if base_has else None
            ours_value = ours_dict.get(key) if ours_has else None
            theirs_value = theirs_dict.get(key) if theirs_has else None

            if ours_has and not theirs_has:
                if base_has and ours_value == base_value:
                    continue
                result[key] = ours_value
                continue
            if theirs_has and not ours_has:
                if base_has and theirs_value == base_value:
                    continue
                result[key] = theirs_value
                continue
            if ours_value == theirs_value:
                result[key] = ours_value
                continue
            if base_has and ours_value == base_value:
                result[key] = theirs_value
                continue
            if base_has and theirs_value == base_value:
                result[key] = ours_value
                continue
            try:
                result[key] = deep_merge(base_value, ours_value, theirs_value, child_prefix)
            except MergeConflictError:
                raise MergeConflictError(child_prefix) from None
        return result

    if ours == theirs:
        return cast("Any", ours)
    if base == ours:
        return theirs
    if base == theirs:
        return cast("Any", ours)
    raise MergeConflictError(prefix or "<root>")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--ours", required=True)
    parser.add_argument("--theirs", required=True)
    parser.add_argument("--generated", action="store_true")
    args = argparse.Namespace()
    # parse into a typed namespace manually to keep pyright happy
    args = parser.parse_args()

    try:
        base_text = Path(args.base).read_text(encoding="utf-8")
        ours_text = Path(args.ours).read_text(encoding="utf-8")
        theirs_text = Path(args.theirs).read_text(encoding="utf-8")
        base: object
        ours: object
        theirs: object
        base = cast("object", json.loads(base_text)) if base_text.strip() else {}
        ours = cast("object", json.loads(ours_text)) if ours_text.strip() else {}
        theirs = cast("object", json.loads(theirs_text)) if theirs_text.strip() else {}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"merge_json: cannot read/parse input: {exc}", file=sys.stderr)
        return 1

    if args.generated:
        print("merge_json: generated files require manual resolution", file=sys.stderr)
        return 1

    try:
        merged = deep_merge(cast("object", base), cast("object", ours), cast("object", theirs))
    except MergeConflictError as exc:
        print(f"merge_json: conflict at {exc.path}", file=sys.stderr)
        return 1

    Path(args.ours).write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
