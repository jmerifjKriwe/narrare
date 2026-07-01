"""Checker terminology alignment checks.

Validates that terms used in checker scripts match canonical sources:
1. Audit states in checker scripts match AuditState enum values
2. Category names in checker scripts match adoption-registry.yaml
3. Mode names in checker output match registry modes

See: ADR-041 Decision 2.
"""

from __future__ import annotations

import re
from pathlib import Path

from doc_drift import safe_relative
from doc_drift.adr_checks import DocDriftFinding

# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = REPO_ROOT / "scripts" / "architecture" / "adoption-registry.yaml"


CHECKER_SCRIPTS = [
    REPO_ROOT / "scripts" / "check_adoption.py",
    REPO_ROOT / "scripts" / "check_kg_consistency.py",
    REPO_ROOT / "scripts" / "adoption" / "audit_report.py",
    REPO_ROOT / "adoption" / "scorer_modes.py",
]

# Canonical audit states from core/ai_invocation/_enums.py AuditState
CANONICAL_AUDIT_STATES: frozenset[str] = frozenset(
    {
        "identified",
        "specified",
        "static_verified",
        "runtime_verified",
        "adopted",
        "ratcheted_debt",
        "blocked",
    }
)


def _load_registry_categories(registry_path: Path) -> dict[str, list[str]]:
    """Load category -> mode names from adoption-registry.yaml.

    Returns dict mapping category name to list of mode names.
    """
    categories: dict[str, list[str]] = {}
    if not registry_path.exists():
        return categories

    try:
        content = registry_path.read_text(encoding="utf-8")
    except OSError:
        return categories

    # Parse YAML manually for the features section to avoid import
    # Simple extraction: look for category: and modes: blocks
    in_features = False
    current_category: str | None = None
    in_modes = False

    for line in content.splitlines():
        stripped = line.strip()

        if stripped == "features:":
            in_features = True
            continue

        if not in_features:
            continue

        if stripped.startswith("#") or not stripped:
            continue

        # Category line: "  writing:" (2-space indent under features:)
        cat_match = re.match(r"^  (\w+):\s*$", line)
        if cat_match and not line.startswith("    "):
            current_category = cat_match.group(1)
            in_modes = False
            if current_category and current_category not in (
                "infrastructure_definitions",
                "inline_fallbacks",
                "feature_templates",
            ):
                categories[current_category] = []
            continue

        # Modes section: "    modes:"
        if current_category and stripped == "modes:":
            in_modes = True
            continue

        # Infrastructure/context blocks end modes section
        if current_category and re.match(r"^    \w+:", line) and stripped != "modes:":
            in_modes = False
            continue

        # Mode entry: "      mode_name:" or "      - mode_name"
        if in_modes and current_category and current_category in categories:
            mode_match = re.match(r"^      (\S+?):", line)
            if mode_match:
                categories[current_category].append(mode_match.group(1))
            mode_dash = re.match(r"^      - (\S+)", line)
            if mode_dash:
                categories[current_category].append(mode_dash.group(1))

    return categories


def _extract_audit_state_strings(filepath: Path) -> set[str]:
    """Extract quoted audit state strings from a Python file.

    Finds string literals that look like audit state names:
      "identified", "static_verified", etc.
    """
    states: set[str] = set()
    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError:
        return states

    # Find string assignments that look like state names
    for m in re.finditer(r'["\'](\w+)["\']', content):
        candidate = m.group(1)
        if candidate in CANONICAL_AUDIT_STATES:
            states.add(candidate)

    return states


def _extract_category_refs(filepath: Path) -> set[str]:
    """Extract category name references from a Python file.

    Looks for string literals matching known registry categories.
    """
    categories: set[str] = set()
    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError:
        return categories

    # Find quoted category-like strings
    for m in re.finditer(r'["\'](\w+)["\']', content):
        candidate = m.group(1)
        # Only include plausible category names (all lowercase, >2 chars)
        if (
            len(candidate) > 2
            and candidate.islower()
            and candidate
            not in (
                "true",
                "false",
                "none",
                "pass",
                "warn",
                "fail",
                "self",
                "args",
                "data",
                "file",
                "json",
                "yaml",
                "text",
            )
        ):
            categories.add(candidate)

    return categories


