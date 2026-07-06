#!/usr/bin/env python3
"""RULE-04 frontend TypeScript/TSX file-size gate.

Large frontend files are treated as architecture debt. Existing violations are
ratcheted by baseline; new oversized files fail the gate and must be split.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.architecture.baselines import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    compare_section,
    format_comparison,
    stable_fingerprint,
)

WEB_DIR = ROOT / "packages" / "web"
FRONTEND_FILE_SIZE_BASELINE_SECTION = "frontend_file_size_violations"


def _display_path(path: Path, base: Path = ROOT) -> Path:
    """Return a stable display path, tolerating synthetic test paths."""
    try:
        return path.relative_to(base)
    except ValueError:
        return Path(path.as_posix())


@dataclass(frozen=True)
class FileSizeViolation:
    """A TS/TSX file above its configured hard limit."""

    path: Path
    lines: int
    limit: int
    kind: str

    def fingerprint(self) -> str:
        """Stable baseline key; excludes line count so debt can shrink freely."""
        return stable_fingerprint(self.path.as_posix(), self.kind, self.limit)


def _limit_for(path: Path, content: str | None = None) -> tuple[str, int]:
    """Return (kind, hard-limit lines) for a frontend file.

    Hooks are detected two ways (AUFG-03-04):
    1. By filename prefix ``use*.ts`` (e.g. ``useContinueStream.ts``).
    2. By export signature: any ``.ts`` file whose top-level exports
       include ``export function use*`` / ``export const use*`` is a
       hook regardless of filename (e.g. ``TipTapEditorController.ts``
       exports ``useTipTapEditorController``).

    The ``content`` arg lets callers pass pre-read file text (avoids a
    double-read in the scan loop); when omitted, the file is read lazily.
    """
    name = path.name
    if name == "page.tsx":
        return "page", 100
    if path.suffix == ".tsx":
        return "component", 200
    if path.suffix == ".ts":
        if name.startswith("use") or name.endswith("Store.ts"):
            return "hook" if name.startswith("use") else "store", 150
        if _exports_hook(path, content):
            return "hook", 150
    return "typescript", 400


# Matches `export function useFoo`, `export const useFoo =`, `export async function useFoo`.
_HOOK_EXPORT_RE = __import__("re").compile(
    r"^export\s+(?:async\s+)?(?:function|const)\s+use[A-Z]\w*",
    __import__("re").MULTILINE,
)


def _exports_hook(path: Path, content: str | None) -> bool:
    """True if the file exports a ``useXxx`` hook (top-level exports only)."""
    if content is None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return False
    return bool(_HOOK_EXPORT_RE.search(content))


def _iter_frontend_sources(web_dir: Path) -> list[Path]:
    ignored_parts = {"node_modules", ".next", "dist", "coverage"}
    files: list[Path] = []
    for pattern in ("**/*.ts", "**/*.tsx"):
        for path in web_dir.glob(pattern):
            if any(part in ignored_parts for part in path.parts):
                continue
            if path.name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
                continue
            files.append(path)
    return sorted(set(files))


def collect_violations(web_dir: Path = WEB_DIR) -> list[FileSizeViolation]:
    """Collect TS/TSX files exceeding frontend RULE-04 hard limits."""
    violations: list[FileSizeViolation] = []
    for path in _iter_frontend_sources(web_dir):
        # Read once and reuse for both line-counting and hook-export detection.
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        kind, limit = _limit_for(path, content)
        lines = content.count("\n") + (0 if content.endswith("\n") else 1)
        if lines > limit:
            violations.append(
                FileSizeViolation(
                    path=_display_path(path),
                    lines=lines,
                    limit=limit,
                    kind=kind,
                )
            )
    return violations


def format_report(violations: list[FileSizeViolation]) -> str:
    """Format a human-readable file-size report."""
    lines = ["Frontend RULE-04 file-size check", "=" * 36]
    if not violations:
        lines.append("✅ All TS/TSX files are within hard limits")
        return "\n".join(lines)
    for violation in sorted(violations, key=lambda item: (item.path.as_posix(), item.lines)):
        lines.append(
            f"WARN: {violation.path} has {violation.lines} lines "
            f"({violation.kind} hard limit: {violation.limit})"
        )
    return "\n".join(lines)


def format_json(violations: list[FileSizeViolation]) -> str:
    """Format findings as machine-readable JSON."""
    return json.dumps(
        [
            {
                "path": item.path.as_posix(),
                "lines": item.lines,
                "limit": item.limit,
                "kind": item.kind,
                "fingerprint": item.fingerprint(),
            }
            for item in violations
        ],
        indent=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check frontend TS/TSX file-size limits.")
    parser.add_argument("--web-dir", type=Path, default=WEB_DIR)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--no-baseline", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    violations = collect_violations(args.web_dir)
    if args.json:
        print(format_json(violations))
    else:
        print(format_report(violations))

    if args.no_baseline:
        return 1 if violations else 0

    comparison = compare_section(
        {item.fingerprint() for item in violations},
        FRONTEND_FILE_SIZE_BASELINE_SECTION,
        args.baseline,
    )
    print(format_comparison(comparison, "Frontend file-size ratchet"))
    if comparison.ok:
        print("RESULT: Frontend file-size debt did not grow")
        return 0
    print("RESULT: New frontend hard-limit violation(s) require modularization")
    return 1


if __name__ == "__main__":
    sys.exit(main())
