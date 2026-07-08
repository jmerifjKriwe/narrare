"""Dependency-path validation for the review→registry linking checker.

Single responsibility (RULE-06 / RULE-04 extraction): given an active registry
entry's dependency-citation text, extract the path-like tokens and verify each
resolves against the repo filesystem. Split out of
:mod:`governance._review_registry_link` so the linking checker stays under the
RULE-04 script file-size limit.

The bare-filename resolution (``retry.py`` resolved anywhere under the repo)
closes the ADR-062 false-control class where a wrong path like ``_retry.py``
(when the file is ``retry.py``) was previously skipped because it bore no slash.

RULE-07: reads the repo filesystem (paths as text, never imported). Imports no
application runtime modules.

ADR: docs/architecture/decisions/ADR-062-governance-drift-phase2-status-ssot.md
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from governance._review_registry_link import RegistryMeta, ReviewLinkFinding

__all__ = [
    "DEPS_CHECKED_STATUSES",
    "DEP_PATH_RE",
    "validate_deps",
]

#: Lifecycle statuses whose dependency paths are enforced (current work).
#: ``resolved`` / ``not_applicable`` / ``covered_by_existing_aufg`` entries hold
#: historical dependency references (e.g. a since-deleted file) and are skipped.
DEPS_CHECKED_STATUSES: frozenset[str] = frozenset({"open", "in_progress", "blocked"})

#: A dependency candidate: a slash-bearing or bare, extension-bearing path with
#: no glob. Used both for repo-relative paths (``apps/api/retry.py``) and bare
#: filenames (``retry.py``) which are resolved by basename anywhere under the repo.
DEP_PATH_RE = re.compile(r"`?([A-Za-z0-9._][\w./-]*\.[A-Za-z]{1,5})`?")


def validate_deps(
    entry: RegistryMeta,
    review_file: str,
    repo_root: Path,
    make_finding: Callable[[str, str, str], ReviewLinkFinding],
) -> list[ReviewLinkFinding]:
    """Validate dependency paths for an *active* entry; skip historical ones.

    Args:
        entry: the registry entry whose ``dependencies_text`` is checked.
        review_file: originating review basename (for finding attribution).
        repo_root: repository root for resolving dependency paths.
        make_finding: factory ``(task_id, kind, detail) -> ReviewLinkFinding`` so
            this module need not import the dataclass at runtime (avoids a
            circular import — ``ReviewLinkFinding`` lives in the linking module).

    Returns:
        One ``ReviewLinkFinding`` per cited path that does not resolve.
    """
    if entry.status not in DEPS_CHECKED_STATUSES:
        return []

    findings: list[ReviewLinkFinding] = []
    for candidate in _dep_path_candidates(entry.dependencies_text):
        if not _resolve_dep_path(candidate, repo_root):
            findings.append(
                make_finding(
                    entry.entry_id,
                    "invalid_dependency_path",
                    (
                        f"registry entry {entry.entry_id} cites dependency path "
                        f"'{candidate}' which does not resolve under {repo_root}"
                    ),
                )
            )
    return findings


def _resolve_dep_path(candidate: str, repo_root: Path) -> bool:
    """Resolve a dependency path candidate against the repo.

    Repo-relative paths (``apps/api/retry.py``) are checked directly. Bare
    filenames (``retry.py``) are resolved by name anywhere under the repo —
    this catches the ADR-062 false-control class (``_retry.py`` when the file
    is ``retry.py``). A glob-free candidate with an extension that matches no
    file by relative path AND no file by basename is an invalid path.
    """
    if "/" in candidate:
        return (repo_root / candidate).exists()
    # Bare filename: resolve by basename anywhere under the repo.
    return any(repo_root.rglob(candidate))


def _dep_path_candidates(deps_text: str) -> list[str]:
    """Extract extension-bearing, non-glob path tokens for validation.

    Both repo-relative paths (``apps/api/retry.py``) and bare filenames
    (``retry.py``) are returned as candidates. Bare filenames are resolved
    against the repo via :func:`_resolve_dep_path` — this closes the ADR-062
    bare-filename gap where a wrong path like ``_retry.py`` (when the file is
    ``retry.py``) was skipped because it bore no slash. Pure prose words (no
    extension) and globs are still skipped to stay high-precision.
    """
    candidates: list[str] = []
    seen: set[str] = set()
    for match in DEP_PATH_RE.finditer(deps_text):
        path = match.group(1)
        if "*" in path:
            continue
        if path not in seen:
            seen.add(path)
            candidates.append(path)
    return candidates
