"""ADR cross-reference and status consistency checks.

Validates that:
1. Every ADR file has a matching row in INDEX.md
2. ADR file status matches INDEX.md status
3. Cross-referenced ADRs actually exist
4. Superseded ADRs reference the replacing ADR

See: ADR-041 Decision 2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from doc_drift import safe_relative

# ── Data model ─────────────────────────────────────────────────


@dataclass
class DocDriftFinding:
    """A single doc-drift finding with severity, file, and message."""

    severity: str  # "critical" | "warning"
    file: str
    message: str


# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_ADR_DIR = REPO_ROOT / "docs" / "architecture" / "decisions"
_DEFAULT_INDEX_PATH = _DEFAULT_ADR_DIR / "INDEX.md"

_STATUS_EMOJI: dict[str, str] = {
    "accepted": "\u2705",  # ✅
    "proposed": "\U0001f504",  # 🔄
    "superseded": "\u26d4",  # ⛔
    "deprecated": "\U0001f5c4\ufe0f",  # 🗄️
    "implemented": "\u2705",  # ✅ (treated same as accepted)
}

# Valid status values extracted from ADR files
_VALID_STATUSES: frozenset[str] = frozenset(
    {"accepted", "proposed", "superseded", "deprecated", "implemented"}
)


# ── Parsing helpers ────────────────────────────────────────────


def _extract_adr_id(filename: str) -> str | None:
    """Extract ADR ID from filename.

    Handles 'ADR-001-title.md' and '001-title.md' naming.
    Returns None for non-ADR files (INDEX, _TEMPLATE).
    """
    if filename.startswith("_") or filename == "INDEX.md":
        return None
    m = re.match(r"(?:ADR-)?(\d{3})", filename)
    if m:
        return f"ADR-{m.group(1)}"
    return None


def _parse_adr_status(content: str) -> str | None:
    """Extract status from ADR file content.

    Handles two formats:
      > **Status:** ⛔ Superseded by ADR-031
      ## Status

    ⛔ Superseded by ADR-033
      > **Status:** ✅ Accepted | ✅ Implemented

    Returns lowercase status string or None if not parseable.
    """
    # Format 1: > **Status:** EMOJI StatusWord ...
    m = re.search(r"\*\*Status:\*\*\s*\S+\s+(\w+)", content)
    if m:
        return m.group(1).lower()

    # Format 2: ## Status\n\nEMOJI StatusWord ...
    m = re.search(r"##\s*Status\s*\n+\s*\S+\s+(\w+)", content)
    if m:
        return m.group(1).lower()

    return None


def _parse_supersedes(content: str) -> list[str]:
    """Extract ADR IDs from 'Supersedes:' line in ADR content."""
    m = re.search(r"\*\*Supersedes:\*\*\s*(.+)", content)
    if not m:
        return []
    text = m.group(1)
    return re.findall(r"ADR-\d{3}", text)


def _parse_superseded_by(content: str) -> list[str]:
    """Extract ADR IDs from superseded-by references in ADR content."""
    # "Superseded by ADR-NNN" in status line or body
    refs: list[str] = []
    m = re.search(r"\*\*Status:\*\*\s*.*?Superseded by (ADR-\d{3})", content)
    if m:
        refs.append(m.group(1))
    # Also check body: "Superseded by ADR-NNN" in any context
    for found in re.findall(r"Superseded by (ADR-\d{3})", content):
        if found not in refs:
            refs.append(found)
    return refs


def _parse_related_adrs(content: str) -> list[str]:
    """Extract ADR IDs from 'Related:' line in ADR content."""
    m = re.search(r"\*\*Related:\*\*\s*(.+)", content)
    if not m:
        return []
    text = m.group(1)
    return re.findall(r"ADR-\d{3}", text)


def _get_adr_files(adr_dir: Path) -> dict[str, Path]:
    """Map ADR IDs to their file paths in the decisions directory.

    Returns dict mapping 'ADR-001' -> Path for all valid ADR files.
    """
    result: dict[str, Path] = {}
    if not adr_dir.exists():
        return result
    for f in sorted(adr_dir.iterdir()):
        if not f.is_file() or f.suffix != ".md":
            continue
        adr_id = _extract_adr_id(f.name)
        if adr_id:
            result[adr_id] = f
    return result


def _parse_index_entries(index_content: str) -> dict[str, dict[str, str]]:
    """Parse INDEX.md table rows into {adr_id: {status, title}}.

    Table rows: | [ADR-001](ADR-001-llm-gateway.md) | Title | ✅ | ...
    """
    entries: dict[str, dict[str, str]] = {}
    for m in re.finditer(
        r"\[(ADR-\d{3})\]\([^)]+\)\s*\|\s*([^|]+)\|\s*(\S+)",
        index_content,
    ):
        adr_id = m.group(1)
        title = m.group(2).strip()
        status_emoji = m.group(3).strip()
        entries[adr_id] = {"title": title, "status_emoji": status_emoji}
    return entries


def _emoji_to_status(emoji: str) -> str:
    """Convert INDEX.md status emoji to canonical status string."""
    for status, e in _STATUS_EMOJI.items():
        if emoji == e:
            return status
    return "unknown"


# ── Check functions ────────────────────────────────────────────


def _check_index_consistency(
    adr_files: dict[str, Path],
    index_entries: dict[str, dict[str, str]],
) -> list[DocDriftFinding]:
    """Check: every ADR file has a matching row in INDEX.md."""
    findings: list[DocDriftFinding] = []

    for adr_id, filepath in sorted(adr_files.items()):
        if adr_id not in index_entries:
            findings.append(
                DocDriftFinding(
                    severity="warning",
                    file=safe_relative(filepath),
                    message=f"{adr_id} exists as file but has no row in INDEX.md",
                )
            )

    # Check: INDEX.md entries that don't have a corresponding file
    for adr_id in sorted(index_entries):
        if adr_id not in adr_files:
            findings.append(
                DocDriftFinding(
                    severity="critical",
                    file="docs/architecture/decisions/INDEX.md",
                    message=(f"{adr_id} listed in INDEX.md but no corresponding file exists"),
                )
            )

    return findings


def _check_status_alignment(
    adr_files: dict[str, Path],
    index_entries: dict[str, dict[str, str]],
) -> list[DocDriftFinding]:
    """Check: ADR file status matches INDEX.md status."""
    findings: list[DocDriftFinding] = []

    for adr_id, filepath in sorted(adr_files.items()):
        if adr_id not in index_entries:
            continue  # Already flagged by consistency check

        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError:
            continue

        file_status = _parse_adr_status(content)
        if file_status is None:
            findings.append(
                DocDriftFinding(
                    severity="warning",
                    file=safe_relative(filepath),
                    message=f"{adr_id}: could not parse status from file",
                )
            )
            continue

        if file_status not in _VALID_STATUSES:
            findings.append(
                DocDriftFinding(
                    severity="warning",
                    file=safe_relative(filepath),
                    message=f"{adr_id}: unrecognized status '{file_status}'",
                )
            )
            continue

        # Map "implemented" → "accepted" for INDEX comparison (same emoji)
        normalized_file = "accepted" if file_status == "implemented" else file_status
        index_status = _emoji_to_status(index_entries[adr_id]["status_emoji"])
        normalized_index = "accepted" if index_status == "implemented" else index_status

        if normalized_file != normalized_index and normalized_index != "unknown":
            findings.append(
                DocDriftFinding(
                    severity="critical",
                    file=safe_relative(filepath),
                    message=(
                        f"{adr_id}: status mismatch — file says '{file_status}', "
                        f"INDEX.md says '{index_status}'"
                    ),
                )
            )

    return findings


def _check_cross_references(
    adr_files: dict[str, Path],
) -> list[DocDriftFinding]:
    """Check: ADRs referenced in other ADRs actually exist."""
    findings: list[DocDriftFinding] = []
    known_ids = set(adr_files.keys())

    for adr_id, filepath in sorted(adr_files.items()):
        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError:
            continue

        # Check Related: references
        for ref_id in _parse_related_adrs(content):
            if ref_id not in known_ids:
                findings.append(
                    DocDriftFinding(
                        severity="critical",
                        file=safe_relative(filepath),
                        message=(
                            f"{adr_id} references {ref_id} in Related but {ref_id} does not exist"
                        ),
                    )
                )

    return findings


def _check_superseded_linkage(
    adr_files: dict[str, Path],
) -> list[DocDriftFinding]:
    """Check: superseded ADRs reference the replacing ADR, and links are valid."""
    findings: list[DocDriftFinding] = []
    known_ids = set(adr_files.keys())

    for adr_id, filepath in sorted(adr_files.items()):
        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError:
            continue

        file_status = _parse_adr_status(content)

        # If the ADR says it's superseded, it must reference the replacing ADR
        if file_status == "superseded":
            superseded_by = _parse_superseded_by(content)
            if not superseded_by:
                findings.append(
                    DocDriftFinding(
                        severity="warning",
                        file=safe_relative(filepath),
                        message=(
                            f"{adr_id} is superseded but does not reference the replacing ADR"
                        ),
                    )
                )
            else:
                for replacing in superseded_by:
                    if replacing not in known_ids:
                        findings.append(
                            DocDriftFinding(
                                severity="critical",
                                file=safe_relative(filepath),
                                message=(
                                    f"{adr_id} is superseded by {replacing} "
                                    f"but {replacing} does not exist"
                                ),
                            )
                        )

        # Check Supersedes: line — referenced ADRs should exist
        for superseded_id in _parse_supersedes(content):
            if superseded_id not in known_ids:
                findings.append(
                    DocDriftFinding(
                        severity="critical",
                        file=safe_relative(filepath),
                        message=(
                            f"{adr_id} claims to supersede {superseded_id} "
                            f"but {superseded_id} does not exist"
                        ),
                    )
                )

    return findings


# ── Public API ─────────────────────────────────────────────────


def check_adr_consistency(
    adr_dir: Path | None = None,
    index_path: Path | None = None,
) -> list[DocDriftFinding]:
    """Run all ADR consistency checks.

    Args:
        adr_dir: Override ADR directory (for testing). Defaults to
            docs/architecture/decisions/.
        index_path: Override INDEX.md path (for testing). Defaults to
            docs/architecture/decisions/INDEX.md.

    Returns:
        List of DocDriftFinding with severity, file, and message.
    """
    effective_adr_dir = adr_dir or _DEFAULT_ADR_DIR
    effective_index_path = index_path or _DEFAULT_INDEX_PATH

    findings: list[DocDriftFinding] = []

    adr_files = _get_adr_files(effective_adr_dir)

    # Parse INDEX.md
    index_entries: dict[str, dict[str, str]] = {}
    if effective_index_path.exists():
        try:
            index_content = effective_index_path.read_text(encoding="utf-8")
            index_entries = _parse_index_entries(index_content)
        except OSError:
            findings.append(
                DocDriftFinding(
                    severity="critical",
                    file=str(effective_index_path),
                    message="Cannot read INDEX.md",
                )
            )
    else:
        findings.append(
            DocDriftFinding(
                severity="critical",
                file=str(effective_index_path),
                message="INDEX.md not found",
            )
        )

    findings.extend(_check_index_consistency(adr_files, index_entries))
    findings.extend(_check_status_alignment(adr_files, index_entries))
    findings.extend(_check_cross_references(adr_files))
    findings.extend(_check_superseded_linkage(adr_files))

    return findings
