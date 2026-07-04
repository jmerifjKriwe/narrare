"""Safety helpers and size formatting for clean_caches.

This module is an implementation detail of ``scripts/clean_caches.py`` and
holds the path-level safety primitives shared by every operation handler in
``handlers.py``:

  - ``is_excluded``      guard against deleting inside protected roots
  - ``_calculate_size``   byte accounting for a file or directory tree
  - ``format_size``       human-readable byte formatting (public)
  - ``safe_rmtree``      remove a directory tree (dry-run aware)
  - ``safe_unlink``      remove a single file (dry-run aware)
  - ``expand_categories`` resolve category/group names to concrete names

Key design principle
--------------------
Dry-run and real deletion share a SINGLE safe code path. The helpers
``safe_rmtree`` and ``safe_unlink`` receive the ``dry_run`` flag and handle
both modes internally. This guarantees that the ``is_excluded`` guard runs
identically whether or not files are actually removed — the bug that
previously let dry-run previews list paths inside ``.venv/`` was caused by
handlers duplicating the dry-run logic and skipping the safety check.

The operation handlers (``_handle_*``, ``_clean_logs``) and the category
dispatcher (``clean_category``) live in ``handlers.py`` and delegate all
deletion to the safe helpers defined here.
"""

from __future__ import annotations

import contextlib
import shutil
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from .data import (
    CATEGORY_GROUPS,
    CATEGORY_INDEX,
    EXCLUDED_ROOTS,
    ROOT,
    CleanStats,
)

# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def is_excluded(path: Path) -> bool:
    """Return True if *path* is inside an excluded root directory.

    The check inspects only the first path component (relative to ROOT), so
    any nested path beneath an excluded root — e.g. ``.venv/lib/.../foo`` —
    is protected. This runs in BOTH dry-run and real mode.
    """
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return True  # Outside project root — shouldn't happen, but be safe
    parts = rel.parts
    return bool(parts and parts[0] in EXCLUDED_ROOTS)


def _calculate_size(path: Path) -> int:
    """Return total size in bytes of *path* (file or directory contents)."""
    try:
        if path.is_symlink():
            return 0
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            total = 0
            for f in path.rglob("*"):
                if f.is_file() and not f.is_symlink():
                    with contextlib.suppress(OSError):
                        total += f.stat().st_size
            return total
    except OSError:
        pass
    return 0


def format_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    s = float(abs(size_bytes))
    for unit in ("B", "KiB", "MiB", "GiB"):
        if s < 1024:
            return f"{size_bytes} B" if unit == "B" else f"{s:.1f} {unit}"
        s /= 1024
    return f"{s:.1f} TiB"


def safe_rmtree(
    path: Path,
    dry_run: bool,
    verbose: bool,
    track_size: bool,
) -> CleanStats:
    """Remove a directory tree or symlink with safety checks.

    In dry-run mode, prints what would be removed without deleting anything.

    Safety rules (apply in BOTH modes):
      - Paths under any EXCLUDED_ROOT are skipped (never listed or removed).
      - Symlinks are unlinked (not followed / rmtree'd).
      - PermissionError / OSError are caught and reported (non-fatal).

    Returns the number of paths removed and bytes freed.
    """
    if is_excluded(path):
        if verbose:
            rel = path.relative_to(ROOT)
            print(f"  \u23ed  Skipping (inside excluded root): {rel}")
        return CleanStats()

    if not path.exists() and not path.is_symlink():
        return CleanStats()

    # Pre-deletion size accounting
    size = _calculate_size(path) if track_size else 0
    rel = path.relative_to(ROOT)

    if dry_run:
        if verbose:
            print(f"  Would remove: {rel}/")
        return CleanStats(paths_removed=1, bytes_freed=size)

    try:
        if path.is_symlink() or not path.is_dir():
            path.unlink()
            if verbose:
                print(f"  Removed: {rel}")
        else:
            shutil.rmtree(path)
            if verbose:
                print(f"  Removed: {rel}/")
        return CleanStats(paths_removed=1, bytes_freed=size)

    except (PermissionError, OSError) as exc:
        print(f"  \u26a0  Error removing {rel}: {exc}", file=sys.stderr)
        return CleanStats(errors=1)


def safe_unlink(
    path: Path,
    dry_run: bool,
    verbose: bool,
    track_size: bool,
) -> CleanStats:
    """Remove a single file with safety checks.

    In dry-run mode, prints what would be removed without deleting anything.

    Safety rules (apply in BOTH modes):
      - Paths under any EXCLUDED_ROOT are skipped.
      - Directories are never unlinked here (return empty stats).
      - PermissionError / OSError are caught and reported (non-fatal).
    """
    if is_excluded(path):
        if verbose:
            rel = path.relative_to(ROOT)
            print(f"  \u23ed  Skipping (inside excluded root): {rel}")
        return CleanStats()

    if not path.exists() or path.is_dir():
        return CleanStats()

    size = _calculate_size(path) if track_size else 0
    rel = path.relative_to(ROOT)

    if dry_run:
        if verbose:
            print(f"  Would remove: {rel}")
        return CleanStats(paths_removed=1, bytes_freed=size)

    try:
        path.unlink()
        if verbose:
            print(f"  Removed: {rel}")
        return CleanStats(paths_removed=1, bytes_freed=size)

    except (PermissionError, OSError) as exc:
        print(f"  \u26a0  Error removing {rel}: {exc}", file=sys.stderr)
        return CleanStats(errors=1)


# ---------------------------------------------------------------------------
# Category name resolution
# ---------------------------------------------------------------------------


def expand_categories(
    names: list[str],
) -> set[str]:
    """Expand a list of category/group names into a set of concrete category names."""
    result: set[str] = set()
    for name in names:
        if name in CATEGORY_GROUPS:
            result.update(CATEGORY_GROUPS[name])
        elif name in CATEGORY_INDEX:
            result.add(name)
        else:
            print(
                f"  \u26a0  Unknown category or group: {name!r}",
                file=sys.stderr,
            )
    return result
