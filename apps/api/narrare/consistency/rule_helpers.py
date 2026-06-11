"""Rule-based consistency helpers — deterministic checks and deduplication.

Pure functions (no I/O, no service dependencies) for CONS-001 pre-check
and post-processing. Extracted from checker_service.py to stay under the
300-line service limit (RULE-04).

See:
    :mod:`narrare.consistency.checker_service` — Service that calls these helpers.
"""

from __future__ import annotations

from typing import cast

import structlog

from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyIssue,
    ConsistencySeverity,
)

logger = structlog.get_logger(__name__)


def rule_based_check(
    kb_summaries: list[dict[str, object]],
) -> list[ConsistencyIssue]:
    """Direct field comparison for obvious KB contradictions.

    Runs BEFORE the LLM agent call. Detects same-name entities with
    conflicting metadata fields — guaranteed correct (no false positives).

    This is a pure function with no I/O or service dependencies.

    Args:
        kb_summaries: KB entity summaries with ``entity_type``, ``name``,
            and ``fields`` keys. Each ``fields`` value should be a dict
            mapping field names to values.

    Returns:
        List of deterministic issues with ``confidence=1.0``.
        Empty list if no KB summaries or no conflicts found.
    """
    if not kb_summaries:
        return []

    # Group by normalised name for cross-entity comparison
    by_name: dict[str, list[dict[str, object]]] = {}
    for entry in kb_summaries:
        name = str(entry.get("name", "")).strip().lower()
        if name:
            by_name.setdefault(name, []).append(entry)

    issues: list[ConsistencyIssue] = []
    for name, entries in by_name.items():
        if len(entries) < 2:
            continue

        # Extract fields dicts, skipping entries without structured fields
        field_maps: list[dict[str, object]] = []
        for e in entries:
            raw_fields = e.get("fields")
            if isinstance(raw_fields, dict):
                field_maps.append(cast("dict[str, object]", raw_fields))

        if len(field_maps) < 2:
            continue

        # Collect all field keys present in more than one entry
        key_counts: dict[str, int] = {}
        for fields in field_maps:
            for key in fields:
                key_counts[key] = key_counts.get(key, 0) + 1

        for field_key, count in key_counts.items():
            if count < 2:
                continue

            # Gather values for this field across entries
            values: set[str] = set()
            facts: list[str] = []
            for idx, fields in enumerate(field_maps):
                val = fields.get(field_key)
                if val is None:
                    continue
                val_str = str(val).strip()
                if val_str:
                    values.add(val_str.lower())
                    entity_name = entries[idx].get("name", name)
                    facts.append(f"{entity_name}.{field_key} = {val_str}")

            if len(values) > 1:
                display_name = str(entries[0].get("name", name))
                issues.append(
                    ConsistencyIssue(
                        check_type=ConsistencyCheckType.CHARACTER,
                        severity=ConsistencySeverity.WARNING,
                        description=(
                            f"Entity '{display_name}' has conflicting "
                            f"'{field_key}' values: {', '.join(values)}"
                        ),
                        locations=["Knowledge Base"],
                        conflicting_facts=facts,
                        suggestion=f"Unify the '{field_key}' field for '{display_name}'.",
                        confidence=1.0,
                    )
                )

    if issues:
        logger.debug(
            "consistency_rule_based_issues",
            issue_count=len(issues),
        )
    return issues


def deduplicate_issues(
    issues: list[ConsistencyIssue],
) -> list[ConsistencyIssue]:
    """Remove near-duplicate issues.

    Two issues are considered duplicates if they share the same
    ``check_type``, ``severity``, and first 50 characters of ``description``.
    Preserves insertion order (first occurrence wins).

    This is a pure function with no I/O or service dependencies.

    Args:
        issues: Combined list of rule-based + LLM issues.

    Returns:
        Deduplicated list preserving insertion order.
    """
    seen: set[str] = set()
    deduped: list[ConsistencyIssue] = []
    for issue in issues:
        key = f"{issue.check_type}:{issue.severity}:{issue.description[:50]}"
        if key not in seen:
            seen.add(key)
            deduped.append(issue)

    removed = len(issues) - len(deduped)
    if removed:
        logger.debug(
            "consistency_deduplication",
            removed_count=removed,
            remaining_count=len(deduped),
        )
    return deduped
