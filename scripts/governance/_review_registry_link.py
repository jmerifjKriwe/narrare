"""ADR-062 P5 — review→registry metadata linking checker.

Single responsibility (RULE-06): assert that every ``### [AUFG-XX-YY]`` /
``### [CR-AUFG-XX-YY]`` task header in a technical-review file maps to exactly
one *consistent* AUFG-registry entry. "Consistent" means:

  * the ``id`` matches,
  * the entry's ``source`` references the originating review file,
  * any dependency paths cited by an *active* entry resolve against the repo,
  * and the ``id`` is unique — a header is not silently claimed by an
    *unrelated* entry that happens to share the id (the AUFG-01-03 collision
    class), unless a documented re-homing redirects it.

Re-homing recognition: when a header's id is claimed by an entry whose source
does not match the review, the checker accepts a *different* registry entry as
the claimant when that entry's source references the review AND its section
documents a re-homing from the original id (e.g. review-01's editor-hotspots
``[AUFG-01-03]`` re-homed to ``AUFG-01-08``).

RULE-07: reads review/registry markdown and the repo filesystem (paths as text,
never imported). Imports no application runtime modules.

WARNING-only this cycle (exit 0): findings are reported but never fail the
gate. Ratchets to blocking in a follow-up.

ADR: docs/architecture/decisions/ADR-062-governance-drift-phase2-status-ssot.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "RegistryMeta",
    "ReviewLinkFinding",
    "ReviewLinkReport",
    "ReviewTaskHeader",
    "check_review_registry_link",
    "collect_review_headers",
    "parse_registry_meta",
    "parse_review_headers",
]

#: Lifecycle statuses whose dependency paths are enforced (current work).
#: ``resolved`` / ``not_applicable`` / ``covered_by_existing_aufg`` entries hold
#: historical dependency references (e.g. a since-deleted file) and are skipped.
_DEPS_CHECKED_STATUSES: frozenset[str] = frozenset({"open", "in_progress", "blocked"})

#: Keyword indicating a documented re-homing in a registry section.
_REHOME_TOKEN = "re-hom"  # nosec B105 — re-homing documentation marker, not a credential

#: Matches a review task header: ``### [AUFG-01-01]`` or ``### [CR-AUFG-07-07]``.
_HEADER_RE = re.compile(r"^#{1,6}\s+\[((?:CR-)?(?:AUFG|AR|AE))-(\d{2})-(\d{2})\]\s*(.*)$")

#: Matches a registry entry header: ``### AUFG-01-01 — Title``.
_ENTRY_HEADER_RE = re.compile(
    r"^(#{1,6})\s+((?:CR-)?(?:AUFG|AR|AE))-(\d{2})-(\d{2})\s*[—–-]\s*(.+)$",  # noqa: RUF001
    re.MULTILINE,
)

#: ``| Source | value |`` table row.
_SOURCE_ROW_RE = re.compile(r"^\|\s*Source\s*\|\s*(.+?)\s*\|\s*$", re.MULTILINE)

#: ``| Status | `value` |`` or ``| Type | `value` |`` table row.
_STATUS_ROW_RE = re.compile(r"^\|\s*(?:Status|Type)\s*\|\s*`?([^|`]+?)`?\s*\|\s*$", re.MULTILINE)

#: ``| Dependencies | value |`` table row.
_DEPS_ROW_RE = re.compile(r"^\|\s*Dependencies\s*\|\s*(.+?)\s*\|\s*$", re.MULTILINE)

#: A dependency candidate: a slash-bearing, extension-bearing path with no glob.
_DEP_PATH_RE = re.compile(r"`?([A-Za-z0-9._][\w./-]*\.[A-Za-z]{1,5})`?")


@dataclass(frozen=True)
class ReviewTaskHeader:
    """A ``### [AUFG-XX-YY]`` task header parsed from a review file."""

    task_id: str
    review_file: str
    line: int


