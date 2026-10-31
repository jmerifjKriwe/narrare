"""Decide which E2E suites a set of changed paths owes.

One resolver, one answer: a shared surface (kernel, api, generated client,
web shell, i18n, the locks, the CI workflow) owes every suite; a path under
a known capability owes that capability's suite; docs, tooling and release
bookkeeping owe nothing; and anything the tables do not recognize owes every
suite — an unrecognized change is a reason to run more, never less. Every
resolution, including every fallback, prints its reason to stderr and exits
0, except when the script cannot do its job: bad usage exits 2, an import
error fails on its own, and an every-suite answer with no nameable suite
exits 3 — a green gate while every suite is owed and none can be named is
the design's anti-goal. This closes two holes the previous
per-capability rules had:
`app/conftest.py` owed nothing, so fixture changes silently slipped under
every suite, and `app/capabilities/conftest.py` produced a suite path that
did not exist. Stdlib only: CI resolves affected suites before `uv sync`.
"""

import argparse
import fnmatch
import json
import shutil
import subprocess  # nosec B404 - fixed argv git queries, no shell
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

CAPABILITIES: Path = Path("app/capabilities")

# A change here can break any suite, so it owes all of them.
SHARED: tuple[str, ...] = (
    "app/kernel/",
    "app/api/",
    "app/generated/",
    "web/",
    "i18n/",
    "app/conftest.py",
    "app/capabilities/conftest.py",
    "justfile",
    "pyproject.toml",
    "uv.lock",
    "pnpm-lock.yaml",
    ".github/workflows/ci.yml",
)

# A change here cannot break a suite, so it owes none of them.
INERT: tuple[str, ...] = (
    "docs/",
    "README*",
    "CHANGELOG.md",
    "LICENSE",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "TESTING.md",
    "scripts/",
    "docker-compose*.yml",
    ".pre-commit-config.yaml",
    ".release-please-manifest.json",
    ".github/",
)

# What a release PR touches and nothing else, so it owes no suite at all —
# checked before the shared surfaces, which two of these entries also are.
RELEASE: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "uv.lock",
        "CHANGELOG.md",
        ".release-please-manifest.json",
        "package.json",
        "web/package.json",
        "app/kernel/version.py",
        "web/lib/api/openapi.json",
    }
)


class Resolution(NamedTuple):
    """What a set of changed paths owes, and why.

    `capabilities` is None for every suite, [] for none, otherwise the
    sorted capability names; `reason` is one stderr line in every mode.
    """

    capabilities: list[str] | None
    reason: str


def _matches(path: str, entry: str) -> bool:
    """A table entry is a path prefix; entries with a glob match by fnmatch."""
    if "*" in entry:
        return fnmatch.fnmatchcase(path, entry)
    return path.startswith(entry)


def resolve(
    paths: Sequence[str], *, known: set[str] | None = None, release: bool = False
) -> Resolution:
    """Map changed paths to the suites they owe: None is every suite, [] is none.

    The release check runs first: a release PR touches only release-please
    files and owes nothing, even though two of them are shared surfaces.
    """
    names = known_capabilities() if known is None else set(known)
    if release and paths and all(path in RELEASE for path in paths):
        return Resolution([], "release PR: only release-please files changed")
    suites: set[str] = set()
    owed_everywhere: list[str] = []
    inert: list[str] = []
    prefix = f"{CAPABILITIES.as_posix()}/"
    for raw in paths:
        path = raw.removeprefix("./")
        if any(_matches(path, entry) for entry in SHARED):
            owed_everywhere.append(f"{path} is a shared surface")
        elif path.startswith(prefix):
            name = path.removeprefix(prefix).split("/", 1)[0]
            if name in names:
                suites.add(name)
            else:
                owed_everywhere.append(f"app/capabilities/{name}/ is not a known capability")
        elif any(_matches(path, entry) for entry in INERT):
            inert.append(path)
        else:
            owed_everywhere.append(f"{path} is not recognized")
    if owed_everywhere:
        return Resolution(None, "all suites — " + "; ".join(owed_everywhere))
    if suites:
        return Resolution(sorted(suites), "changed capabilities: " + ", ".join(sorted(suites)))
    detail = "; ".join(f"{path} owes nothing" for path in inert) or "nothing changed"
    return Resolution([], f"no suites — {detail}")


