"""CI-BLOCKING §7 "documented ≠ implemented" stub-variable detector.

Context
-------
Architectural-discipline §7 distinguishes three claims that must never be
collapsed: "it's documented", "the template exists", and "the check is
green". The concrete lesson (FIND-010 / FIND-011, relearned in CR-04) is
that a governed prompt template can sit on disk with a ``{{var}}`` slot
while the runtime populates that slot with a literal empty string ``""`` —
so the template *looks* wired but the model never receives the data. The
prompt checkers stay green because each validates one slice and none
validates that the slice is actually fed.

This checker makes that anti-pattern visible: a service builds a
:class:`~narrare_core.prompts.context.PromptContext` (or any equivalent
var-building call) with ``extra={...}`` / ``variables={...}`` where a
**registered** prompt variable (see
:mod:`narrare_core.prompts.variable_registry`) is assigned a **literal
empty string** at runtime. Conditional fallbacks such as
``x or ""`` or ``str(x) if x else ""`` are NOT literals and are correctly
left alone — only an unconditional ``""`` stub is flagged.

Severity / ratchet
------------------
This check is **CI-BLOCKING**: every finding it emits has
``severity="critical"``, so ``check_doc_drift.py`` reports it AND exits
non-zero (it fails CI / pre-commit on its own). A ratcheted **(file, var)
allowlist** (:mod:`doc_drift.stub_variable_allowlist`, the §7 work list)
records every current occurrence with a one-line *reason* tagged ``RULE-11``
(legitimately empty) or ``§7 GAP`` (true stub pending remediation).

The allowlist absorbed every legitimate occurrence, so the post-scan tree
starts clean (zero findings — the 7 RULE-11 entries stay absorbed, no
§7 GAPs remain). The allowlist IS the work list: as each §7 GAP was closed
(real value wired), its entry was removed and the checker stayed clean.
Now that §7 stub-gaps are at 0, the gate is critical: any *new*
unallowlisted stub blocks CI (prevents regression).

Relationship to ``scripts/check_empty_kb_vars.py``
--------------------------------------------------
The four KB variables (``kb_characters`` / ``kb_locations`` /
``kb_factions`` / ``kb_relationships``) are *also* enforced by the separate
CI-**blocking** no-growth gate ``check_empty_kb_vars.py`` (ratcheted in
``scripts/architecture/ai-gate-baseline.json``). This checker is the
**comprehensive** CI-blocking inventory across *all* registered variables
— it bounds "close them all". The two coexist deliberately: the narrow
baseline gate protects the highest-risk KB vars from regrowing, while this
checker keeps the full §7 surface visible and now also blocks on any new
unallowlisted stub.

RULE-11: the guard never fails silently — if the scan root is unreadable,
a file is unparseable, or the variable registry cannot be imported, it
emits a finding describing the problem (critical, so the gate fails closed
rather than silently passing when it cannot scan).

See: .opencode/context/narrare-dev/standards/architectural-discipline.md §7
     docs/_shared/CONSTRAINTS.md (RULE-11)
     docs/development/finding-lifecycle.md (enforcement ⇒ ✅ Resolved)
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from doc_drift.adr_checks import DocDriftFinding
from doc_drift.stub_variable_allowlist import allowlist_pairs

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Default scan root: the service layer where PromptContext var-building
# lives (mirrors scripts/check_empty_kb_vars.py's SCAN_ROOT). A repo-wide
# scan confirms all current occurrences are contained here.
DEFAULT_SCAN_ROOT = REPO_ROOT / "apps" / "api" / "narrare"

# CI-BLOCKING (critical). With the §7 stub-gap inventory at 0 — every
# remaining allowlist entry is RULE-11 (legitimately optional) — any NEW
# unallowlisted stub now fails CI (prevents regression). See module
# docstring "Severity / ratchet".
_SEVERITY = "critical"

# Keyword arguments that carry a var-building dict literal. ``extra`` is the
# PromptContext slot; ``variables`` covers equivalent var-building call sites.
_VAR_DICT_KWARGS: frozenset[str] = frozenset({"extra", "variables"})

# Directories never scanned (build artefacts, vendored deps, caches).
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".code-review-graph",
        "dist",
        "build",
        ".next",
        ".turbo",
        "_scratch",
    }
)

# Path fragments indicating auto-generated or migration content.
_SKIP_PATH_FRAGMENTS: frozenset[str] = frozenset(
    {
        "alembic/versions",
        "alembic\\versions",
    }
)


@dataclass(frozen=True)
class StubOccurrence:
    """One registered-var-stubbed-to-"" occurrence (inventory unit)."""

    file: str  # repo-relative POSIX path
    lineno: int  # 1-based line of the dict key
    var: str  # registered variable name
    call_target: str  # function/callee that received the var-building dict


@dataclass(frozen=True)
class _ScanResult:
    """Single-pass scan output: occurrences + files that could not be parsed."""

    occurrences: list[StubOccurrence]
    parse_errors: list[tuple[str, str]]  # (rel_path, exc class name)


def _load_registered_variables() -> frozenset[str] | None:
    """Load the governed prompt-variable set from the registry.

    Imported lazily so a missing/broken ``narrare_core`` install degrades to
    a warning (RULE-11) instead of crashing the whole doc-drift runner.
    Returns ``None`` on import failure so the caller can emit a warning.
    """
    try:
        from narrare_core.prompts.variable_registry import (
            VARIABLE_CLASSIFICATIONS,
        )
    except Exception:  # intentional broad guard (RULE-11)
        return None
    return frozenset(VARIABLE_CLASSIFICATIONS)


def _should_skip(path: Path) -> bool:
    """True if *path* is test/cache/migration code excluded from scanning."""
    name = path.name
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py") or name.endswith("_test_helpers.py"):
        return True
    if any(part in _SKIP_DIRS for part in path.parts):
        return True
    return any(frag in path.as_posix() for frag in _SKIP_PATH_FRAGMENTS)


def _iter_python(scan_root: Path) -> Iterator[Path]:
    """Yield ``*.py`` files under *scan_root*, skipping vendored/test dirs."""
    if not scan_root.exists():
        return
    for path in scan_root.rglob("*.py"):
        if _should_skip(path):
            continue
        yield path


def _call_target(call: ast.Call) -> str:
    """Best-effort human-readable name of a call's callee."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return "<expr>"


