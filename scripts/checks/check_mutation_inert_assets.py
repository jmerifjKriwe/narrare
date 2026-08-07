#!/usr/bin/env python3
"""Convention gate: repo-asset-reading tests must be ``mutation_inert``.

Problem
-------
MutMut runs the test suite from inside a sandbox under ``mutants/``. There
``Path(__file__).resolve().parents[N]`` resolves to a different root than the
real repository root (typically ``<repo>/mutants`` instead of ``<repo>``).
Tests that read committed repo-root assets — YAML manifests, bundled prompt
templates, ``pyproject.toml``, … — therefore crash inside the MutMut sandbox
with ``Failed: Missing: <repo>/mutants/scripts/...`` and, because MutMut is
invoked with ``-x`` (stop after first failure), abort the whole monthly
mutation run (see GitHub issue #146).

Convention
----------
Such structure/convention tests are mutations-invariant by construction
(they assert on committed file contents, so no source-code mutant can ever
kill them). The established repo convention is to mark them with
``@pytest.mark.mutation_inert`` so that MutMut's
``-m "not mutation_inert"`` test-selection filter (see
``scripts/run_mutmut.py``) excludes them. Four reference tests already
follow this convention; two ``dialogue_coach`` asset tests regressed and
silently crashed the August 2026 monthly run because the convention was
not machine-enforced.

Enforcement
-----------
This checker closes that "documented ≠ implemented" gap (CR-04 lesson):
it deterministically detects asset-reading tests under the MutMut test
scopes (``tests/unit/core/``, ``tests/unit/api/`` — matching SCOPE_CORE /
SCOPE_API in ``scripts/run_mutmut.py``) and fails if any asset-reading
test class or function lacks the ``mutation_inert`` marker.

Heuristic (chosen for precision, see note below)
-----------------------------------------------
A test file is "asset-reading" when **both** hold:

1. it contains a ``.parents[N]`` subscript access (reaching above the
   test's own directory), AND
2. it references a committed repo-root asset via a string literal that
   matches a known out-of-tests asset indicator (``scripts/architecture``,
   ``_bundled``, ``pyproject.toml``, ``packages/core``, ``apps/api``,
   ``adoption-registry``, ``prompt-surface-manifest``, …).

Condition (2) is what distinguishes a true repo-root asset read (crashes
MutMut — the asset is not copied into ``mutants/``) from a within-tests
data-file read (does not crash MutMut — the file is copied along with the
test tree). A pure ``parents[N]`` AST check would over-flag the latter.

Per-test attribution then identifies which specific test classes /
functions actually read the asset (directly, via a module-level constant,
or via an asset-reading helper) and verifies the marker is present at the
function, class, or module (``pytestmark``) level.

Exit codes:
    0: all asset-reading tests carry the marker.
    1: at least one asset-reading test lacks the marker.

Usage:
    python scripts/checks/check_mutation_inert_assets.py        # human-readable
    python scripts/checks/check_mutation_inert_assets.py --json # CI JSON
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repository root

# MutMut test scopes — MUST match scripts/run_mutmut.py SCOPE_CORE / SCOPE_API
# (the ``pytest_add_cli_args_test_selection`` directories). Keep in sync.
DEFAULT_SCOPES: tuple[str, ...] = ("tests/unit/core/", "tests/unit/api/")

# String-literal substrings that indicate a committed repo-root asset — i.e.
# a file that lives OUTSIDE the test tree and is therefore NOT copied into
# MutMut's ``mutants/`` sandbox. Their presence combined with a ``parents[N]``
# access is the precision filter that avoids false positives on tests reading
# local ``tests/data/`` fixtures.
_REPO_ASSET_INDICATORS: tuple[str, ...] = (
    "scripts/architecture",
    "scripts/checks",
    "_bundled",
    "pyproject.toml",
    "uv.lock",
    "packages/core",
    "packages/web",
    "packages/i18n",
    "apps/api",
    "adoption-registry",
    "prompt-surface-manifest",
)


@dataclass(frozen=True)
class MarkerViolation:
    """One asset-reading test class/function that lacks ``mutation_inert``."""

    file: str
    scope: str  # the test class or standalone function, e.g. "Class" or "test_func"
    line: int
    detail: str

    def as_json(self) -> dict[str, object]:
        return asdict(self)


def _display(path: Path) -> str:
    """Return a stable repo-relative display path, tolerating synthetic paths."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _has_parents_subscript(node: ast.AST) -> bool:
    """True if *node*'s tree contains any ``.parents[N]`` subscript access."""
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Subscript)
            and isinstance(n.value, ast.Attribute)
            and n.value.attr == "parents"
        ):
            return True
    return False