def known_capabilities() -> set[str]:
    """Capability directory names that carry an E2E suite.

    Anchored at the repository root — the same toplevel `changed` reads — so
    a caller standing in a subdirectory still sees every suite. Outside a
    repository the cwd-relative table is used, which is also what lets tests
    point the script at a tree of their own.
    """
    root = _toplevel()
    capabilities = Path(root) / CAPABILITIES if root else CAPABILITIES
    if not capabilities.is_dir():
        return set()
    return {entry.name for entry in capabilities.iterdir() if (entry / "e2e").is_dir()}


def _toplevel() -> str | None:
    """The repository root, from wherever the caller stands; None outside a repository."""
    top = _git("rev-parse", "--show-toplevel")
    return top[0] if top else None


def _git(*args: str) -> list[str] | None:
    """One git query from wherever the caller stands; None when git fails."""
    executable = shutil.which("git")
    if executable is None:
        return None
    completed = subprocess.run(  # noqa: S603  # nosec  # fixed argv, no shell
        [executable, *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.splitlines()


def default_base() -> str | None:
    """The remote's default branch, else narrare/main, else origin/main, else None."""
    for remote in _git("remote") or []:
        head = _git("symbolic-ref", "--quiet", f"refs/remotes/{remote}/HEAD")
        if head:
            candidate = head[0].removeprefix("refs/remotes/")
            if _git("rev-parse", "--verify", "--quiet", f"refs/remotes/{candidate}"):
                return candidate
    for candidate in ("narrare/main", "origin/main"):
        if _git("rev-parse", "--verify", "--quiet", f"refs/remotes/{candidate}"):
            return candidate
    return None


def changed(base: str | None, *, worktree: bool) -> list[str] | None:
    """Paths changed against base, plus the working tree's when worktree.

    None when the range cannot be read — no base, a repository git cannot
    see — so the caller falls open to every suite instead of to none.
    """
    root = _toplevel()
    if base is None or root is None:
        return None
    files = _git("-C", root, "diff", "--name-only", f"{base}...HEAD")
    if files is None:
        return None
    if worktree:
        tracked = _git("-C", root, "diff", "--name-only", "HEAD")
        untracked = _git("-C", root, "ls-files", "--others", "--exclude-standard")
        if tracked is None or untracked is None:
            return None
        files.extend(tracked)
        files.extend(untracked)
    return sorted(set(files))


def _suite_dir(name: str) -> str:
    return f"{CAPABILITIES.as_posix()}/{name}/e2e/"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affected.py",
        description="Decide which E2E suites a change owes.",
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="print a JSON array of names")
    output.add_argument(
        "--paths",
        nargs="?",
        const="affected",
        default=None,
        metavar="SCOPE",
        help="print suite dirs for SCOPE: affected (default), all, or a capability name",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--base", metavar="REF", help="diff against REF, not the default base")
    source.add_argument("--all", action="store_true", help="every known capability")
    source.add_argument("--none", action="store_true", help="no suites at all")
    parser.add_argument(
        "--release-pr", action="store_true", help="only release-please files changed"
    )
    parser.add_argument(
        "--worktree", action="store_true", help="also count staged, unstaged, untracked paths"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve and print; exit 0 on every resolution, 3 only when every suite
    is owed but none can be named, 2 only on bad usage."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    known = known_capabilities()
    json_mode: bool = args.json
    scope: str = args.paths if args.paths is not None else "affected"
    if args.none:
        resolution = Resolution([], "--none: no suites owed")
    elif args.all:
        # Through the same every-suite path as a fallback: an empty discovery
        # must reach the warning below, not silently expand to nothing.
        resolution = Resolution(sorted(known) or None, "--all: every suite")
    elif json_mode or scope == "affected":
        base: str | None = args.base or default_base()
        paths = changed(base, worktree=bool(args.worktree))
        why = "no base could be resolved" if base is None else f"base {base} is unreadable"
        resolution = (
            Resolution(None, f"{why}: all suites")
            if paths is None
            else resolve(paths, known=known, release=bool(args.release_pr))
        )
    elif scope == "all":
        resolution = Resolution(sorted(known) or None, "scope all: every suite")
    elif scope in known:
        resolution = Resolution([scope], f"scope {scope}: {_suite_dir(scope)}")
    else:
        resolution = Resolution(None, f"scope {scope} is not a known capability: all suites")
    names = resolution.capabilities if resolution.capabilities is not None else sorted(known)
    if json_mode:
        print(json.dumps(names))
    else:
        print(" ".join(_suite_dir(name) for name in names))
    print(resolution.reason, file=sys.stderr)
    if resolution.capabilities is None and not names:
        print(
            "warning: every suite is owed (--all or an unrecognized change), "
            "but no capability carries an e2e/ suite",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
