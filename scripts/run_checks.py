#!/usr/bin/env python3
"""
Narrare Quality Check Runner.

Runs all quality checks and produces a compact, readable summary.
Usage:
    just check              # compact summary (default)
    just check-verbose      # raw tool output

Exit code: 0 if all checks pass, 1 if any fail.
"""

from __future__ import annotations

import os
import re
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── ANSI helpers ──────────────────────────────────────────────

_NO_COLOR = bool(os.environ.get("NO_COLOR"))


def _c(code: str, text: str) -> str:
    """Wrap *text* in ANSI *code*, respecting NO_COLOR."""
    return text if _NO_COLOR else f"{code}{text}\033[0m"


_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_SEP = "━" * 55


# ── Data model ────────────────────────────────────────────────


@dataclass
class Step:
    """One logical check step (may run multiple commands)."""

    label: str
    commands: list[tuple[list[str], Path | None]]  # (cmd, cwd)


@dataclass
class Result:
    """Outcome of a single check step."""

    step: Step
    passed: bool
    output: str
    summary: str


# ── Step definitions ──────────────────────────────────────────


def _build_steps() -> list[Step]:
    web = ROOT / "packages" / "web"
    steps: list[Step] = [
        Step(
            "Architecture",
            [
                (["uv", "run", "python", "scripts/check_architecture.py"], None),
                (["uv", "run", "python", "scripts/check_exception_baseline.py"], None),
                (["uv", "run", "python", "scripts/check_python_file_size.py"], None),
                (["uv", "run", "python", "scripts/check_prompt_surface_contract.py"], None),
                (["uv", "run", "python", "scripts/check_configuration_matrix.py"], None),
                # ADR-061: P2 aggregation prohibition (BLOCKING) + P1 effect
                # integrity (WARNING-only) over the configuration adoption matrix.
                (["uv", "run", "python", "scripts/check_matrix_effect_integrity.py"], None),
                # ADR-062: P3 doc↔status-SSOT consistency + P5 review→registry
                # linking. WARNING-only baseline (exit 0; ratchets to blocking).
                (["uv", "run", "python", "scripts/check_governance_drift.py"], None),
            ],
        ),
        Step(
            "Lint & Format",
            [
                (["uv", "run", "ruff", "check", "apps/", "packages/", "scripts/", "tests/"], None),
                (
                    [
                        "uv",
                        "run",
                        "ruff",
                        "format",
                        "--check",
                        "apps/",
                        "packages/",
                        "scripts/",
                        "tests/",
                    ],
                    None,
                ),
            ],
        ),
        Step(
            "Typecheck",
            [
                (["uv", "run", "pyright"], None),
            ],
        ),
        Step(
            "Security",
            [
                (
                    [
                        "uv",
                        "run",
                        "bandit",
                        "-c",
                        "pyproject.toml",
                        "-r",
                        "apps/api/narrare",
                        "packages/core/narrare_core",
                    ],
                    None,
                ),
                (["uv", "run", "pip-audit"], None),
            ],
        ),
        Step(
            "Model Registry",
            [
                (["uv", "run", "python", "scripts/check_model_registry.py"], None),
            ],
        ),
        Step(
            "Prompts",
            [
                (["uv", "run", "python", "scripts/check_prompt_structure.py"], None),
                # ADR-056 — runtime-evidence-aware adoption gate (matches
                # `just check-adoption` and CI). Reads committed .evidence markers.
                (
                    [
                        "uv",
                        "run",
                        "python",
                        "scripts/check_adoption.py",
                        "--evidence-dir",
                        ".evidence",
                    ],
                    None,
                ),
                (["uv", "run", "python", "scripts/check_streaming_compliance.py"], None),
            ],
        ),
    ]

    if web.is_dir() and (web / "package.json").exists():
        steps.extend(
            [
                Step(
                    "Frontend Lint",
                    [
                        (["uv", "run", "python", "scripts/check_frontend_file_size.py"], None),
                        (["pnpm", "lint:check"], web),
                    ],
                ),
                Step(
                    "i18n Validation",
                    [
                        (["npx", "tsx", "scripts/validate-i18n.ts"], None),
                    ],
                ),
                Step(
                    "Frontend Types",
                    [
                        (["pnpm", "type-check"], web),
                    ],
                ),
            ]
        )

    return steps


# ── Execution ─────────────────────────────────────────────────


def _run_step(step: Step) -> Result:
    """Run all commands for a step; stop at first failure."""
    combined = ""
    for cmd, cwd in step.commands:
        try:
            proc = subprocess.run(  # noqa: S603  # nosec B603
                cmd,
                cwd=cwd or ROOT,
                capture_output=True,
                text=True,
                timeout=300,
            )
            combined += proc.stdout + proc.stderr
            if proc.returncode != 0:
                return Result(
                    step,
                    False,
                    combined,
                    _failure_summary(step.label, combined),
                )
        except FileNotFoundError:
            return Result(step, False, combined, f"not found: {cmd[0]}")
        except subprocess.TimeoutExpired:
            return Result(step, False, combined, "timed out")

    return Result(step, True, combined, _success_summary(step.label, combined))


# ── Summary helpers ───────────────────────────────────────────

