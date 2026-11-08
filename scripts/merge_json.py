#!/usr/bin/env python3
"""Merge driver for JSON files and generated artefacts.

Usage:
    python scripts/merge_json.py --base O --ours A --theirs B
    python scripts/merge_json.py --generated --path P --base O --ours A --theirs B

Exit 0 on a successful merge (result written to --ours), 1 on a conflict
or unreadable input.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import cast


class MergeConflictError(Exception):
    def __init__(self, path: str):
        super().__init__(path)
        self.path = path


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return cast("dict[str, object]", {})


def _merge_dicts(
    base: dict[str, object],
    ours: dict[str, object],
    theirs: dict[str, object],
    prefix: str,
) -> dict[str, object]:
    result: dict[str, object] = {}

    def merge_key(key: str) -> None:
        child_prefix = f"{prefix}.{key}" if prefix else key
        base_has = key in base
        ours_has = key in ours
        theirs_has = key in theirs
        base_value = base.get(key) if base_has else None
        ours_value = ours.get(key) if ours_has else None
        theirs_value = theirs.get(key) if theirs_has else None

        if ours_has and not theirs_has:
            if base_has:
                if ours_value == base_value:
                    return
                raise MergeConflictError(child_prefix)
            result[key] = ours_value
            return
        if theirs_has and not ours_has:
            if base_has:
                if theirs_value == base_value:
                    return
                raise MergeConflictError(child_prefix)
            result[key] = theirs_value
            return
        if ours_value == theirs_value:
            result[key] = ours_value
            return
        if base_has and ours_value == base_value:
            result[key] = theirs_value
            return
        if base_has and theirs_value == base_value:
            result[key] = ours_value
            return
        result[key] = deep_merge(base_value, ours_value, theirs_value, child_prefix)

    # Keep the order the branch already carries, then append keys only the
    # other side added. Re-sorting every key would rewrite whole catalogs.
    for key in ours:
        merge_key(key)
    for key in theirs:
        if key not in ours:
            merge_key(key)
    return result


def deep_merge(base: object, ours: object, theirs: object, prefix: str = "") -> object:
    if isinstance(ours, dict) and isinstance(theirs, dict):
        return _merge_dicts(
            _as_dict(base),
            _as_dict(cast("dict[str, object]", ours)),
            _as_dict(cast("dict[str, object]", theirs)),
            prefix,
        )

    if ours == theirs:
        return cast("object", ours)
    if base == ours:
        return theirs
    if base == theirs:
        return cast("object", ours)
    raise MergeConflictError(prefix or "<root>")


def allowed_generated_path(path: str) -> bool:
    normalized = Path(path)
    if normalized.is_absolute() or ".." in normalized.parts:
        return False
    return (
        path == "web/lib/api/openapi.json"
        or path == "web/lib/api/schema.d.ts"
        or path.startswith("web/lib/generated/")
    )


def _regenerate(root: Path, path: str, ours: Path) -> None:
    """Regenerate in-process; no shell, no external executable.

    ``schema.d.ts`` is produced by the Node openapi-typescript step, which has
    no Python equivalent. It stays manual: the driver refuses and the developer
    runs ``just generate`` after the merge.
    """
    if not allowed_generated_path(path):
        raise RuntimeError(f"{path} is not a generated merge-driver path")
    if path.endswith("schema.d.ts"):
        raise RuntimeError(
            "schema.d.ts needs `just generate`; the Node step has no in-process path"
        )
    previous = Path.cwd()
    os.chdir(root)
    try:
        if path == "web/lib/api/openapi.json":
            from scripts.export_openapi import main as export_main

            export_main()
        else:
            from scripts.generate_capabilities import main as generate_main

            generate_main()
    finally:
        os.chdir(previous)
    source = root / path
    if not source.is_file():
        raise FileNotFoundError(f"generator did not write {path}")
    ours.write_bytes(source.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--ours", required=True)
    parser.add_argument("--theirs", required=True)
    parser.add_argument("--generated", action="store_true")
    parser.add_argument("--path")
    parser.add_argument("--root")
    args = parser.parse_args()

    # Generated files are TypeScript/JSON artefacts whose only source of truth
    # is the generator. Do not parse them: regenerate and write %A.
    if args.generated:
        if not args.path:
            print("merge_json: --generated requires --path <%P>", file=sys.stderr)
            return 1
        try:
            root = Path(args.root) if args.root else Path.cwd()
            _regenerate(root, args.path, Path(args.ours))
        except (OSError, RuntimeError) as exc:
            print(f"merge_json: regeneration failed: {exc}", file=sys.stderr)
            return 1
        return 0

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

    try:
        merged = deep_merge(base, ours, theirs)
    except MergeConflictError as exc:
        print(f"merge_json: conflict at {exc.path}", file=sys.stderr)
        return 1

    Path(args.ours).write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