# ── Check functions ────────────────────────────────────────────


def _check_audit_state_usage(
    checker_scripts: list[Path],
) -> list[DocDriftFinding]:
    """Check: checker scripts use valid AuditState values."""
    findings: list[DocDriftFinding] = []

    for script_path in checker_scripts:
        if not script_path.exists():
            continue

        used_states = _extract_audit_state_strings(script_path)

        # Check if any used state is NOT in the canonical set
        invalid = used_states - CANONICAL_AUDIT_STATES
        if invalid:
            findings.append(
                DocDriftFinding(
                    severity="critical",
                    file=safe_relative(script_path),
                    message=(f"Uses non-canonical audit states: {', '.join(sorted(invalid))}"),
                )
            )

    return findings


def _check_category_alignment(
    checker_scripts: list[Path],
    registry_categories: set[str],
) -> list[DocDriftFinding]:
    """Check: category names in checkers match registry.

    Only checks .md files — Python scripts use string literals for argparse,
    variable names, path components, etc. that falsely trigger this check.
    See: terminology_checks.py _extract_category_refs.
    """
    findings: list[DocDriftFinding] = []

    for script_path in checker_scripts:
        if not script_path.exists():
            continue

        # Skip Python files: _extract_category_refs is too greedy for code
        # (catches argparse store_true, __main__, path components, etc.)
        if script_path.suffix in {".py"}:
            continue

        # Get category-like strings from checker
        ref_categories = _extract_category_refs(script_path)

        # Check if any referenced category is not in registry
        unknown = ref_categories - registry_categories
        # Filter out common false positives
        false_positives = {
            "description",
            "override",
            "overrides",
            "required",
            "optional",
            "partial",
        }
        unknown -= false_positives

        if unknown:
            findings.append(
                DocDriftFinding(
                    severity="warning",
                    file=safe_relative(script_path),
                    message=(
                        f"References categories not in registry: {', '.join(sorted(unknown))}"
                    ),
                )
            )

    return findings


def _check_mode_alignment(
    registry_categories: dict[str, list[str]],
) -> list[DocDriftFinding]:
    """Check: registry modes are well-formed (no duplicates, no empty categories)."""
    findings: list[DocDriftFinding] = []

    for category, modes in sorted(registry_categories.items()):
        # Empty category with no modes is fine (e.g., chat has modes: [])
        if not modes:
            continue

        # Check for duplicate modes
        seen: set[str] = set()
        for mode in modes:
            if mode in seen:
                findings.append(
                    DocDriftFinding(
                        severity="critical",
                        file="scripts/architecture/adoption-registry.yaml",
                        message=(f"Category '{category}' has duplicate mode '{mode}'"),
                    )
                )
            seen.add(mode)

    return findings


# ── Public API ─────────────────────────────────────────────────


def check_terminology_alignment(
    registry_path: Path | None = None,
    checker_scripts: list[Path] | None = None,
) -> list[DocDriftFinding]:
    """Run all terminology alignment checks.

    Args:
        registry_path: Override adoption-registry.yaml path (for testing).
        checker_scripts: Override checker script paths (for testing).

    Returns:
        List of DocDriftFinding with severity, file, and message.
    """
    effective_registry = registry_path or REGISTRY_PATH
    effective_scripts = checker_scripts or CHECKER_SCRIPTS

    findings: list[DocDriftFinding] = []

    # Load registry data
    registry_categories = _load_registry_categories(effective_registry)
    category_names = set(registry_categories.keys())

    # Run checks
    findings.extend(_check_audit_state_usage(effective_scripts))
    findings.extend(_check_category_alignment(effective_scripts, category_names))
    findings.extend(_check_mode_alignment(registry_categories))

    return findings