def _scan(
    target: Path,
    root: Path,
    registered: frozenset[str],
) -> _ScanResult:
    """Single-pass AST scan of *target*.

    Returns every registered-var → literal ``""`` occurrence inside an
    ``extra=`` / ``variables=`` dict literal, plus the (rel_path, class) of
    any file that could not be parsed (surfaced by the caller per RULE-11).
    Never raises — read/parse failures become parse_errors entries.
    """
    try:
        prefix = target.relative_to(root)
    except ValueError:
        prefix = Path()

    occurrences: list[StubOccurrence] = []
    parse_errors: list[tuple[str, str]] = []

    for path in _iter_python(target):
        try:
            tree = ast.parse(
                path.read_text(encoding="utf-8", errors="replace"),
                filename=str(path),
            )
        except (SyntaxError, ValueError) as exc:
            try:
                rel = (prefix / path.relative_to(target)).as_posix()
            except ValueError:
                rel = path.as_posix()
            parse_errors.append((rel, exc.__class__.__name__))
            continue

        try:
            rel = (prefix / path.relative_to(target)).as_posix()
        except ValueError:
            rel = path.as_posix()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _call_target(node)
            for kw in node.keywords:
                if kw.arg not in _VAR_DICT_KWARGS:
                    continue
                if not isinstance(kw.value, ast.Dict):
                    continue
                for key, value in zip(kw.value.keys, kw.value.values, strict=False):
                    if not (
                        isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and key.value in registered
                    ):
                        continue
                    if isinstance(value, ast.Constant) and value.value == "":
                        occurrences.append(
                            StubOccurrence(
                                file=rel,
                                lineno=key.lineno,
                                var=key.value,
                                call_target=callee,
                            )
                        )

    occurrences.sort(key=lambda o: (o.file, o.lineno, o.var))
    return _ScanResult(occurrences=occurrences, parse_errors=parse_errors)


