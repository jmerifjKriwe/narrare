#!/usr/bin/env python3
"""Feature scaffolder — declaration surfaces that are green on arrival.

``scaffold_feature()`` writes only artifacts the architecture gates accept:
the feature document (frontmatter ``paths:`` listing only paths that already
exist or that the same run creates), one test skeleton per named layer, a
Protocol contract stub when ``core`` is named, and a task-report stub. It never
writes ``service.py``, ``router.py``, ``repository.py`` or a frontend
component — those are half-implementations (RULE-20).

Deterministic naming for ``FIND-099``:

* document      ``docs/features/FIND-099.md``
* slug          ``find_099``
* test skeleton ``tests/unit/<layer>/test_find_099.py``
* contract      ``packages/core/narrare_core/find_099/contracts.py`` (core only)
* report        ``docs/superpowers/plans/reports/<UTC date>-find_099.md``

Exit codes: ``0`` written, ``1`` a target path already exists (nothing is
written), ``2`` invalid input or an unwired surface.

``with_intent`` is part of the public signature but raises
``NotImplementedError`` until the intent-surface task (T12b) fills it; it is
never silently ignored.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

EXISTING_ID_EXIT = 1
GATE_FAILURE_EXIT = 2

LAYERS: tuple[str, ...] = ("core", "api", "web")

_FEATURE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+$")


def _slug(feature_id: str) -> str:
    """Return the snake_case path fragment for a feature id."""
    return re.sub(r"[^a-z0-9]+", "_", feature_id.lower()).strip("_")


def _protocol_name(feature_id: str) -> str:
    """Return the contract Protocol name derived from the feature id."""
    return "".join(part.capitalize() for part in _slug(feature_id).split("_")) + "Protocol"


def _utc_date() -> str:
    """Return today's UTC date in ISO form, used in the report file name."""
    return datetime.now(UTC).date().isoformat()


def _require_valid_feature_id(feature_id: str) -> None:
    """Reject ids that cannot map onto the documented naming scheme."""
    if _FEATURE_ID_RE.fullmatch(feature_id):
        return
    print(
        f"scaffold_feature: invalid feature id '{feature_id}' — expected an id such as FIND-099",
        file=sys.stderr,
    )
    raise SystemExit(GATE_FAILURE_EXIT)


def _normalize_layers(layers: tuple[str, ...]) -> tuple[str, ...]:
    """Deduplicate layers in input order and reject names outside the vocabulary."""
    unique = tuple(dict.fromkeys(layers))
    unknown = [layer for layer in unique if layer not in LAYERS]
    if not unique or unknown:
        known = ", ".join(LAYERS)
        shown = ", ".join(unknown) if unknown else "<none>"
        print(
            f"scaffold_feature: unsupported layer(s): {shown} — choose from {known}",
            file=sys.stderr,
        )
        raise SystemExit(GATE_FAILURE_EXIT)
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
    if not existing:
        return
    listing = "\n  ".join(path.as_posix() for path in existing)
    print(
        "scaffold_feature: refusing to write — these paths already exist:\n  " + listing,
        file=sys.stderr,
    )
    raise SystemExit(EXISTING_ID_EXIT)


def _write(root: Path, relative: Path, text: str) -> Path:
    """Write one generated file, creating parent directories as needed."""
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _feature_document(
    feature_id: str,
    layers: tuple[str, ...],
    paths: list[Path],
    root: Path,
    report_date: str,
) -> str:
    """Render the feature document with a verified frontmatter path list."""
    document = paths[0]
    existing = [path for path in paths if path == document or (root / path).exists()]
    path_lines = "\n".join(f"  - {path.as_posix()}" for path in existing)
    layer_list = ", ".join(layers)
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

**Layers scaffolded:** {layer_list}

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


def _package_init(feature_id: str) -> str:
    """Render the feature package initialiser."""
    return f'"""{feature_id} feature package (scaffolded)."""\n'


def _contract_stub(feature_id: str) -> str:
    """Render a Protocol-only contract stub (RULE-03)."""
    name = _protocol_name(feature_id)
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
) -> list[Path]:
    """Write the declaration surfaces for *feature_id* under *root*.

    Returns the written paths; exits with ``EXISTING_ID_EXIT`` without writing
    when a target exists. ``with_intent`` is reserved for T12b.
    """
    if with_intent is not None:
        raise NotImplementedError(
            "scaffold_feature(with_intent=...) lands with T12b; no intent surface was written"
        )
    _require_valid_feature_id(feature_id)
    normalized = _normalize_layers(layers)
    report_date = _utc_date()
    planned = _planned_paths(feature_id, normalized, report_date)
    _refuse_existing(planned, root)

    slug = _slug(feature_id)
    contents: dict[Path, str] = {}
    if "core" in normalized:
        package = Path("packages") / "core" / "narrare_core" / slug
        contents[package / "__init__.py"] = _package_init(feature_id)
        contents[package / "contracts.py"] = _contract_stub(feature_id)
    for layer in normalized:
        contents[Path("tests") / "unit" / layer / f"test_{slug}.py"] = _test_skeleton(
            feature_id, layer
        )
    contents[planned[-1]] = _report_stub(feature_id, normalized, report_date)

    written = [_write(root, relative, text) for relative, text in contents.items()]
    document = _feature_document(feature_id, normalized, planned, root, report_date)
    written.append(_write(root, planned[0], document))
    return written


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the CLI contract ``<id> <layer...> [--with-intent NAME] [--root PATH]``."""
    parser = argparse.ArgumentParser(
        description="Scaffold the declaration surfaces of a new feature.",
        epilog="Green on arrival — never service, router, repository or component stubs (RULE-20).",
    )
    parser.add_argument("feature_id", metavar="id", help="feature id, e.g. FIND-099")
    parser.add_argument(
        "layers",
        nargs="+",
        choices=LAYERS,
        metavar="layer",
        help="layer(s) to scaffold: core, api, web",
    )
    parser.add_argument("--with-intent", metavar="NAME", help="reserved for T12b")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI, printing each written path and returning the exit code."""
    args = _parse_args(argv)
    try:
        written = scaffold_feature(
            args.feature_id,
            tuple(args.layers),
            args.root,
            with_intent=args.with_intent,
        )
    except NotImplementedError as exc:
        print(f"scaffold_feature: {exc}", file=sys.stderr)
        return GATE_FAILURE_EXIT
    for path in written:
        print(f"created {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
