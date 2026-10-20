#!/usr/bin/env python3
"""Feature scaffolder — declaration surfaces that are green on arrival.

``scaffold_feature()`` writes only artifacts the architecture gates accept
(feature document, per-layer test skeletons, a core Protocol stub and a report
stub), never service/router/repository/component stubs (RULE-20).

``with_intent=NAME`` (with ``category`` and ``mode``) also writes the eight
intent declaration surfaces. Their planning, parsers and renderers live in
:mod:`scripts.scaffold_intent` (RULE-04 split); this module keeps the feature
artifacts, orchestration and the CLI.

Writes are atomic; a duplicate intent exits 1 untouched, invalid input or a
failed write exits 2 after restoring every touched file.

A successful write is not a successful scaffold: the post-condition runs before
returning. The intent parity gate always runs (it works on a mirror tree too),
and the four scoped architecture checks run when *root* is this repository.
Any failure exits 2 after restoring every file written by the run, so a
scaffold either arrives gate-green or leaves the tree exactly as it was.
"""

from __future__ import annotations

import argparse
import re
import subprocess  # nosec B404 - scoped gate scripts via sys.executable, fixed argv
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_intent_parity import collect_facts, find_disagreements  # noqa: E402
from scripts.scaffold_intent import (  # noqa: E402
    EXISTING_ID_EXIT,
    GATE_FAILURE_EXIT,
    fail,
    plan_intent,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["EXISTING_ID_EXIT", "GATE_FAILURE_EXIT", "main", "scaffold_feature"]

LAYERS: tuple[str, ...] = ("core", "api", "web")

# Scoped architecture checks, run only when writing into this repository. They
# resolve their own paths from the invoked script, so running ``root/<script>``
# under ``cwd=root`` points them at *root*.
_SCOPED_CHECKS: tuple[str, ...] = (
    "scripts/check_prompt_structure.py",
    "scripts/check_prompt_surface_contract.py",
    "scripts/check_locale_sync.py",
    "scripts/check_feature_path_accuracy.py",
)

_FEATURE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+$")


def _slug(feature_id: str) -> str:
    """Return the snake_case path fragment for a feature id."""
    return re.sub(r"[^a-z0-9]+", "_", feature_id.lower()).strip("_")


def _contract_stub(feature_id: str) -> str:
    """Render a Protocol-only contract stub (RULE-03)."""
    name = "".join(part.capitalize() for part in _slug(feature_id).split("_")) + "Protocol"
    return f'''"""Contract stub for {feature_id} (RULE-03).

The Protocol is the boundary the feature's service implements and the router
consumes. Declare methods here before the implementation exists so neither
side depends on a concrete repository.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class {name}(Protocol):
    """Boundary for the {feature_id} feature.

    Add the feature's method signatures here first; the service and the router
    then depend on this Protocol rather than on each other.
    """
'''


def _require_valid_feature_id(feature_id: str) -> None:
    """Reject ids that cannot map onto the documented naming scheme."""
    if not _FEATURE_ID_RE.fullmatch(feature_id):
        fail(f"invalid feature id '{feature_id}' — expected an id such as FIND-099")


def _normalize_layers(layers: tuple[str, ...]) -> tuple[str, ...]:
    """Deduplicate layers in input order and reject names outside the vocabulary."""
    unique = tuple(dict.fromkeys(layers))
    unknown = [layer for layer in unique if layer not in LAYERS]
    if not unique or unknown:
        shown = ", ".join(unknown) if unknown else "<none>"
        fail(f"unsupported layer(s): {shown} — choose from {', '.join(LAYERS)}")
    return unique


def _planned_paths(feature_id: str, layers: tuple[str, ...], report_date: str) -> list[Path]:
    """Return every path the run would write; the document is first, report last."""
    slug = _slug(feature_id)
    paths = [Path("docs") / "features" / f"{feature_id}.md"]
    paths.extend(Path("tests") / "unit" / layer / f"test_{slug}.py" for layer in layers)
    if "core" in layers:
        package = Path("packages") / "core" / "narrare_core" / slug
        paths.extend((package / "__init__.py", package / "contracts.py"))
    paths.append(Path("docs") / "superpowers" / "plans" / "reports" / f"{report_date}-{slug}.md")
    return paths


def _refuse_existing(paths: list[Path], root: Path) -> None:
    """Exit before writing anything when any target path already exists."""
    existing = [path for path in paths if (root / path).exists()]
    if existing:
        listing = "\n  ".join(path.as_posix() for path in existing)
        print(
            "scaffold_feature: refusing to write — these paths already exist:\n  " + listing,
            file=sys.stderr,
        )
        raise SystemExit(EXISTING_ID_EXIT)


def _restore(snapshots: dict[Path, str | None]) -> None:
    """Return every snapshotted file to its pre-run state.

    A failing restore is reported rather than raised: the caller is already on
    the failure path and must keep its exit code.
    """
    failures: list[str] = []
    for target, original in snapshots.items():
        try:
            if original is None:
                target.unlink(missing_ok=True)
            else:
                target.write_text(original, encoding="utf-8")
        except OSError as exc:
            failures.append(f"{target}: {exc}")
    if failures:
        print(
            "scaffold_feature: could not restore every file:\n  " + "\n  ".join(failures),
            file=sys.stderr,
        )


def _write_all(contents: dict[Path, str], root: Path) -> tuple[list[Path], dict[Path, str | None]]:
    """Write every file, returning the written paths and their pre-run snapshots."""
    snapshots: dict[Path, str | None] = {}
    written: list[Path] = []
    try:
        for relative, text in contents.items():
            target = root / relative
            snapshots[target] = target.read_text(encoding="utf-8") if target.exists() else None
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            written.append(target)
    except OSError as exc:
        _restore(snapshots)
        fail(f"write failed ({exc}); restored {len(snapshots)} file(s)")
    return written, snapshots


def _run_check(script: str, root: Path) -> subprocess.CompletedProcess[str]:
    """Run one scoped architecture check against *root* and capture its output."""
    return subprocess.run(  # noqa: S603  # nosec B603 — fixed repository script, no shell
        [sys.executable, str(root / script)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _post_condition(root: Path) -> None:
    """Refuse a scaffold the gates reject; the caller restores on exit 2."""
    try:
        disagreements = find_disagreements(collect_facts(root))
    except RuntimeError as exc:
        fail(f"post-condition could not read the declaration surfaces: {exc}")
    if disagreements:
        listing = "\n  ".join(disagreements)
        fail(f"intent parity gate rejected the scaffold:\n  {listing}")
    if root.resolve() != _ROOT:
        return
    for script in _SCOPED_CHECKS:
        result = _run_check(script, root)
        if result.returncode == 0:
            continue
        # Enough of the check's own report to name the offending prompt or path.
        tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-8:])
        fail(f"{script} failed (exit {result.returncode}) after scaffolding:\n{tail}")


def _feature_document(
    feature_id: str, layers: tuple[str, ...], paths: list[Path], root: Path, report_date: str
) -> str:
    """Render the feature document with a verified frontmatter path list."""
    document = paths[0]
    existing = [path for path in paths if path == document or (root / path).exists()]
    path_lines = "\n".join(f"  - {path.as_posix()}" for path in existing)
    return f"""---
id: {feature_id}
title: "{feature_id} — feature scaffold"
status: planned
area: unassigned
mvp: false
paths:
{path_lines}
---

# [{feature_id}] — Feature scaffold

## What it does

Describe the writer-facing behaviour this feature adds in one or two sentences.

## Why it exists

Name the friction this removes and what changes for the writer.

## How it works (Technical)

**Layers scaffolded:** {", ".join(layers)}

Record the entry point, service boundary and contract methods; depend on the
contract, never a concrete repository.

## UX Requirements

Describe the interaction type, streaming, loading and error states.

## Constraints & Edge Cases

List what the feature cannot do, its failure modes and its size limits.

## Open questions

Record unresolved design questions here; remove this section once answered.

## Status & History

- {report_date} — Added by the feature scaffolder.
"""


def _test_skeleton(feature_id: str, layer: str) -> str:
    """Render a test skeleton that is green as soon as the scaffold lands."""
    return f'''"""Scaffolded tests for {feature_id} — {layer} layer.

Generated by ``scripts/scaffold_feature.py``. Replace the scaffold assertion
with behaviour tests as the feature lands; the document check stays as the
registry anchor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.mutation_inert


def test_{_slug(feature_id)}_document_exists() -> None:
    """The feature document created with this skeleton is present."""
    root = Path(__file__).resolve().parents[3]
    assert (root / "docs" / "features" / "{feature_id}.md").is_file()
'''


def _report_stub(feature_id: str, layers: tuple[str, ...], report_date: str) -> str:
    """Render the task-report stub following the report contract."""
    return f"""# {feature_id} — Implementation report

- **Date:** {report_date}
- **Feature:** {feature_id}
- **Status:** scaffolded — implementation not started
- **Feature document:** `docs/features/{feature_id}.md`
- **Layers:** {", ".join(layers)}

## 1. Scope

Describe the behaviour this feature adds and the layer boundaries it crosses.

## 2. Verification

Record the commands that prove the implementation, with the raw result tails.

## 3. Concerns

Record deviations, open questions and follow-up work.
"""


def scaffold_feature(
    feature_id: str,
    layers: tuple[str, ...],
    root: Path,
    *,
    with_intent: str | None = None,
    category: str | None = None,
    mode: str | None = None,
) -> list[Path]:
    """Write the declaration surfaces for *feature_id* under *root*.

    Returns the written paths; exits ``1`` without writing when a target or the
    intent already exists, and ``2`` on invalid input, a failed write or a failed
    post-condition (after restoring every file the run touched).
    """
    _require_valid_feature_id(feature_id)
    normalized = _normalize_layers(layers)
    if with_intent is None and (category is not None or mode is not None):
        fail("--category and --mode are only valid together with --with-intent")
    intent_writes = plan_intent(with_intent, category, mode, root) if with_intent else {}
    report_date = datetime.now(UTC).date().isoformat()
    planned = _planned_paths(feature_id, normalized, report_date)
    # Existing surfaces are edited in place by plan_intent; only new prompt files
    # are targets that must not exist yet.
    new_intent = [
        path for path in intent_writes if path not in planned and not (root / path).exists()
    ]
    _refuse_existing(planned + new_intent, root)

    slug = _slug(feature_id)
    contents: dict[Path, str] = {}
    if "core" in normalized:
        package = Path("packages") / "core" / "narrare_core" / slug
        contents[package / "__init__.py"] = f'"""{feature_id} feature package (scaffolded)."""\n'
        contents[package / "contracts.py"] = _contract_stub(feature_id)
    for layer in normalized:
        contents[Path("tests") / "unit" / layer / f"test_{slug}.py"] = _test_skeleton(
            feature_id, layer
        )
    contents[planned[-1]] = _report_stub(feature_id, normalized, report_date)
    contents.update(intent_writes)
    contents[planned[0]] = _feature_document(feature_id, normalized, planned, root, report_date)
    written, snapshots = _write_all(contents, root)
    try:
        _post_condition(root)
    except SystemExit:
        _restore(snapshots)
        print(
            f"scaffold_feature: restored {len(snapshots)} file(s) after the post-condition failed",
            file=sys.stderr,
        )
        raise
    return written


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse ``<id> <layer...> [--with-intent NAME --category C --mode M] [--root PATH]``."""
    parser = argparse.ArgumentParser(
        description="Scaffold the declaration surfaces of a new feature.",
        epilog="Green on arrival — never service, router, repository or component stubs (RULE-20).",
    )
    parser.add_argument("feature_id", metavar="id", help="feature id, e.g. FIND-099")
    parser.add_argument(
        "layers", nargs="+", choices=LAYERS, metavar="layer", help="layer(s): core, api, web"
    )
    parser.add_argument(
        "--with-intent",
        metavar="NAME",
        help="also declare the eight intent surfaces for NAME (requires --category and --mode)",
    )
    parser.add_argument(
        "--category",
        metavar="CATEGORY",
        help="model category for --with-intent: writing, analysis, kb, planning, …",
    )
    parser.add_argument("--mode", metavar="MODE", help="prompt mode name for --with-intent")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI, printing each written path and returning the exit code."""
    args = _parse_args(argv)
    written = scaffold_feature(
        args.feature_id,
        tuple(args.layers),
        args.root,
        with_intent=args.with_intent,
        category=args.category,
        mode=args.mode,
    )
    for path in written:
        print(f"created {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
