"""Operation handlers and category orchestration for clean_caches.

This module is an implementation detail of ``scripts/clean_caches.py`` and
holds the path-level category handlers plus the category dispatcher:

  - ``_handle_glob_dir`` / ``_handle_glob_file``   glob-based removal
  - ``_handle_path_dir`` / ``_handle_path_file``   fixed-path removal
  - ``_handle_empty_dir``                          empty a directory in place
  - ``_clean_logs``                                log retention cleanup
  - ``clean_category``                             dispatch one category's ops

Key design principle
--------------------
Every handler delegates deletion to the SINGLE safe code path defined in
``ops.py`` (``safe_rmtree`` / ``safe_unlink``), which receive the
``dry_run`` flag and handle both modes internally. There is no duplicated
dry-run logic here, so the ``is_excluded`` guard runs identically in either
mode — this prevents dry-run previews from listing paths inside excluded
roots such as ``.venv/``.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from .data import (
    ROOT,
    Category,
    CleanStats,
)
from .ops import (
    is_excluded,
    safe_rmtree,
    safe_unlink,
)

# ---------------------------------------------------------------------------
# Operation handlers
#
# Each handler finds candidate paths and delegates to a SINGLE safe helper
# (safe_rmtree / safe_unlink). The helpers handle both dry-run and real
# deletion, so there is no duplicated logic that could bypass is_excluded.
# ---------------------------------------------------------------------------


def _handle_glob_dir(
    pattern: str,
    dry_run: bool,
    verbose: bool,
    track_size: bool,
) -> CleanStats:
    """Find and remove all directories matching a glob pattern."""
    total = CleanStats()
    for path in sorted(ROOT.glob(pattern)):
        if not path.is_dir() and not path.is_symlink():
            continue
        total += safe_rmtree(path, dry_run, verbose, track_size)
    return total


def _handle_glob_file(
    pattern: str,
    dry_run: bool,
    verbose: bool,
    track_size: bool,
) -> CleanStats:
    """Find and remove all files matching a glob pattern."""
    total = CleanStats()
    for path in sorted(ROOT.glob(pattern)):
        if not path.is_file():
            continue
        total += safe_unlink(path, dry_run, verbose, track_size)
    return total


def _handle_path_dir(
    rel_path: str,
    dry_run: bool,
    verbose: bool,
    track_size: bool,
) -> CleanStats:
    """Remove a specific directory at a relative path from ROOT."""
    path = ROOT / rel_path
    if not path.exists() and not path.is_symlink():
        return CleanStats()
    return safe_rmtree(path, dry_run, verbose, track_size)


def _handle_path_file(
    rel_path: str,
    dry_run: bool,
    verbose: bool,
    track_size: bool,
) -> CleanStats:
    """Remove a specific file at a relative path from ROOT."""
    path = ROOT / rel_path
    if not path.exists() or path.is_dir():
        return CleanStats()
    return safe_unlink(path, dry_run, verbose, track_size)


def _handle_empty_dir(
    rel_path: str,
    dry_run: bool,
    verbose: bool,
    track_size: bool,
) -> CleanStats:
    """Remove all contents of a directory but keep the directory itself."""
    path = ROOT / rel_path
    if not path.exists() or not path.is_dir():
        return CleanStats()

    total = CleanStats()
    for item in sorted(path.iterdir()):
        if item.name == ".gitignore":
            # Preserve tracked .gitignore inside the directory
            if verbose:
                print(f"  Keeping: {item.relative_to(ROOT)}")
            continue

        if item.is_dir() and not item.is_symlink():
            total += safe_rmtree(item, dry_run, verbose, track_size)
        else:
            total += safe_unlink(item, dry_run, verbose, track_size)
    return total


def _clean_logs(
    dry_run: bool,
    verbose: bool,
    track_size: bool,
    keep_logs: int,
) -> CleanStats:
    """Clean log files, respecting *keep_logs* retention policy.

    Log files are grouped by (parent_directory, stem) so that rotated
    logs for the same service are kept together. The *keep_logs* most
    recent files (by mtime) are retained per group; the rest are deleted.
    """
    total = CleanStats()

    # Collect all .log files
    log_files: list[Path] = []

    # Root-level *.log
    log_files.extend(ROOT.glob("*.log"))

    # Logs inside logs/ directory
    logs_dir = ROOT / "logs"
    if logs_dir.exists():
        log_files.extend(sorted(logs_dir.rglob("*.log")))

    if not log_files:
        return total

    # Additional log-like files (e.g., .txt logs, rotated logs)
    if logs_dir.exists():
        for ext in ("*.txt", "*.log.*"):
            log_files.extend(sorted(logs_dir.rglob(ext)))

    # Group by (parent_dir, service_name) so rotated logs (dev.log.1, dev.log.2)
    # are grouped with the main log (dev.log).
    def _log_service_name(path: Path) -> str:
        """Extract the service name from a log file path.

        Handles both simple (dev.log) and rotated (dev.log.1, dev.log.2.gz) names.
        """
        name = path.name
        m = re.match(r"^(.+?)\.(log|txt)(\.\d+)?(\.\w+)?$", name)
        if m:
            return m.group(1)
        return path.stem

    groups: dict[tuple[Path, str], list[Path]] = defaultdict(list)
    for lp in log_files:
        try:
            lp.relative_to(ROOT)
        except ValueError:
            continue  # Skip files outside project root
        if is_excluded(lp):
            continue
        groups[(lp.parent, _log_service_name(lp))].append(lp)

    for (_parent, _svc), paths in groups.items():
        # Sort newest first
        sorted_paths = sorted(
            paths,
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )

        to_keep = sorted_paths[:keep_logs]
        to_delete = sorted_paths[keep_logs:]

        if keep_logs > 0 and verbose and to_keep:
            kept = ", ".join(str(p.relative_to(ROOT)) for p in to_keep)
            print(f"  Keeping {len(to_keep)} log(s): {kept}")

        for lp in to_delete:
            total += safe_unlink(lp, dry_run, verbose, track_size)

    return total


# ---------------------------------------------------------------------------
# Category processing
# ---------------------------------------------------------------------------

OP_HANDLERS = {
    "glob_dir": _handle_glob_dir,
    "glob_file": _handle_glob_file,
    "path_dir": _handle_path_dir,
    "path_file": _handle_path_file,
    "empty_dir": _handle_empty_dir,
}


def clean_category(
    cat: Category,
    dry_run: bool,
    verbose: bool,
    track_size: bool,
    keep_logs: int,
) -> CleanStats:
    """Process all operations in *cat*, returning aggregate stats."""
    if cat.name == "logs":
        return _clean_logs(dry_run, verbose, track_size, keep_logs)

    total = CleanStats()
    for kind, target in cat.ops:
        handler = OP_HANDLERS.get(kind)
        if handler is None:
            print(
                f"  \u26a0  Unknown operation kind {kind!r} in category {cat.name!r}",
                file=sys.stderr,
            )
            continue
        total += handler(target, dry_run, verbose, track_size)
    return total