@dataclass(frozen=True)
class RegistryMeta:
    """The link-relevant metadata for one registry entry."""

    entry_id: str
    source: str
    status: str
    dependencies_text: str
    section_text: str


@dataclass(frozen=True)
class ReviewLinkFinding:
    """One review→registry linking inconsistency."""

    task_id: str
    review_file: str
    kind: str  # missing_entry | source_mismatch | invalid_dependency_path
    detail: str


@dataclass(frozen=True)
class ReviewLinkReport:
    """Aggregated WARNING-only review→registry linking report."""

    findings: tuple[ReviewLinkFinding, ...] = field(default_factory=tuple)
    headers_scanned: int = 0
    entries_scanned: int = 0
    rehomings_recognized: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_review_headers(text: str, review_file: str) -> list[ReviewTaskHeader]:
    """Extract bracketed task headers from review markdown *text*."""
    headers: list[ReviewTaskHeader] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = _HEADER_RE.match(line)
        if match is None:
            continue
        task_id = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        headers.append(ReviewTaskHeader(task_id=task_id, review_file=review_file, line=line_no))
    return headers


def collect_review_headers(repo_root: Path) -> list[ReviewTaskHeader]:
    """Collect ``### [AUFG-XX-YY]`` headers from every review file under *repo_root*.

    Scans ``_audit/results/**/review-*.md`` recursively (the review-→-registry
    source surface established by ADR-047). ``review_file`` is the basename so it
    matches the registry's ``Source`` references (which cite reviews by name).
    Missing directories yield an empty list (no reviews is not an error).
    """
    review_root = repo_root / "_audit" / "results"
    if not review_root.is_dir():
        return []
    headers: list[ReviewTaskHeader] = []
    for path in sorted(review_root.rglob("review-*.md")):
        headers.extend(parse_review_headers(path.read_text(encoding="utf-8"), path.name))
    return headers


def parse_registry_meta(text: str) -> dict[str, RegistryMeta]:
    """Parse registry markdown into link-relevant metadata per entry."""
    meta: dict[str, RegistryMeta] = {}
    for match in _ENTRY_HEADER_RE.finditer(text):
        entry_id = f"{match.group(2)}-{match.group(3)}-{match.group(4)}"
        section = _section_text(text, match.end())
        meta[entry_id] = RegistryMeta(
            entry_id=entry_id,
            source=_row(section, _SOURCE_ROW_RE),
            status=_normalize(_row(section, _STATUS_ROW_RE)),
            dependencies_text=_row(section, _DEPS_ROW_RE),
            section_text=section,
        )
    return meta


def _section_text(text: str, start: int) -> str:
    """Return text from *start* to the next entry header of any level."""
    next_h = text.find("\n### ", start)
    next_h2 = text.find("\n## ", start)
    candidates = [end for end in (next_h, next_h2) if end != -1]
    end = min(candidates) if candidates else len(text)
    return text[start:end]


