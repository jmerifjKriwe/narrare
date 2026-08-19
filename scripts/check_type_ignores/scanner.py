"""Core scanning logic — walks Python files, counts type-ignore suppressions."""

from __future__ import annotations

import io
import re
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

# ── Project paths ────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]

PRODUCTION_PREFIXES = (
    str(ROOT / "apps" / "api" / "narrare"),
    str(ROOT / "packages" / "core" / "narrare_core"),
)

SCAN_DIRS = (
    ROOT / "apps",
    ROOT / "packages",
    ROOT / "scripts",
    ROOT / "tests",
)

EXCLUDE_DIRS = frozenset(
    {"__pycache__", ".venv", "_scratch", ".tox", ".mypy_cache", ".pytest_cache"}
)

# If a comment after ``# type: ignore[xxx]`` matches this pattern it counts as
# having a reason.  This covers both explicit "reason:" markers and the most
# common third-party-stub explanations found in the audit.
_REASON_RE = re.compile(
    r"#\s*(?:"
    r"reason\s*:"
    r"|no\s+stubs?\s+for\s+\S+"
    r"|untyped\s+(?:dependency|package|library|third.party)"
    r")",
    re.IGNORECASE,
)

# Regexes for matching type-ignore comments on a single line.
# Both anchored at the comment boundary so we don't match inside strings.
_TYPE_IGNORE_RE = re.compile(r"#\s+type:\s*ignore")
_NAKED_CHECK_RE = re.compile(
    r"#\s+type:\s*ignore"  # the marker itself
    r"(?!\s*\[)"  # not followed by [code]
    r"(?:\s*(?:#|$))",  # only whitespace / EOL / another comment
)
_CODE_EXTRACT_RE = re.compile(r"#\s+type:\s*ignore\s*\[([^\]]+)\]")


def comment_marker_lines(text: str) -> set[int] | None:
    """Line numbers whose COMMENT token contains a ``# type: ignore`` marker.

    Prose mentions of ``# type: ignore`` (docstrings, string literals —
    e.g. ``implement this without ``# type: ignore`` (RULE-23)``) live in
    STRING tokens and are never suppressions. Only actual comments count.

    Returns ``None`` when the source cannot be tokenized (degenerate or
    mid-edit files): the caller then falls back to the legacy line-regex
    scan, preserving the pre-tokenize behavior for such files.
    """
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        marker_lines = {
            tok.start[0]
            for tok in tokens
            if tok.type == tokenize.COMMENT and _TYPE_IGNORE_RE.search(tok.string)
        }
    except tokenize.TokenError, IndentationError, SyntaxError, ValueError:
        return None
    return marker_lines


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class TypeIgnoreMatch:
    """A single ``# type: ignore`` suppression found in the codebase."""

    file: Path
    line: int
    line_content: str
    code: str = ""  # error code(s) — empty means naked
    is_naked: bool = False  # ``# type: ignore`` without ``[code]``
    has_reason: bool = False  # production only: has a reason comment


@dataclass
class ScanResult:
    """Aggregated results of a full codebase scan."""

    total: int = 0
    production_total: int = 0
    test_total: int = 0
    other_total: int = 0

    naked_ignores: list[TypeIgnoreMatch] = field(default_factory=list[TypeIgnoreMatch])
    uncommented_ignores: list[TypeIgnoreMatch] = field(default_factory=list[TypeIgnoreMatch])

    # file-relative-path → count
    by_file: dict[str, int] = field(default_factory=dict[str, int])
    by_file_production: dict[str, int] = field(default_factory=dict[str, int])
    by_file_test: dict[str, int] = field(default_factory=dict[str, int])

    @property
    def file_count(self) -> int:
        return len(self.by_file)


# ── Helpers ──────────────────────────────────────────────────────────────────


def relative(file: Path) -> str:
    """Return a project-root-relative path string."""
    try:
        return str(file.relative_to(ROOT))
    except ValueError:
        return str(file)


def _is_production(file: Path) -> bool:
    """True when *file* lives under one of the production directories."""
    s = str(file)
    return any(s.startswith(p) for p in PRODUCTION_PREFIXES)


def _is_test(file: Path) -> bool:
    """True when *file* is part of the ``tests/`` tree."""
    return ROOT / "tests" in file.parents


def _get_category(file: Path) -> str:
    if _is_production(file):
        return "production"
    if _is_test(file):
        return "test"
    return "other"


def _should_skip(file: Path) -> bool:
    """Return True for directories / files that should never be scanned."""
    return any(part in EXCLUDE_DIRS for part in file.parts)


# ── Scanning ─────────────────────────────────────────────────────────────────


def scan_codebase() -> ScanResult:
    """Walk all Python files under *SCAN_DIRS* and collect type-ignore data."""
    result = ScanResult()

    for scan_root in SCAN_DIRS:
        if not scan_root.exists():
            continue
        for py_file in scan_root.rglob("*.py"):
            if _should_skip(py_file):
                continue

            _scan_single_file(py_file, result)

    # Top offenders — files with the most suppressions
    sorted_files = sorted(result.by_file.items(), key=lambda x: -x[1])
    result.by_file = dict(sorted_files)

    return result


def _scan_single_file(file: Path, result: ScanResult) -> None:
    """Scan one Python file and update *result* in place."""
    try:
        text = file.read_text("utf-8", errors="replace")
    except OSError, UnicodeDecodeError:
        return

    scan_text(text, file, result)


def scan_text(text: str, file: Path, result: ScanResult) -> None:
    """Scan one Python source text (file content) into *result* in place.

    *file* is only used for categorization (production/test/other) and
    reporting — the text is scanned as given, which lets the staged-files
    mode feed git-index blobs through the exact same logic.
    """
    category = _get_category(file)
    file_rel = relative(file)
    file_count = 0

    # Tokenize once: only lines whose ``# type: ignore`` sits in an actual
    # COMMENT token count as suppressions (docstring prose does not).
    marker_lines = comment_marker_lines(text)

    for lineno, line in enumerate(text.splitlines(), 1):
        # Does this line contain any type: ignore at all?
        if not _TYPE_IGNORE_RE.search(line):
            continue

        # STRING-token occurrences (docstrings, literals) are prose, not
        # suppressions — skip them when tokenization succeeded.
        if marker_lines is not None and lineno not in marker_lines:
            continue

        is_naked = bool(_NAKED_CHECK_RE.search(line))
        code = ""
        if not is_naked:
            m = _CODE_EXTRACT_RE.search(line)
            if m:
                code = m.group(1)

        has_reason = bool(_REASON_RE.search(line)) if category == "production" else False

        ti = TypeIgnoreMatch(
            file=file,
            line=lineno,
            line_content=line.strip(),
            code=code,
            is_naked=is_naked,
            has_reason=has_reason,
        )

        file_count += 1
        result.total += 1
        if category == "production":
            result.production_total += 1
        elif category == "test":
            result.test_total += 1
        else:
            result.other_total += 1

        if is_naked:
            result.naked_ignores.append(ti)

        # Uncommented (but scoped!) production ignores
        if category == "production" and not is_naked and not has_reason:
            result.uncommented_ignores.append(ti)

    if file_count:
        result.by_file[file_rel] = file_count
        if category == "production":
            result.by_file_production[file_rel] = file_count
        elif category == "test":
            result.by_file_test[file_rel] = file_count