def _string_literal_blob(tree: ast.AST) -> str:
    """Concatenate all string-literal values in *tree* for substring matching."""
    parts: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            parts.append(n.value)
    return "\n".join(parts)


def _references_repo_asset(tree: ast.AST) -> bool:
    """True if *tree* contains a repo-root asset indicator string literal."""
    blob = _string_literal_blob(tree)
    return any(indicator in blob for indicator in _REPO_ASSET_INDICATORS)


def _is_mutation_inert_decorator(dec: ast.expr) -> bool:
    """True if *dec* is ``pytest.mark.mutation_inert`` (bare or called)."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    return isinstance(target, ast.Attribute) and target.attr == "mutation_inert"


def _module_has_pytestmark(tree: ast.Module) -> bool:
    """True if the module sets ``pytestmark`` to include ``mutation_inert``."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            continue
        # pytestmark = pytest.mark.mutation_inert  /  = [..., mutation_inert, ...]
        for sub in ast.walk(node.value):
            if isinstance(sub, ast.Attribute) and sub.attr == "mutation_inert":
                return True
    return False


def _collect_asset_names(tree: ast.Module) -> set[str]:
    """Names assigned (transitively) from ``parents[N]``-derived expressions.

    Seeds from module-level assignments whose RHS contains a ``parents[N]``
    subscript, then propagates to any name assigned from an expression that
    references an already-known asset name (e.g. ``MANIFEST = REPO_ROOT / ...``).
    """
    names: set[str] = set()
    assigns: list[tuple[ast.Name, ast.expr]] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                assigns.append((target, node.value))

    changed = True
    while changed:
        changed = False
        for target, value in assigns:
            if target.id in names:
                continue
            referenced = {n.id for n in ast.walk(value) if isinstance(n, ast.Name)}
            if _has_parents_subscript(value) or (referenced & names):
                names.add(target.id)
                changed = True
    return names


def _helper_names(tree: ast.Module, asset_names: set[str]) -> set[str]:
    """Function names whose body directly references an asset name.

    One level of indirection is sufficient for the known cases (helpers like
    ``_read_template()`` that close over a module-level asset constant).
    """
    helpers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            referenced = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if referenced & asset_names:
                helpers.add(node.name)
    return helpers


def _body_is_asset_reading(
    body: list[ast.stmt],
    asset_names: set[str],
    helpers: set[str],
) -> bool:
    """True if a test body reads an asset (by name, helper call, or inline parents)."""
    for n in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(n, ast.Name) and n.id in asset_names:
            return True
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in helpers:
            return True
    # Inline ``parents[N]`` access inside the test body (no module constant).
    return _has_parents_subscript(ast.Module(body=body, type_ignores=[]))


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------


