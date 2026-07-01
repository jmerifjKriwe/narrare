import fnmatch
import os
import re
import subprocess  # nosec
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WEB_DIR = REPO_ROOT / "packages" / "web"
I18N_DIR = REPO_ROOT / "packages" / "i18n" / "messages"

MANDATORY_FIELDS = ("owner", "gate", "reason", "exit", "added", "re_evaluated")


# ---------------------------------------------------------------------------
# Exclude Registry (ADR-043 Note 6 structured parsing)
# ---------------------------------------------------------------------------


class ExcludeEntry:
    """Parsed exclude entry with mandatory ADR-043 Note 6 metadata."""

    __slots__ = (
        "added",
        "exit_criteria",
        "gate",
        "line_number",
        "owner",
        "path",
        "raw_line",
        "re_evaluated",
        "reason",
    )

    def __init__(
        self,
        path: str,
        owner: str,
        gate: str,
        reason: str,
        exit_criteria: str,
        added: str,
        re_evaluated: str,
        raw_line: str,
        line_number: int,
    ) -> None:
        self.path = path
        self.owner = owner
        self.gate = gate
        self.reason = reason
        self.exit_criteria = exit_criteria
        self.added = added
        self.re_evaluated = re_evaluated
        self.raw_line = raw_line
        self.line_number = line_number


class ExcludeRegistry:
    """Structured exclude list with validation and gate-based lookup.

    Replaces the old ``set[str]`` approach.  Each entry is parsed into an
    ``ExcludeEntry`` with all mandatory fields from ADR-043 Note 6.
    Malformed entries (missing fields) are collected separately and can be
    reported as governance errors.
    """

    def __init__(self) -> None:
        self.entries: list[ExcludeEntry] = []
        self.malformed: list[str] = []

    # -- queries ----------------------------------------------------------

    def is_excluded(self, filepath: str, gate: str | None = None) -> bool:
        """Check whether *filepath* is covered by a governed exclusion.

        When *gate* is provided, only exclusions for that specific check
        gate are considered.
        """
        return any(e.path == filepath for e in self.entries if gate is None or e.gate == gate)

    def get_entries_for_gate(self, gate: str) -> list[ExcludeEntry]:
        """Return all governed exclusions matching *gate*."""
        return [e for e in self.entries if e.gate == gate]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Regex for ``key="quoted value"`` or ``key=unquoted``.
_KV_PATTERN = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')


def load_exclude_list(path: Path) -> ExcludeRegistry:
    """Load and validate the ADR-043 governed exclude list.

    Returns an ``ExcludeRegistry`` with parsed entries and any malformed
    line diagnostics.
    """
    if not path.exists():
        print(f"  [info] No exclude file at {path} — using empty exclude list")
        return ExcludeRegistry()

    registry = ExcludeRegistry()
    lines = path.read_text(encoding="utf-8").splitlines()

    for line_num, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Split: <path>  <key=value ...>
        match = re.match(r"^(\S+)\s+(.+)$", line)
        if not match:
            registry.malformed.append(
                f"L{line_num}: Missing metadata — expected "
                f'\'<path>  owner=... gate=... reason="..." exit="..." '
                f"added=YYYY-MM-DD re_evaluated=YYYY-MM-DD'\n"
                f"  Got: {line}"
            )
            continue

        file_path = match.group(1)
        metadata_str = match.group(2)

        # Parse key=value pairs (handles quoted and unquoted values).
        kv_pairs: dict[str, str] = {}
        for m in _KV_PATTERN.finditer(metadata_str):
            key = m.group(1)
            value = m.group(2) if m.group(2) is not None else m.group(3)
            kv_pairs[key] = value

        # Validate mandatory fields.
        missing = [f for f in MANDATORY_FIELDS if f not in kv_pairs]
        if missing:
            registry.malformed.append(
                f"L{line_num}: Missing mandatory field(s): "
                f"{', '.join(missing)}\n"
                f"  Path: {file_path}\n"
                f"  Got: {metadata_str}"
            )
            continue

        registry.entries.append(
            ExcludeEntry(
                path=file_path,
                owner=kv_pairs["owner"],
                gate=kv_pairs["gate"],
                reason=kv_pairs["reason"],
                exit_criteria=kv_pairs["exit"],
                added=kv_pairs["added"],
                re_evaluated=kv_pairs["re_evaluated"],
                raw_line=line,
                line_number=line_num,
            )
        )

    total = len(registry.entries)
    malformed_count = len(registry.malformed)
    print(f"  [info] Loaded {total} exclude(s), {malformed_count} malformed from {path}")
    return registry


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def display_path(path: Path, base: Path = REPO_ROOT) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Pure-Python fallback (used when the ``rg`` binary is unavailable)
# ---------------------------------------------------------------------------
#
# ``rg`` (ripgrep) is an optional performance optimisation for scanning large
# trees.  Some CI runners do not ship it; without a fallback every file-based
# check (1, 4, 5, 6, 7, 12) would silently return zero results — checks pass
# for the wrong reason.  These helpers replicate rg's behaviour for the option
# shapes the checkers actually use (``-g``/``--glob`` and ``--type``) so the
# checks keep working regardless of whether ``rg`` is installed.

# Directories rg skips by default (build artefacts + VCS/tool caches).  Pruning
# these in the fallback avoids huge scans (e.g. ``node_modules``) and false
# matches from vendored code.
_IGNORED_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        ".next",
        ".turbo",
        ".cache",
        "coverage",
        "site-packages",
    }
)

