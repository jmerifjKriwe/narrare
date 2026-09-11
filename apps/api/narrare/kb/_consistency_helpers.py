"""Consistency analysis helpers — extracted from consistency_service.py (RULE-04).

Pure functions for converting relationship asymmetries to issues and
generating candidate entity pairs for cross-entity analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.kb.worldbuilding_contracts import ConsistencyCategory, ConsistencyIssue

if TYPE_CHECKING:
    from narrare.kb.consistency_contracts import RelationshipAsymmetry

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def asymmetry_to_issue(idx: int, a: RelationshipAsymmetry) -> ConsistencyIssue:
    """Convert a :class:`RelationshipAsymmetry` to a :class:`ConsistencyIssue`."""
    return ConsistencyIssue(
        finding_index=idx,
        category=ConsistencyCategory.RELATIONSHIP_ASYMMETRY,
        entity_ids=[a.source_id, a.target_id],
        entity_names=[a.source_name, a.target_name],
        description=(
            f"Asymmetric relationship: {a.source_name} \u2192 {a.target_name} "
            f"({a.forward_rel_type})"
        ),
        contradiction=(
            f"Forward: {a.forward_rel_type}, "
            f"Reverse: {a.reverse_rel_type or 'none'}, "
            f"Expected: {a.expected_inverse or 'none'}"
        ),
        suggested_resolution=(
            f"Add {a.expected_inverse} relationship from {a.target_name} to {a.source_name}"
        )
        if a.expected_inverse
        else None,
        severity=a.severity,
        confidence=1.0,  # Algorithmic — deterministic
    )


# Severity ranking for report ordering (critical first). Shared by
# ``consistency_service.check`` — moved here (IDOR fix S9, RULE-04) to
# keep the service under the file-size limit.
SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "major": 1,
    "minor": 2,
    "info": 3,
}


def generate_candidate_pairs(
    adjacency: dict[str, set[str]],
    max_pairs: int = 15,
) -> list[tuple[str, str]]:
    """Generate entity pairs from existing relationships for cross-entity check.

    Uses the adjacency map to find connected entity pairs, deduplicating
    by unordered pair.  Only pairs with actual relationships are included —
    the most likely source of cross-entity consistency issues.
    """
    pairs: list[tuple[str, str]] = []
    seen: set[frozenset[str]] = set()

    for entity_id, connected in adjacency.items():
        for other_id in connected:
            pair = frozenset({entity_id, other_id})
            if pair not in seen:
                seen.add(pair)
                pairs.append((entity_id, other_id))
                if len(pairs) >= max_pairs:
                    return pairs
    return pairs