def _scan_file(path: Path) -> list[MarkerViolation]:
    """Return marker violations for a single test file (empty if not in scope)."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []  # unreadable file is out of scope here; other gates own that.
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []  # unparseable file is owned by ruff/CI; not this gate.

    # File-level gate: must both reach above its own dir AND target a repo asset.
    if not _has_parents_subscript(tree) or not _references_repo_asset(tree):
        return []

    asset_names = _collect_asset_names(tree)
    helpers = _helper_names(tree, asset_names)
    module_marked = _module_has_pytestmark(tree)
    rel = _display(path)
    violations: list[MarkerViolation] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            class_marked = any(_is_mutation_inert_decorator(d) for d in node.decorator_list)
            uncovered: list[tuple[str, int]] = []
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not child.name.startswith("test"):
                    continue
                if not _body_is_asset_reading([child], asset_names, helpers):
                    continue
                method_marked = any(_is_mutation_inert_decorator(d) for d in child.decorator_list)
                if not (method_marked or class_marked or module_marked):
                    uncovered.append((child.name, child.lineno))
            if uncovered:
                violations.append(
                    MarkerViolation(
                        file=rel,
                        scope=node.name,
                        line=node.lineno,
                        detail=(
                            f"Asset-reading test class '{node.name}' is missing "
                            f"@pytest.mark.mutation_inert ({len(uncovered)} method(s) "
                            f"read committed repo-root assets, none marked). Add the "
                            f"marker on the class or each reading method so MutMut's "
                            f"-m 'not mutation_inert' filter excludes them."
                        ),
                    )
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test"
        ):
            if not _body_is_asset_reading([node], asset_names, helpers):
                continue
            fn_marked = any(_is_mutation_inert_decorator(d) for d in node.decorator_list)
            if not (fn_marked or module_marked):
                violations.append(
                    MarkerViolation(
                        file=rel,
                        scope=node.name,
                        line=node.lineno,
                        detail=(
                            f"Asset-reading test function '{node.name}' is missing "
                            f"@pytest.mark.mutation_inert. It reads a committed "
                            f"repo-root asset via parents[N], which crashes MutMut's "
                            f"sandbox. Add the marker so MutMut's "
                            f"-m 'not mutation_inert' filter excludes it."
                        ),
                    )
                )
    return violations


def find_violations(scopes: list[Path]) -> list[MarkerViolation]:
    """Scan every ``test_*.py`` under *scopes* and return all violations."""
    violations: list[MarkerViolation] = []
    for scope in scopes:
        if not scope.is_dir():
            continue
        for path in sorted(scope.rglob("test_*.py")):
            violations.extend(_scan_file(path))
    return violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_human(violations: list[MarkerViolation]) -> None:
    if not violations:
        print(
            "✅ mutation_inert convention check passed — every asset-reading test "
            "under the MutMut scopes carries the marker."
        )
        return
    print(
        f"❌ {len(violations)} asset-reading test class(es)/function(s) lack "
        f"@pytest.mark.mutation_inert:\n"
    )
    for v in violations:
        print(f"  • {v.file}:{v.line}  ({v.scope})")
        print(f"    {v.detail}\n")
    print(
        "Why: MutMut runs tests inside mutants/, where parents[N] resolves "
        "differently and committed repo-root assets are missing — the test "
        "crashes and aborts the whole mutation run (issue #146).\n"
        "Fix: decorate the reading test class/function with "
        "@pytest.mark.mutation_inert (or set module-level "
        "pytestmark = pytest.mark.mutation_inert). This matches the four "
        "reference tests: test_prompt_path_compliance, test_preview_no_provider, "
        "test_mem0_prompt_path_scope, test_observability.\n"
        "See: scripts/checks/check_mutation_inert_assets.py and "
        "scripts/run_mutmut.py (SCOPE_CORE/SCOPE_API, mutation_inert filter)."
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enforce the mutation_inert convention for asset-reading tests.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for CI consumption).",
    )
    parser.add_argument(
        "--scopes",
        nargs="+",
        type=Path,
        default=None,
        help=(
            "Override the scanned test directories (default: "
            f"{list(DEFAULT_SCOPES)}). Mainly for tests."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    scopes = args.scopes if args.scopes else [ROOT / s for s in DEFAULT_SCOPES]
    violations = find_violations(scopes)

    if args.json:
        payload = {
            "passed": not violations,
            "violations": [v.as_json() for v in violations],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_human(violations)

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
