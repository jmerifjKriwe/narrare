#!/usr/bin/env python3
"""Wrapper for MutMut 3.x with scope selection.

MutMut 3.x reads ALL configuration from ``pyproject.toml`` ``[tool.mutmut]``.
The CLI (``mutmut run``) only accepts ``--max-children`` — there are NO
``--paths-to-mutate`` / ``--runner`` / ``--use-coverage`` flags (those were
MutMut 2.x and cause ``Error: No such option``).

To run different scopes, this wrapper temporarily rewrites the
``[tool.mutmut]`` table, runs ``mutmut run``, and restores the original
``pyproject.toml`` in a ``finally`` block — so the file is ALWAYS restored,
even on Ctrl-C (KeyboardInterrupt) or any other exception.

**Workspace/monorepo support:** MutMut derives mutant keys from file paths
relative to the repo root (only stripping a ``src.`` prefix). For our layout
(``packages/core/narrare_core/``) this produces keys like
``packages.core.narrare_core...`` which don't match the Python import path
``narrare_core...``. To fix this, the wrapper creates **temporary symlinks**
(e.g. ``narrare_core → packages/core/narrare_core``) before running MutMut
and removes them in the ``finally`` block alongside the pyproject restore.

Usage:
    uv run python scripts/run_mutmut.py                       # core (default)
    uv run python scripts/run_mutmut.py --scope api            # api scope
    uv run python scripts/run_mutmut.py --scope all            # all scopes
    uv run python scripts/run_mutmut.py --scope custom \\
        --paths "narrare_core/writing/style_variants.py" \\
        --tests "tests/unit/core/writing/"
    uv run python scripts/run_mutmut.py --max-children 1       # slow & safe

Exit code: that of the ``mutmut run`` subprocess (0 = success).
The ``pyproject.toml`` and symlinks are ALWAYS restored, even on failure.

See: docs/development/testing-standards.md (mutation testing)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404 — controlled CLI wrapper, not user-facing
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
BACKUP = REPO_ROOT / ".mutmut.pyproject.toml.bak"
MUTANTS_DIR = REPO_ROOT / "mutants"

# Marker so a human can tell the table was temporarily rewritten by the wrapper.
WRAPPER_MARKER = "# [rewritten temporarily by scripts/run_mutmut.py]"

# Symlink map: temporary symlink name → real package directory (relative to repo root).
#
# MutMut 3.x derives mutant keys from file paths relative to the repo root,
# stripping only a "src." prefix (see mutmut/utils/format_utils.py:get_mutant_name).
# For our monorepo layout (packages/core/narrare_core/), this produces keys like
# "packages.core.narrare_core..." which don't match the Python import path
# "narrare_core...". The temporary symlinks below make the path-derived key
# match the import path, so MutMut's trampoline hit detection works correctly.
SYMLINK_MAP: dict[str, str] = {
    "narrare_core": "packages/core/narrare_core",
    "narrare": "apps/api/narrare",
}

# Each scope defines the full [tool.mutmut] table (excluding the header line).
# Glob patterns must end in `*` or `.py` (MutMut warns otherwise).
# NOTE: source_paths use symlink names (see SYMLINK_MAP) so MutMut's
# path-derived module keys match the actual Python import paths.
SCOPE_CORE: dict[str, object] = {
    "source_paths": ["narrare_core"],
    "only_mutate": [
        "narrare_core/prompts/*",
        "narrare_core/writing/*",
        "narrare_core/llm/intents.py",
    ],
    "do_not_mutate": ["*/migrations/*", "*/__pycache__/*"],
    "pytest_add_cli_args": ["-x", "--timeout=30", "-q"],
    "pytest_add_cli_args_test_selection": ["-m", "not mutation_inert", "tests/unit/core/"],
}

SCOPE_API: dict[str, object] = {
    "source_paths": ["narrare"],
    "only_mutate": ["narrare/*"],
    "do_not_mutate": ["*/migrations/*", "*/__pycache__/*"],
    "pytest_add_cli_args": ["-x", "--timeout=30", "-q"],
    "pytest_add_cli_args_test_selection": ["-m", "not mutation_inert", "tests/unit/api/"],
}

SCOPE_ALL: dict[str, object] = {
    "source_paths": ["narrare_core", "narrare"],
    # Empty only_mutate = mutate everything under source_paths (except do_not_mutate).
    "only_mutate": [],
    "do_not_mutate": ["*/migrations/*", "*/__pycache__/*"],
    "pytest_add_cli_args": ["-x", "--timeout=30", "-q"],
    "pytest_add_cli_args_test_selection": ["-m", "not mutation_inert", "tests/unit/"],
}

SCOPES: dict[str, dict[str, object]] = {
    "core": SCOPE_CORE,
    "api": SCOPE_API,
    "all": SCOPE_ALL,
}


def _format_toml_table(scope: dict[str, object]) -> list[str]:
    """Render a [tool.mutmut] body (without the header) as TOML lines."""
    lines: list[str] = [WRAPPER_MARKER]
    for key, value in scope.items():
        if isinstance(value, list):
            str_items = [f'"{item!s}"' for item in value]  # type: ignore[literal-required]
            lines.append(f"{key} = [{', '.join(str_items)}]")
        elif isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        else:
            lines.append(f'{key} = "{value}"')
    return lines


def replace_mutmut_section(scope: dict[str, object]) -> None:
    """Replace the [tool.mutmut] table in pyproject.toml in place.

    Finds the top-level ``[tool.mutmut]`` header and replaces everything from
    that header up to (but not including) the next top-level ``[`` section, or
    end of file.
    """
    original = PYPROJECT.read_text(encoding="utf-8").splitlines(keepends=True)
    header_idx = None
    for i, line in enumerate(original):
        if line.strip() == "[tool.mutmut]":
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError(
            "Could not find [tool.mutmut] section in pyproject.toml — refusing to proceed."
        )

    # Find the end: next line that starts a new top-level table (starts with '['
    # at column 0) after the header. Blank lines/comments belong to the section.
    end_idx = len(original)
    for j in range(header_idx + 1, len(original)):
        stripped = original[j].lstrip()
        if stripped.startswith("[") and not stripped.startswith("[["):
            end_idx = j
            break

    new_body = _format_toml_table(scope)
    new_lines: list[str] = ["[tool.mutmut]\n"]
    for body_line in new_body:
        new_lines.append(body_line + "\n")

    # Preserve a blank line separator before the next section if the original had one.
    rebuilt = original[:header_idx] + new_lines + original[end_idx:]
    PYPROJECT.write_text("".join(rebuilt), encoding="utf-8")


def restore_pyproject() -> None:
    """Restore pyproject.toml from the backup if the backup exists."""
    if BACKUP.exists():
        shutil.copy2(BACKUP, PYPROJECT)
        BACKUP.unlink()


# ---------------------------------------------------------------------------
# Symlink management — fixes MutMut module-key mismatch for monorepo layouts.
# ---------------------------------------------------------------------------


def create_symlinks(source_paths: list[str]) -> list[str]:
    """Create temporary symlinks for the given source_paths.

    Only paths listed in ``SYMLINK_MAP`` get a symlink. Returns the list of
    symlink names created (for later cleanup by :func:`remove_symlinks`).

    Raises ``RuntimeError`` if a real file/directory (not our symlink) already
    exists at the symlink location — this prevents clobbering user files.
    """
    created: list[str] = []
    for sp in source_paths:
        if sp not in SYMLINK_MAP:
            continue
        target = SYMLINK_MAP[sp]
        real_target = REPO_ROOT / target
        if not real_target.is_dir():
            print(
                f"[run_mutmut] WARNING: symlink target {target} does not exist, skipping",
                file=sys.stderr,
            )
            continue

        link_path = REPO_ROOT / sp
        if link_path.is_symlink():
            # Already a symlink — check if it points to our target.
            if os.readlink(link_path) == target:
                continue
            raise RuntimeError(f"Symlink {sp} exists but points elsewhere. Refusing to proceed.")
        if link_path.exists():
            raise RuntimeError(
                f"Cannot create symlink {sp}: a real file/directory already exists "
                f"at {link_path}. Refusing to proceed."
            )

        link_path.symlink_to(target)
        created.append(sp)
        print(f"[run_mutmut] created symlink: {sp} -> {target}", flush=True)
    return created


def remove_symlinks(names: list[str]) -> None:
    """Remove symlinks created by :func:`create_symlinks`."""
    for name in names:
        link_path = REPO_ROOT / name
        if link_path.is_symlink():
            link_path.unlink()
            print(f"[run_mutmut] removed symlink: {name}", flush=True)


def run_mutmut(max_children: int | None) -> int:
    """Run `mutmut run` and return its exit code."""
    cmd: list[str] = [sys.executable, "-m", "mutmut", "run"]
    if max_children is not None:
        cmd += ["--max-children", str(max_children)]
    print(f"[run_mutmut] {' '.join(cmd)}", flush=True)
    try:
        result = subprocess.run(cmd, cwd=REPO_ROOT, check=False)  # noqa: S603  # nosec B603
    except FileNotFoundError:
        print(
            "[run_mutmut] ERROR: could not execute mutmut. "
            "Run via `uv run python scripts/run_mutmut.py`.",
            file=sys.stderr,
        )
        return 1
    return int(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MutMut 3.x wrapper with scope selection.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scope",
        choices=["core", "api", "all", "custom"],
        default="core",
        help="Mutation scope (default: core). 'custom' requires --paths.",
    )
    parser.add_argument(
        "--paths",
        help="Comma-separated only_mutate globs (only with --scope custom).",
    )
    parser.add_argument(
        "--tests",
        help="Test selection dir for pytest_add_cli_args_test_selection (custom scope).",
    )
    parser.add_argument(
        "--max-children",
        type=int,
        default=None,
        help="Forwarded to `mutmut run --max-children`. Lower = slower but safer.",
    )
    args = parser.parse_args()

    # Resolve the scope config.
    if args.scope == "custom":
        if not args.paths:
            parser.error("--scope custom requires --paths (comma-separated globs).")
        globs = [g.strip() for g in args.paths.split(",") if g.strip()]
        if not globs:
            parser.error("--paths resolved to zero globs.")
        tests = args.tests if args.tests else "tests/unit/"
        scope: dict[str, object] = {
            "source_paths": ["narrare_core"],
            "only_mutate": globs,
            "do_not_mutate": ["*/migrations/*", "*/__pycache__/*"],
            "pytest_add_cli_args": ["-x", "--timeout=30", "-q"],
            "pytest_add_cli_args_test_selection": ["-m", "not mutation_inert", tests],
        }
    else:
        scope = SCOPES[args.scope]

    # Safety: never start if a stale backup already exists (previous crashed run).
    if BACKUP.exists():
        print(
            f"[run_mutmut] WARNING: stale backup found at {BACKUP}. "
            "Restoring it and aborting to avoid clobbering pyproject.toml. "
            "Delete the backup manually if you know what you're doing.",
            file=sys.stderr,
        )
        restore_pyproject()
        return 1

    # Safety: clean up any stale symlinks from a previous crashed run.
    for name in SYMLINK_MAP:
        link_path = REPO_ROOT / name
        if link_path.is_symlink():
            print(
                f"[run_mutmut] WARNING: stale symlink {name} found. Removing it.",
                file=sys.stderr,
            )
            link_path.unlink()

    # Backup pyproject, create symlinks, rewrite config, run, restore — ALWAYS.
    shutil.copy2(PYPROJECT, BACKUP)
    created_symlinks: list[str] = []
    try:
        replace_mutmut_section(scope)
        source_paths_raw = scope.get("source_paths", [])
        if isinstance(source_paths_raw, list):
            created_symlinks = create_symlinks([str(p) for p in source_paths_raw])  # type: ignore[arg-type]
        print(f"[run_mutmut] scope={args.scope} — running mutmut", flush=True)
        exit_code = run_mutmut(max_children=args.max_children)
    except KeyboardInterrupt:
        print("\n[run_mutmut] interrupted — cleaning up", file=sys.stderr)
        exit_code = 130  # 128 + SIGINT(2)
    finally:
        remove_symlinks(created_symlinks)
        restore_pyproject()

    print(f"[run_mutmut] done (exit {exit_code}). pyproject.toml restored.", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
