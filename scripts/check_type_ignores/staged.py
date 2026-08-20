"""Staged-files scope for the RULE-23 pre-commit hook.

The full-scan baseline comparison is the CI gate's job; the pre-commit
hook needs to be fast, so it scans ONLY the Python files staged in the
git index and checks them against the per-file counts of the baseline:

- naked ignores in staged files                  → exit 2
- production suppressions without reason         → exit 2
- production per-file count above baseline       → exit 2
- test/other per-file count above baseline       → exit 1

This is a sound commit-time enforcement of the ratchet: the committed
tree equals HEAD plus the staged changes, so if every staged file is at
or below its baseline allowance, the full-tree totals cannot grow.
Baseline updates are separate, auditable commits.
"""

from __future__ import annotations

import shutil

# Dev tooling whose purpose is shelling out to git — not production attack surface.
import subprocess  # nosec B404
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, cast

from .baseline import DEFAULT_BASELINE_PATH, load_baseline
from .scanner import ROOT, ScanResult, relative, scan_text

if TYPE_CHECKING:
    from pathlib import Path

# Absolute git path (resolved once): a missing git surfaces as a clear
# FileNotFoundError inside run_staged_mode's OSError handling.
_GIT = shutil.which("git") or "git"

SEVERITY_ERROR = 2
SEVERITY_BUDGET = 1


@dataclass
class StagedFinding:
    """One violation found in a staged file."""

    file: str
    line: int
    severity: int
    message: str


@dataclass
class StagedReport:
    """Aggregated staged-scope check result."""

    findings: list[StagedFinding] = field(default_factory=list[StagedFinding])
    scanned_files: int = 0

    @property
    def exit_code(self) -> int:
        if not self.findings:
            return 0
        return max(f.severity for f in self.findings)


class StagedSource(Protocol):
    """Contract (RULE-03): provider of staged file contents."""

    def staged_python_files(self) -> list[tuple[str, str]]:
        """Return ``(repo-relative path, file content)`` per staged .py file."""
        ...


class GitStagedSource:
    """Read added/copied/modified .py files from the git index.

    Content is read via ``git show :<path>`` so the check sees exactly
    what will be committed, not the (possibly unstaged-edited) working
    tree copy.
    """

    def __init__(self, cwd: Path = ROOT) -> None:
        self._cwd = cwd

    def staged_python_files(self) -> list[tuple[str, str]]:
        names = subprocess.run(  # noqa: S603  # nosec B603  # controlled git invocation, fixed argv
            [
                _GIT,
                "diff",
                "--cached",
                "--name-only",
                "--diff-filter=ACMR",
                "-z",
                "--",
                "*.py",
            ],
            capture_output=True,
            check=True,
            cwd=self._cwd,
        ).stdout.decode("utf-8", errors="replace")

        files: list[tuple[str, str]] = []
        for name in filter(None, names.split("\0")):
            if not name.endswith(".py"):
                continue
            blob = subprocess.run(  # noqa: S603  # nosec B603  # controlled git invocation; :<path> is a fixed index refspec
                [_GIT, "show", f":{name}"],
                capture_output=True,
                check=True,
                cwd=self._cwd,
            ).stdout.decode("utf-8", errors="replace")
            files.append((name, blob))
        return files


def check_staged(source: StagedSource, baseline: dict[str, Any]) -> StagedReport:
    """Scan staged files and compare per-file counts against *baseline*."""
    result = ScanResult()
    report = StagedReport()

    staged = source.staged_python_files()
    report.scanned_files = len(staged)
    for rel, text in staged:
        scan_text(text, ROOT / rel, result)

    # The baseline file is machine-written by ``save_baseline`` as
    # ``{"files": {path: int, ...}}``; the cast states that structural
    # contract at the boundary (runtime no-op, mirrors _coverage_model.py).
    raw_files: object = baseline.get("files") or {}
    files_map = cast("dict[str, Any]", raw_files)
    baseline_files: dict[str, int] = {str(k): int(v) for k, v in files_map.items()}

    for ti in result.naked_ignores:
        report.findings.append(
            StagedFinding(
                file=relative(ti.file),
                line=ti.line,
                severity=SEVERITY_ERROR,
                message="naked # type: ignore (no [error-code])",
            )
        )

    for ti in result.uncommented_ignores:
        report.findings.append(
            StagedFinding(
                file=relative(ti.file),
                line=ti.line,
                severity=SEVERITY_ERROR,
                message=f"production suppression without reason comment [{ti.code}]",
            )
        )

    for rel, count in sorted(result.by_file.items()):
        allowed = baseline_files.get(rel, 0)
        if count <= allowed:
            continue
        is_production = rel in result.by_file_production
        report.findings.append(
            StagedFinding(
                file=rel,
                line=0,
                severity=SEVERITY_ERROR if is_production else SEVERITY_BUDGET,
                message=(
                    f"{count} suppression(s) exceed the per-file baseline "
                    f"{allowed} (+{count - allowed}); the ratchet only allows "
                    "reductions — deliberate changes require "
                    "`python -m scripts.check_type_ignores --update-baseline` "
                    "(disappearing keys: --allow-removed)"
                ),
            )
        )

    return report


def run_staged_mode(baseline_path: Path = DEFAULT_BASELINE_PATH) -> int:
    """CLI entry for ``--staged``: run the check, print, return exit code."""
    try:
        source = GitStagedSource()
        baseline: dict[str, object] = load_baseline(baseline_path)
    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        print(f"❌  RULE-23 staged check could not run: {exc}", file=sys.stderr)
        return SEVERITY_ERROR

    report = check_staged(source, baseline)

    if report.scanned_files == 0:
        print("✅  RULE-23 (staged): no staged Python files to check")
        return 0

    if not report.findings:
        print(f"✅  RULE-23 (staged): {report.scanned_files} staged Python file(s) within baseline")
        return 0

    print(
        f"❌  RULE-23 (staged): {len(report.findings)} violation(s) in "
        f"{report.scanned_files} staged Python file(s):\n",
        file=sys.stderr,
    )
    for f in report.findings:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        print(f"    [{f.severity}] {loc}  {f.message}", file=sys.stderr)
    print(
        "\n    Budget additions are blocked by the ratchet. If this change "
        "is deliberate, update the baseline in a separate, reviewable "
        "commit: python -m scripts.check_type_ignores --update-baseline "
        "(disappearing keys must be named via --allow-removed).",
        file=sys.stderr,
    )
    return report.exit_code