# rg ``--type`` names mapped to the filename suffixes they cover.
_TYPE_SUFFIXES: dict[str, tuple[str, ...]] = {
    "ts": (".ts", ".tsx", ".mts", ".cts"),
    "js": (".js", ".jsx", ".mjs", ".cjs"),
    "py": (".py",),
}


def _parse_scan_args(
    extra_args: tuple[str, ...],
) -> tuple[list[str], list[str], list[str]]:
    """Split ``rg`` extra args into ``(includes, excludes, types)``.

    Supports the two option families used by the checkers:

    * ``-g``/``--glob GLOB`` — a leading ``!`` marks an exclude glob.
    * ``--type NAME`` — restrict to a file-type (mapped to suffixes).
    """
    includes: list[str] = []
    excludes: list[str] = []
    types: list[str] = []
    args = list(extra_args)
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--type", "-t") and i + 1 < len(args):
            types.append(args[i + 1])
            i += 2
        elif token in ("-g", "--glob") and i + 1 < len(args):
            glob = args[i + 1]
            if glob.startswith("!"):
                excludes.append(glob[1:])
            else:
                includes.append(glob)
            i += 2
        else:
            # Unknown / unsupported option — skip defensively (best effort).
            i += 1
    return includes, excludes, types


def _glob_matches(rel_posix: str, basename: str, glob: str) -> bool:
    """Match an rg-style glob against a file.

    Globs without a slash match the basename (any depth); globs with a slash
    are anchored relative to the search root and also accepted one level deeper
    (``*/`` prefix) so patterns like ``__tests__/*`` exclude nested dirs.
    """
    if "/" in glob:
        if fnmatch.fnmatch(rel_posix, glob):
            return True
        return fnmatch.fnmatch(rel_posix, "*/" + glob)
    return fnmatch.fnmatch(basename, glob)


def _file_passes_filters(
    rel_posix: str,
    includes: list[str],
    excludes: list[str],
    types: list[str],
) -> bool:
    """Decide whether a file survives the rg glob/type filters."""
    basename = rel_posix.rsplit("/", 1)[-1]
    if basename.startswith("."):
        return False
    if types:
        suffixes = tuple(s for t in types for s in _TYPE_SUFFIXES.get(t, ()))
        if suffixes and not basename.endswith(suffixes):
            return False
    if includes and not any(_glob_matches(rel_posix, basename, g) for g in includes):
        return False
    return not any(_glob_matches(rel_posix, basename, g) for g in excludes)


def _iter_scan_files(root: Path):
    """Yield candidate files under *root*, pruning ignored/hidden dirs.

    Mirrors rg's defaults: hidden files/dirs and the ``_IGNORED_DIRS`` set are
    skipped, so vendored/build trees are never read.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS and not d.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            yield Path(dirpath) / name


def _python_search_files(
    pattern: str,
    extra_args: tuple[str, ...],
    path: str | Path,
) -> list[str]:
    """Fallback for :func:`rg_files` when ``rg`` is unavailable.

    Walks *path* with the same glob/type semantics and returns the sorted list
    of files whose content matches *pattern*.
    """
    includes, excludes, types = _parse_scan_args(extra_args)
    root = Path(path) if path else REPO_ROOT
    try:
        regex = re.compile(pattern)
    except re.error:
        return []
    base = root if root.is_dir() else root.parent
    matches: set[str] = set()
    for fp in _iter_scan_files(root):
        try:
            rel_posix = fp.relative_to(base).as_posix()
        except ValueError:
            rel_posix = fp.as_posix()
        if not _file_passes_filters(rel_posix, includes, excludes, types):
            continue
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if regex.search(content):
            matches.add(str(fp))
    return sorted(matches)


def _python_search_lines(pattern: str, filepath: str | Path) -> list[str]:
    """Fallback for :func:`rg_lines` when ``rg`` is unavailable.

    Returns matching lines in rg's ``-n`` format (``"lineno:content"``).
    """
    fp = Path(filepath)
    try:
        regex = re.compile(pattern)
    except re.error:
        return []
    try:
        content = fp.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [
        f"{lineno}:{line}".strip()
        for lineno, line in enumerate(content.splitlines(), start=1)
        if regex.search(line)
    ]


def rg_files(pattern: str, *extra_args: str, path: str | Path = "") -> list[str]:
    cmd = ["rg", "--no-heading", "-l", pattern]
    if extra_args:
        cmd.extend(extra_args)
    if path:
        cmd.append(str(path))
    try:
        result = subprocess.run(  # noqa: S603  # nosec
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        # rg not installed (e.g. some CI runners) — degrade gracefully.
        print("  [warn] 'rg' not available — using Python fallback (file scan)")
        return _python_search_files(pattern, extra_args, path)
    except subprocess.TimeoutExpired:
        return []
    if result.returncode not in (0, 1):
        return []
    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def rg_lines(pattern: str, filepath: str | Path) -> list[str]:
    cmd = ["rg", "--no-heading", "-n", pattern, str(filepath)]
    try:
        result = subprocess.run(  # noqa: S603  # nosec
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        print("  [warn] 'rg' not available — using Python fallback (line scan)")
        return _python_search_lines(pattern, filepath)
    except subprocess.TimeoutExpired:
        return []
    if result.returncode not in (0, 1):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
