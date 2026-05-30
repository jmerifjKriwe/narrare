"""PROMPT-QUALITY · Content quality checks for bundled prompts.

Ensures bundled prompts with ``prompt_type`` frontmatter contain:
- Role assignment (language-appropriate: EN/DE/FR)
- Output format specification
- At least 3 Do-NOT / negative-behaviour rules

Exemptions:
- Fragment files (no ``prompt_type`` frontmatter) — skipped entirely
- ``prompt_type: meta`` — exempt from output format requirement
- ``system.lite.md`` — exempt from role assignment requirement

Uses multilingual patterns from ``_prompt_quality_patterns.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.architecture._checkers._prompt_quality_patterns import (
    OUTPUT_FORMAT_PATTERNS,
    ROLE_PATTERNS,
    count_do_not_rules,
    has_second_person_role_sentence,
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityFinding:
    """A single content-quality finding for a prompt file."""

    detail: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_DO_NOT_RULES: int = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_prompt_content_quality(
    filepath: str,
    lines: list[str],
) -> list[QualityFinding]:
    """Check a prompt file for content quality patterns.

    Args:
        filepath: Relative path of the prompt file (used for exemptions).
        lines: File content as list of lines (including frontmatter).

    Returns:
        List of :class:`QualityFinding` objects — empty if all checks pass.
    """
    metadata, content_lines = _parse_frontmatter(lines)

    # Fragment files (no prompt_type) are excluded from quality checks.
    if "prompt_type" not in metadata:
        return []

    content = "\n".join(content_lines)
    content_lower = content.lower()
    prompt_type = metadata.get("prompt_type", "")
    filename = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath

    findings: list[QualityFinding] = []

    # --- Role assignment (exempt system.lite.md) ---
    if filename != "system.lite.md" and not _has_role(content, content_lower):
        findings.append(
            QualityFinding(
                detail=(
                    "No role assignment found (expected 'You are', "
                    "'Du bist', 'Tu es', or second-person sentence)"
                ),
            ),
        )

    # --- Output format (exempt meta prompts) ---
    if prompt_type != "meta" and not _has_output_format(content_lower):
        findings.append(
            QualityFinding(detail="No output format specification found"),
        )

    # --- Do-NOT rules ---
    do_not_count = count_do_not_rules(content, content_lower)
    if do_not_count < _MIN_DO_NOT_RULES:
        findings.append(
            QualityFinding(
                detail=(f"Do-NOT rules: found {do_not_count}, need at least {_MIN_DO_NOT_RULES}"),
            ),
        )

    return findings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Parse simple YAML frontmatter delimited by ``---`` lines."""
    if not lines or lines[0].strip() != "---":
        return {}, lines

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, lines

    metadata: dict[str, str] = {}
    for line in lines[1:end_idx]:
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip().strip('"').strip("'")

    return metadata, lines[end_idx + 1 :]


def _has_role(content: str, content_lower: str) -> bool:
    """Check for declarative or second-person role assignment."""
    for pattern in ROLE_PATTERNS:
        if pattern in content_lower:
            return True
    return has_second_person_role_sentence(content)


def _has_output_format(content_lower: str) -> bool:
    """Check for output format specification."""
    return any(pattern in content_lower for pattern in OUTPUT_FORMAT_PATTERNS)
