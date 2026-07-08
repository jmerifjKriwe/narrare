"""ADR-062 P5 — review→registry metadata linking checker.

Single responsibility (RULE-06): assert that every task header in a review file
maps to exactly one *consistent* AUFG-registry entry. "Consistent" means:

  * the ``id`` matches,
  * the entry's ``source`` references the originating review file,
  * any dependency paths cited by an *active* entry resolve against the repo,
  * and the ``id`` is unique — a header is not silently claimed by an
    *unrelated* entry that happens to share the id (the AUFG-01-03 collision
    class), unless a documented re-homing redirects it.

Two review surfaces are scanned:

  * **Technical reviews** (``_audit/results/**/review-*.md``) use
    ``### [AUFG-XX-YY]`` / ``### [CR-AUFG-XX-YY]`` bracketed headers.
  * **Content reviews** (``_audit/results/**/cr-*.md``) use
    ``- **CR-AUFG-NN-MM:**`` bold-bullet tasks (see CR-AUFG-01-08).

Re-homing recognition: when a header's id is claimed by an entry whose source
does not match the review, the checker accepts a *different* registry entry as
the claimant when that entry's source references the review AND its section
documents a re-homing from the original id (e.g. review-01's editor-hotspots
``[AUFG-01-03]`` re-homed to ``AUFG-01-08``).

CR-prefix dual-match (CR-AUFG-01-08): the registry stores CR-02/03/04 content
tasks *unprefixed* (``AUFG-NN-MM``) while the review files write ``CR-AUFG-NN-MM``.
A header therefore matches a registry entry keyed either identically OR with the
``CR-`` prefix stripped. Range-block recognition expands a single registry
section whose ``| IDs | … through … |`` row spans many ids (the CR-08 set) so a
per-id header is not falsely flagged missing.

RULE-07: reads review/registry markdown and the repo filesystem (paths as text,
never imported). Imports no application runtime modules.

Severity: technical-review findings are BLOCKING (ADR-062 enforcement complete,
AUFG-01-09 2026-07-06). Content-review findings are WARNING-only this cycle —
the ~8 genuine cross-review misses are back-filled under CR-AUFG-01-09 before
that surface is ratcheted to blocking.

ADR: docs/architecture/decisions/ADR-062-governance-drift-phase2-status-ssot.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from governance._registry_sections import (
    iter_registry_sections as _iter_registry_sections,
)
from governance._registry_sections import (
    section_ids as _section_ids,
)

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

# Dependency-path validation lives in _dep_path_validation (RULE-04 extraction).
# Imported lazily inside check_review_registry_link to avoid a circular import
# (that module needs ReviewLinkFinding, which is defined below).

#: Matches a technical-review task header: ``### [AUFG-01-01]`` or ``### [CR-AUFG-07-07]``.
_HEADER_RE = re.compile(r"^#{1,6}\s+\[((?:CR-)?(?:AUFG|AR|AE))-(\d{2})-(\d{2})\]\s*(.*)$")

#: Matches a content-review task bullet: ``- **CR-AUFG-01-01:**`` (CR-AUFG-01-08).
#: The bold wraps the id plus an optional colon: ``**CR-AUFG-01-01:**`` or
#: ``**CR-AUFG-01-01**``. Only the ``CR-`` form appears in content reviews today,
#: but the prefix is optional so a future ``- **AUFG-…:**`` is matched too.
_CR_BULLET_RE = re.compile(r"^[-*]\s+\*\*((?:CR-)?(?:AUFG|AR|AE))-(\d{2})-(\d{2}):?\*\*:?\s*(.*)$")

#: ``| Source | value |`` table row.
_SOURCE_ROW_RE = re.compile(r"^\|\s*Source\s*\|\s*(.+?)\s*\|\s*$", re.MULTILINE)

#: ``| Status | `value` … |`` or ``| Type | `value` … |`` table row. Captures the
#: leading status token even when the cell carries a rich suffix (e.g.
#: ``| Status | `resolved` (2026-07-06) — note |``). The cell content between the
#: pipes is matched lazily up to the next pipe; the first backtick-wrapped token
#: (or a bare word) is the status. Rich cells are handled so blocking enforcement
#: does not silently lose the status of an entry (ADR-062 known limitation).
_STATUS_ROW_RE = re.compile(
    r"^\|\s*(?:Status|Type)\s*\|\s*(.+?)\s*\|\s*$",
    re.MULTILINE,
)

#: ``| Dependencies | value |`` table row.
_DEPS_ROW_RE = re.compile(r"^\|\s*Dependencies\s*\|\s*(.+?)\s*\|\s*$", re.MULTILINE)

#: Filename prefixes identifying the two review surfaces.
_TECHNICAL_REVIEW_PREFIX = "review-"
_CONTENT_REVIEW_PREFIX = "cr-"


def _review_origin(review_file: str) -> str:
    """Classify a review filename as ``"technical"`` or ``"content"``.

    ``review-*.md`` → technical (BLOCKING). ``cr-*.md`` → content (WARNING-only
    this cycle, CR-AUFG-01-08/09). Anything else defaults to technical so an
    oddly-named review is not silently demoted to warning severity.
    """
    if review_file.startswith(_CONTENT_REVIEW_PREFIX):
        return "content"
    return "technical"


@dataclass(frozen=True)
class ReviewTaskHeader:
    """A task header parsed from a review file.

    ``origin`` is ``"technical"`` (``review-*.md``, ``### [AUFG-XX-YY]`` headers,
    BLOCKING) or ``"content"`` (``cr-*.md``, ``- **CR-AUFG-NN-MM:**`` bullets,
    WARNING-only this cycle per CR-AUFG-01-08).
    """

    task_id: str
    review_file: str
    line: int
    origin: str = "technical"


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
    """Aggregated review→registry linking report.

    ``findings`` are *blocking* (technical-review surface, ``review-*.md``).
    ``content_findings`` are *WARNING-only* this cycle (content-review surface,
    ``cr-*.md``, CR-AUFG-01-08) and are reported but never fail the gate until
    CR-AUFG-01-09 ratchets them to blocking.
    """

    findings: tuple[ReviewLinkFinding, ...] = field(default_factory=tuple)
    content_findings: tuple[ReviewLinkFinding, ...] = field(default_factory=tuple)
    headers_scanned: int = 0
    entries_scanned: int = 0
    rehomings_recognized: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_review_headers(text: str, review_file: str) -> list[ReviewTaskHeader]:
    """Extract task headers from review markdown *text*.

    Recognizes two task forms, scoped by review surface:

      * the technical-review bracketed header ``### [AUFG-XX-YY]`` /
        ``### [CR-AUFG-XX-YY]`` (``_HEADER_RE``) — parsed from every review file.
      * the content-review bold bullet ``- **CR-AUFG-NN-MM:**`` (``_CR_BULLET_RE``,
        CR-AUFG-01-08) — parsed only from ``cr-*.md`` content reviews. Technical
        reviews (``review-*.md``) also use bold bullets for *summary* lists (e.g.
        review-05's ``- **AE-05-01** …`` recap), which are not task definitions;
        matching them would surface false source-mismatches, so the bullet form
        is restricted to the content-review surface.

    The header's ``origin`` is derived from the filename so the caller can map
    content-review findings to WARNING severity.
    """
    origin = _review_origin(review_file)
    parse_bullets = origin == "content"
    headers: list[ReviewTaskHeader] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = _HEADER_RE.match(line)
        if match is None and parse_bullets:
            match = _CR_BULLET_RE.match(line)
        if match is None:
            continue
        task_id = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        headers.append(
            ReviewTaskHeader(task_id=task_id, review_file=review_file, line=line_no, origin=origin)
        )
    return headers


def collect_review_headers(repo_root: Path) -> list[ReviewTaskHeader]:
    """Collect task headers from every review file under *repo_root*.

    Scans both review surfaces recursively under ``_audit/results/``:

      * ``review-*.md`` — technical reviews (``### [AUFG-XX-YY]`` headers), and
      * ``cr-*.md`` — content reviews (``- **CR-AUFG-NN-MM:**`` bullets,
        CR-AUFG-01-08).

    ``review_file`` is the basename so it matches the registry's ``Source``
    references (which cite reviews by name). Missing directories yield an empty
    list (no reviews is not an error).
    """
    review_root = repo_root / "_audit" / "results"
    if not review_root.is_dir():
        return []
    headers: list[ReviewTaskHeader] = []
    for pattern in (_TECHNICAL_REVIEW_PREFIX + "*.md", _CONTENT_REVIEW_PREFIX + "*.md"):
        for path in sorted(review_root.rglob(pattern)):
            headers.extend(parse_review_headers(path.read_text(encoding="utf-8"), path.name))
    return headers


def parse_registry_meta(text: str) -> dict[str, RegistryMeta]:
    """Parse registry markdown into link-relevant metadata per entry.

    A registry section is delimited by a ``### `` header. Three header shapes
    carry ids, all parsed here:

      * a single-id entry header ``### AUFG-01-01 — Title`` (``_ENTRY_HEADER_RE``);
      * a range-id set header ``### CR-AUFG-01-01..06 — Title`` (the id range in
        the header itself — ``_ENTRY_RANGE_HEADER_RE``); and
      * a set header whose title carries no parseable id, with the ids declared
        in a ``| IDs | … through … |`` row inside the section (the CR-08 set —
        ``_IDS_RANGE_ROW_RE``).

    A section covering many ids (via a range header or a range row) is expanded
    into one virtual entry per id, so a per-id review header is not falsely
    flagged missing. The virtual entries share the section's source/status/deps.
    """
    meta: dict[str, RegistryMeta] = {}
    for section_text in _iter_registry_sections(text):
        ids = _section_ids(section_text)
        if not ids:
            continue
        primary = ids[0]
        entry = RegistryMeta(
            entry_id=primary,
            source=_row(section_text, _SOURCE_ROW_RE),
            status=_normalize(_row(section_text, _STATUS_ROW_RE)),
            dependencies_text=_row(section_text, _DEPS_ROW_RE),
            section_text=section_text,
        )
        for section_id in ids:
            meta.setdefault(section_id, entry)
    return meta


def _row(section: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(section)
    return match.group(1).strip() if match else ""


def _normalize(raw: str) -> str:
    """Extract the canonical status token from a Status-cell value.

    Handles both bare cells (``resolved``) and rich cells
    (``\\`resolved\\` (2026-07-06) — note``) by extracting the first
    backtick-wrapped token, falling back to the leading word. This closes the
    ADR-062 known limitation where rich cells parsed to ``''`` and were then
    treated as non-active (skipping dependency validation).
    """
    stripped = raw.strip()
    if not stripped:
        return ""
    # Prefer the first backtick-wrapped token (the canonical status form).
    tick_match = re.search(r"`([^`]+)`", stripped)
    if tick_match:
        return tick_match.group(1).strip()
    # Fall back to the first whitespace-delimited word.
    return stripped.split()[0] if stripped.split() else ""


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
    content_findings: list[ReviewLinkFinding] = []
    rehomings: list[str] = []
    validated_deps: set[str] = set()

    # Lazy import: _claimant_resolution needs RegistryMeta/ReviewTaskHeader
    # (defined above), so the import is deferred to avoid a circular reference.
    from governance._claimant_resolution import claimant as resolve_claimant

    for header in headers:
        claimant, via_rehome = resolve_claimant(header, registry)
        bucket = content_findings if header.origin == "content" else findings

        if claimant is None:
            bucket.append(
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
        elif header.review_file not in claimant.source:
            # id exists but is an unrelated entry (collision) and no re-homing
            # documents the redirect.
            bucket.append(
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
        # Content-review entries are not dependency-checked this cycle — their
        # registry entries are still being back-filled (CR-AUFG-01-09).
        if header.origin == "technical" and claimant.entry_id not in validated_deps:
            validated_deps.add(claimant.entry_id)
            findings.extend(_validate_active_deps(claimant, header.review_file, repo_root))

    return ReviewLinkReport(
        findings=tuple(findings),
        content_findings=tuple(content_findings),
        headers_scanned=len(headers),
        entries_scanned=len(registry),
        rehomings_recognized=tuple(dict.fromkeys(rehomings)),
    )


def _validate_active_deps(
    entry: RegistryMeta, review_file: str, repo_root: Path
) -> list[ReviewLinkFinding]:
    """Bridge to the extracted dependency-path validator.

    Passes a ``ReviewLinkFinding`` factory so :mod:`governance._dep_path_validation`
    need not import the dataclass at runtime (avoids a circular import: that
    module is imported lazily here, after ``ReviewLinkFinding`` is defined).
    """
    from governance._dep_path_validation import validate_deps

    return validate_deps(
        entry,
        review_file,
        repo_root,
        make_finding=lambda task_id, kind, detail: ReviewLinkFinding(
            task_id=task_id, review_file=review_file, kind=kind, detail=detail
        ),
    )


# Claimant resolution (id matching, re-homing, CR-prefix dual-match) lives in
# _claimant_resolution (RULE-04 extraction); imported lazily inside
# check_review_registry_link to avoid a circular import.