def collect_stub_variable_occurrences(
    scan_root: Path | None = None,
    repo_root: Path | None = None,
) -> list[StubOccurrence]:
    """Collect EVERY §7 stub occurrence under *scan_root* (ignore allowlist).

    Walks ``*.py`` under *scan_root* (default: ``apps/api/narrare``) and
    returns every place a registered prompt variable is assigned a literal
    empty string ``""`` inside an ``extra=`` / ``variables=`` dict literal
    passed to a call. This is the inventory producer — it does NOT apply the
    ratcheted allowlist, so it always reports the full current surface.

    Args:
        scan_root: Root to scan. Defaults to ``apps/api/narrare``.
        repo_root: Repo root for relative-path computation.

    Returns:
        Occurrences sorted by (file, lineno). Empty when the registry cannot
        be loaded or the scan root is missing. Never raises.
    """
    root = repo_root or REPO_ROOT
    target = scan_root or DEFAULT_SCAN_ROOT

    registered = _load_registered_variables()
    if registered is None or not target.is_dir():
        return []

    return _scan(target, root, registered).occurrences


def check_stub_variables(
    scan_root: Path | None = None,
) -> list[DocDriftFinding]:
    """Scan service code for NEW §7 stub-variable occurrences.

    Emits a ``critical``-severity :class:`DocDriftFinding` for every
    occurrence found by :func:`collect_stub_variable_occurrences` that is NOT
    absorbed by the ratcheted allowlist baseline. CI-BLOCKING: findings
    surface in the doc-drift governance report AND fail CI (``check_doc_drift``
    exits non-zero) — a *new* unallowlisted stub prevents regression.

    The allowlist (``doc_drift.stub_variable_allowlist``) is the §7 work
    list. Add an entry only with a ``RULE-11`` or ``§7 GAP`` reason; remove a
    ``§7 GAP`` entry only once the real value source is wired.

    Args:
        scan_root: Root to scan. Defaults to ``apps/api/narrare``.

    Returns:
        Findings list (empty when the baseline absorbs the current tree).
        Never raises — a missing registry, unreadable root, or unparseable
        file is reported as a warning (RULE-11).
    """
    target = scan_root or DEFAULT_SCAN_ROOT
    findings: list[DocDriftFinding] = []

    registered = _load_registered_variables()
    if registered is None:
        findings.append(
            DocDriftFinding(
                severity=_SEVERITY,
                file=str(target),
                message=(
                    "[STUB-VARIABLE] cannot load narrare_core prompt variable "
                    f"registry ({target}). §7 stub-variable detection is "
                    "disabled; verify the narrare_core install."
                ),
            )
        )
        return findings

    if not target.exists():
        findings.append(
            DocDriftFinding(
                severity=_SEVERITY,
                file=str(target),
                message=(
                    "[STUB-VARIABLE] cannot scan: scan root does not exist "
                    f"({target}). Verify the path; §7 stubs may go undetected."
                ),
            )
        )
        return findings

    result = _scan(target, REPO_ROOT, registered)
    baseline = allowlist_pairs()

    for occ in result.occurrences:
        if (occ.file, occ.var) in baseline:
            continue
        findings.append(
            DocDriftFinding(
                severity=_SEVERITY,
                file=occ.file,
                message=(
                    f"[STUB-VARIABLE] registered prompt variable "
                    f"'{occ.var}' assigned literal \"\" in {occ.call_target}"
                    f"(...) extra=/variables= at line {occ.lineno}. The "
                    "template declares this slot but the runtime never "
                    "populates it (architectural-discipline §7: documented ≠ "
                    "implemented). Either wire the real value source, or add "
                    "an allowlist entry in stub_variable_allowlist.py tagged "
                    "'RULE-11' (legit) or '§7 GAP' (remediation)."
                ),
            )
        )

    for rel, exc_name in result.parse_errors:
        findings.append(
            DocDriftFinding(
                severity=_SEVERITY,
                file=rel,
                message=(
                    f"[STUB-VARIABLE] cannot parse file ({exc_name}): §7 "
                    "stubs in this file may go undetected."
                ),
            )
        )

    return findings
