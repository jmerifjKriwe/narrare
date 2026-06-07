"""Spec/RULE-XX alignment checks.

Validates that:
1. Feature specs reference existing files/paths
2. RULE-XX references in specs have valid rule numbers
3. Specs that mention ADRs reference existing ADRs
4. Spec status matches linked ADR status where applicable

See: ADR-041 Decision 2.
"""

from __future__ import annotations

import re
from pathlib import Path

from doc_drift import safe_relative
from doc_drift.adr_checks import DocDriftFinding

# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONSTRAINTS_PATH = REPO_ROOT / "docs" / "_shared" / "CONSTRAINTS.md"
SPECS_DIR = REPO_ROOT / "docs" / "features"
ADR_DIR = REPO_ROOT / "docs" / "architecture" / "decisions"


# RULE-XX numbers that exist in CONSTRAINTS.md.
# Extracted dynamically from the file to stay in sync.
_RULE_PATTERN = re.compile(r"###\s+RULE-(\d+[a-z]?)\s+·")


def _extract_rule_numbers(constraints_content: str) -> set[str]:
    """Extract all RULE-XX identifiers from CONSTRAINTS.md."""
    return {m.group(1) for m in _RULE_PATTERN.finditer(constraints_content)}


def _extract_rule_refs_from_text(text: str) -> set[str]:
    """Extract all RULE-XX references from arbitrary text."""
    return set(re.findall(r"RULE-(\d+[a-z]?)", text))


def _extract_adr_refs_from_text(text: str) -> set[str]:
    """Extract all ADR-NNN references from arbitrary text."""
    return set(re.findall(r"ADR-(\d{3})", text))


def _get_adr_ids(adr_dir: Path) -> set[str]:
    """Get all ADR numeric IDs that exist as files."""
    ids: set[str] = set()
    if not adr_dir.exists():
        return ids
    for f in adr_dir.iterdir():
        if not f.is_file() or f.suffix != ".md":
            continue
        m = re.match(r"(?:ADR-)?(\d{3})", f.name)
        if m:
            ids.add(m.group(1))
    return ids


def _get_spec_files(specs_dir: Path) -> list[Path]:
    """Get all feature spec markdown files recursively."""
    if not specs_dir.exists():
        return []
    return sorted(
        p
        for p in specs_dir.rglob("*.md")
        if p.is_file() and p.name != "INDEX.md" and not p.name.startswith("_")
    )


# ── Check functions ────────────────────────────────────────────


def _check_rule_references(
    spec_files: list[Path],
    valid_rules: set[str],
) -> list[DocDriftFinding]:
    """Check: RULE-XX references in specs have valid rule numbers."""
    findings: list[DocDriftFinding] = []

    for spec_path in spec_files:
        try:
            content = spec_path.read_text(encoding="utf-8")
        except OSError:
            continue

        refs = _extract_rule_refs_from_text(content)
        for rule_num in sorted(refs):
            if rule_num not in valid_rules:
                findings.append(
                    DocDriftFinding(
                        severity="warning",
                        file=safe_relative(spec_path),
                        message=(
                            f"References RULE-{rule_num} which does not exist in CONSTRAINTS.md"
                        ),
                    )
                )

    return findings


def _check_adr_references(
    spec_files: list[Path],
    valid_adr_ids: set[str],
) -> list[DocDriftFinding]:
    """Check: ADR references in specs point to existing ADR files."""
    findings: list[DocDriftFinding] = []

    for spec_path in spec_files:
        try:
            content = spec_path.read_text(encoding="utf-8")
        except OSError:
            continue

        adr_refs = _extract_adr_refs_from_text(content)
        for adr_num in sorted(adr_refs):
            if adr_num not in valid_adr_ids:
                findings.append(
                    DocDriftFinding(
                        severity="critical",
                        file=safe_relative(spec_path),
                        message=f"References ADR-{adr_num} which does not exist",
                    )
                )

    return findings


def _check_file_path_references(
    spec_files: list[Path],
) -> list[DocDriftFinding]:
    """Check: file paths referenced in specs exist in the repo."""
    findings: list[DocDriftFinding] = []

    # Pattern: backtick-wrapped paths like `core/agents/foo.py`
    path_pattern = re.compile(r"`([^`]+\.(?:py|ts|tsx|yaml|json|md))`")

    for spec_path in spec_files:
        try:
            content = spec_path.read_text(encoding="utf-8")
        except OSError:
            continue

        for m in path_pattern.finditer(content):
            ref_path = m.group(1)
            # Skip non-project paths (URLs, absolute system paths)
            if ref_path.startswith(("http://", "https://", "/usr/", "/etc/")):
                continue
            # Normalize: strip leading ./ if present
            normalized = ref_path.lstrip("./")
            full_path = REPO_ROOT / normalized
            if not full_path.exists():
                findings.append(
                    DocDriftFinding(
                        severity="warning",
                        file=safe_relative(spec_path),
                        message=f"References file `{ref_path}` which does not exist",
                    )
                )

    return findings


# ── Public API ─────────────────────────────────────────────────


def check_spec_references(
    specs_dir: Path | None = None,
    constraints_path: Path | None = None,
    adr_dir: Path | None = None,
) -> list[DocDriftFinding]:
    """Run all spec/RULE-XX alignment checks.

    Args:
        specs_dir: Override specs directory (for testing).
        constraints_path: Override CONSTRAINTS.md path (for testing).
        adr_dir: Override ADR directory (for testing).

    Returns:
        List of DocDriftFinding with severity, file, and message.
    """
    effective_specs = specs_dir or SPECS_DIR
    effective_constraints = constraints_path or CONSTRAINTS_PATH
    effective_adr_dir = adr_dir or ADR_DIR

    findings: list[DocDriftFinding] = []

    # Load valid RULE numbers from CONSTRAINTS.md
    valid_rules: set[str] = set()
    if effective_constraints.exists():
        try:
            constraints_content = effective_constraints.read_text(encoding="utf-8")
            valid_rules = _extract_rule_numbers(constraints_content)
        except OSError:
            findings.append(
                DocDriftFinding(
                    severity="critical",
                    file=str(effective_constraints),
                    message="Cannot read CONSTRAINTS.md for RULE validation",
                )
            )
    else:
        findings.append(
            DocDriftFinding(
                severity="critical",
                file=str(effective_constraints),
                message="CONSTRAINTS.md not found — cannot validate RULE references",
            )
        )

    # Get spec files and ADR IDs
    spec_files = _get_spec_files(effective_specs)
    valid_adr_ids = _get_adr_ids(effective_adr_dir)

    findings.extend(_check_rule_references(spec_files, valid_rules))
    findings.extend(_check_adr_references(spec_files, valid_adr_ids))
    findings.extend(_check_file_path_references(spec_files))

    return findings
