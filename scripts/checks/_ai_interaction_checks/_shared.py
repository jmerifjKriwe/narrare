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
    except subprocess.TimeoutExpired, FileNotFoundError:
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
    except subprocess.TimeoutExpired, FileNotFoundError:
        return []
    if result.returncode not in (0, 1):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