def _row(section: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(section)
    return match.group(1).strip() if match else ""


def _normalize(raw: str) -> str:
    return raw.strip().strip("`").strip()


# ---------------------------------------------------------------------------
# Linking check
# ---------------------------------------------------------------------------


def check_review_registry_link(
    headers: list[ReviewTaskHeader],
    registry: dict[str, RegistryMeta],
    repo_root: Path,
) -> ReviewLinkReport:
    """Verify each review header maps to a consistent registry entry.

    Args:
        headers: parsed review task headers.
        registry: parsed registry metadata (id -> :class:`RegistryMeta`).
        repo_root: repository root for resolving dependency paths.

    Returns:
        A :class:`ReviewLinkReport` with any inconsistencies (WARNING-only).
    """
    findings: list[ReviewLinkFinding] = []
    rehomings: list[str] = []
    validated_deps: set[str] = set()

    for header in headers:
        claimant, via_rehome = _claimant(header, registry)

        if claimant is None:
            findings.append(
                ReviewLinkFinding(
                    task_id=header.task_id,
                    review_file=header.review_file,
                    kind="missing_entry",
                    detail=(
                        f"review header {header.task_id} has no registry entry "
                        f"whose source references {header.review_file}"
                    ),
                )
            )
            continue

        if via_rehome:
            rehomings.append(header.task_id)
        elif not _source_references(claimant, header.review_file):
            # id exists but is an unrelated entry (collision) and no re-homing
            # documents the redirect.
            findings.append(
                ReviewLinkFinding(
                    task_id=header.task_id,
                    review_file=header.review_file,
                    kind="source_mismatch",
                    detail=(
                        f"registry entry {claimant.entry_id} source "
                        f"({claimant.source!r}) does not reference "
                        f"{header.review_file} — possible id collision"
                    ),
                )
            )

        # Dependency paths are validated once per claiming entry, active only.
        if claimant.entry_id not in validated_deps:
            validated_deps.add(claimant.entry_id)
            findings.extend(_validate_deps(claimant, header.review_file, repo_root))

    return ReviewLinkReport(
        findings=tuple(findings),
        headers_scanned=len(headers),
        entries_scanned=len(registry),
        rehomings_recognized=tuple(dict.fromkeys(rehomings)),
    )


def _claimant(
    header: ReviewTaskHeader,
    registry: dict[str, RegistryMeta],
) -> tuple[RegistryMeta | None, bool]:
    """Find the registry entry claiming *header*.

    Preference order:
      1. A documented re-homing: an entry (any id) whose source references the
         review AND whose section marks a re-homing from the header's id. This
         is the authoritative, intentional link (preferred over a coincidental
         same-id entry).
      2. The direct same-id entry whose source references the review.

    Returns ``(entry, via_rehoming)`` or ``(None, False)``.
    """
    rehome = _find_rehoming(header, registry)
    if rehome is not None:
        return rehome, True

    direct = registry.get(header.task_id)
    if direct is not None and _source_references(direct, header.review_file):
        return direct, False
    return direct, False  # may be None; caller reports missing/mismatch


def _find_rehoming(
    header: ReviewTaskHeader,
    registry: dict[str, RegistryMeta],
) -> RegistryMeta | None:
    """Return the entry that documents a re-homing of *header*'s id."""
    for entry in registry.values():
        if entry.entry_id == header.task_id:
            continue
        if not _source_references(entry, header.review_file):
            continue
        if _REHOME_TOKEN in entry.section_text.lower() and header.task_id in entry.section_text:
            return entry
    return None


def _source_references(entry: RegistryMeta, review_file: str) -> bool:
    """Return ``True`` when the entry's source cites *review_file* (basename)."""
    return review_file in entry.source


def _validate_deps(
    entry: RegistryMeta,
    review_file: str,
    repo_root: Path,
) -> list[ReviewLinkFinding]:
    """Validate dependency paths for an *active* entry; skip historical ones."""
    if entry.status not in _DEPS_CHECKED_STATUSES:
        return []

    findings: list[ReviewLinkFinding] = []
    for candidate in _dep_path_candidates(entry.dependencies_text):
        if not (repo_root / candidate).exists():
            findings.append(
                ReviewLinkFinding(
                    task_id=entry.entry_id,
                    review_file=review_file,
                    kind="invalid_dependency_path",
                    detail=(
                        f"registry entry {entry.entry_id} cites dependency path "
                        f"'{candidate}' which does not resolve under {repo_root}"
                    ),
                )
            )
    return findings


def _dep_path_candidates(deps_text: str) -> list[str]:
    """Extract slash-bearing, extension-bearing, non-glob path tokens.

    Bare filenames (no slash) are skipped to stay high-precision — the
    historical false-control class (a wrong path prefix) is caught by the
    full repo-relative path; bare prose words are not flagged.
    """
    candidates: list[str] = []
    seen: set[str] = set()
    for match in _DEP_PATH_RE.finditer(deps_text):
        path = match.group(1)
        if "*" in path or "/" not in path:
            continue
        if path not in seen:
            seen.add(path)
            candidates.append(path)
    return candidates