# Prefixes of lines to skip when printing failure details.
_NOISE_PREFIXES = (
    "[main]",
    "Run metrics:",
    "Files skipped",
    "Total issues (by severity):",
    "Total issues (by confidence):",
    "\tUndefined:",
    "\tLow:",
    "\tMedium:",
    "\tHigh:",
    "Skip Reason",
    "---",
)
# Substrings that mark informational pip-audit skip lines.
_SKIP_SUBSTRINGS = (
    "Dependency not found on PyPI",
    "could not be audited",
)


def _is_noise(line: str) -> bool:
    s = line.strip()
    return any(s.startswith(p) for p in _NOISE_PREFIXES) or any(
        sub in s for sub in _SKIP_SUBSTRINGS
    )


def _success_summary(label: str, output: str) -> str:
    if "Architecture" in label:
        files = re.search(r"(\d+) files checked", output)
        excs = re.search(r"(\d+) approved exception", output)
        parts = [f"{files.group(1)} files" if files else "OK"]
        if excs:
            parts.append(f"{excs.group(1)} exception(s)")
        return ", ".join(parts)
    if "Lint" in label and "Frontend" not in label:
        return "clean"
    if "Typecheck" in label and "Frontend" not in label:
        m = re.search(r"(\d+) error", output)
        return f"{m.group(1)} error(s)" if m else "0 errors"
    if "Security" in label:
        return "clean"
    if "Frontend Lint" in label:
        return "clean"
    if "i18n" in label:
        return "clean"
    if "Frontend Types" in label:
        return "0 errors"
    if "Prompts" in label:
        fails = re.search(r"(\d+) FAIL", output)
        warns = re.search(r"(\d+) WARN", output)
        parts: list[str] = []
        if fails:
            parts.append(f"{fails.group(1)} FAIL(s)")
        if warns:
            parts.append(f"{warns.group(1)} WARN(s)")
        return ", ".join(parts) if parts else "clean"
    return "OK"


def _failure_summary(label: str, output: str) -> str:
    if "Lint" in label and "Frontend" not in label:
        errs = re.findall(r"(\d+) error", output)
        fmts = re.findall(r"(\d+) file.*reformatted", output)
        parts: list[str] = []
        if errs:
            parts.append(f"{errs[-1]} lint issue(s)")
        if fmts:
            parts.append(f"{fmts[-1]} need formatting")
        return ", ".join(parts) or "failed"
    if "Typecheck" in label and "Frontend" not in label:
        m = re.search(r"(\d+) error", output)
        return f"{m.group(1)} error(s)" if m else "failed"
    if "Frontend Types" in label:
        m = re.search(r"Found (\d+) error", output)
        return f"{m.group(1)} error(s)" if m else "failed"
    if "i18n" in label:
        m = re.search(r"(\d+) issue", output)
        return f"{m.group(1)} issue(s)" if m else "issues found"
    if "Prompts" in label:
        fails = re.search(r"(\d+) FAIL", output)
        return f"{fails.group(1)} FAIL(s)" if fails else "failed"
    return "issues found"


# ── Compact output ────────────────────────────────────────────


def _print_compact(results: list[Result]) -> None:
    total = len(results)
    label_w = max(len(r.step.label) for r in results)

    print()
    print("  Narrare Quality Check")
    print(f"  {_SEP}")
    print()

    for i, r in enumerate(results, 1):
        mark = _c(_GREEN, "✓") if r.passed else _c(_RED, "✗")
        print(f"  [{i}/{total}] {r.step.label:<{label_w}s}  {mark}  {r.summary}")

    print()
    print(f"  {_SEP}")

    failures = [r for r in results if not r.passed]
    if failures:
        print(f"  {_c(_RED, f'✗ {len(failures)} check(s) failed')}")
        for r in failures:
            print()
            sep_len = max(10, 50 - len(r.step.label))
            print(f"  ── {r.step.label} {'─' * sep_len}")
            for line in r.output.splitlines():
                if not line.strip() or _is_noise(line):
                    continue
                print(f"    {_c(_DIM, line.rstrip())}")
        print()
    else:
        print(f"  {_c(_GREEN, '✓ All checks passed')}")
        print()


# ── Verbose output ────────────────────────────────────────────


def _run_verbose() -> int:
    steps = _build_steps()
    total = len(steps)

    print()
    print("  Narrare Quality Check (verbose)")
    print(f"  {_SEP}")
    print()

    any_failed = False
    for i, step in enumerate(steps, 1):
        print(f"  [{i}/{total}] {step.label}")
        for cmd, cwd in step.commands:
            try:
                proc = subprocess.run(  # noqa: S603  # nosec B603
                    cmd,
                    cwd=cwd or ROOT,
                    timeout=300,
                )
                if proc.returncode != 0:
                    any_failed = True
            except FileNotFoundError, subprocess.TimeoutExpired:
                any_failed = True
        print()

    print(f"  {_SEP}")
    if any_failed:
        print(f"  {_c(_RED, '✗ Some checks failed')}")
    else:
        print(f"  {_c(_GREEN, '✓ All checks passed')}")
    print()

    return 1 if any_failed else 0


# ── Main ──────────────────────────────────────────────────────


def main() -> int:
    if "--verbose" in sys.argv:
        return _run_verbose()

    steps = _build_steps()
    results = [_run_step(s) for s in steps]
    _print_compact(results)
    return 1 if any(not r.passed for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
