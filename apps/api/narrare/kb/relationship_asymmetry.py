"""Relationship asymmetry checker — detects inconsistent reciprocal relationships.

Pure algorithmic — no LLM calls. Uses INVERSE_SUGGESTIONS from
relationship_service to validate reciprocal relationship consistency.

For each relationship A→B with rel_type X:
- Check if there's a reciprocal B→A with the expected inverse type
- If the reciprocal exists but with wrong type → warning (MINOR)
- If no reciprocal exists but one is expected → info (INFO)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.kb.consistency_contracts import RelationshipAsymmetry
from narrare.kb.worldbuilding_contracts import WorldbuildingSeverity

if TYPE_CHECKING:
    from narrare.kb.contracts import RelationshipRepositoryProtocol
    from narrare.kb.relationship_service import RelationshipService

logger = structlog.get_logger(__name__)

# Severity ordering for sorting results
_SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "major": 1,
    "minor": 2,
    "info": 3,
}


class RelationshipAsymmetryChecker:
    """Detects asymmetric reciprocal relationships in a project's KB.

    For each relationship A→B with rel_type X:
    - Check if there's a reciprocal B→A with the expected inverse type
    - If the reciprocal exists but with wrong type → warning (MINOR)
    - If no reciprocal exists but one is expected → info (INFO)
    """

    def __init__(
        self,
        rel_repo: RelationshipRepositoryProtocol,
        rel_service: RelationshipService,
    ) -> None:
        self._rel_repo = rel_repo
        self._rel_service = rel_service

    async def check(
        self,
        novel_id: UUID,
        entity_names: dict[str, str] | None = None,
    ) -> list[RelationshipAsymmetry]:
        """Run asymmetry check on all relationships in the project.

        Args:
            novel_id: The project to check.
            entity_names: Optional mapping of entity_id → entity_name for display.

        Returns:
            List of detected asymmetries, sorted by severity.
        """
        adjacency = await self._rel_repo.get_adjacency_map(novel_id)

        issues: list[RelationshipAsymmetry] = []
        seen_pairs: set[frozenset[str]] = set()
        names = entity_names or {}

        for entity_id_str, connected_ids in adjacency.items():
            for other_id_str in connected_ids:
                pair = frozenset({entity_id_str, other_id_str})
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                # Get outgoing relationships: entity → other
                entity_rels = await self._rel_repo.list_for_entry(
                    entry_id=UUID(entity_id_str),
                    direction="outgoing",
                )
                forward_types = [
                    r.rel_type for r in entity_rels if str(r.target_id) == other_id_str
                ]

                # Get outgoing relationships: other → entity
                other_rels = await self._rel_repo.list_for_entry(
                    entry_id=UUID(other_id_str),
                    direction="outgoing",
                )
                reverse_types = [
                    r.rel_type for r in other_rels if str(r.target_id) == entity_id_str
                ]

                # Check each forward rel for expected inverse
                for fwd_type in forward_types:
                    expected_inverse = self._rel_service.get_inverse_suggestion(
                        fwd_type,
                    )

                    if expected_inverse is None:
                        continue  # No inverse expected for this rel_type

                    reverse_matches = [rt for rt in reverse_types if rt == expected_inverse]

                    source_name = names.get(entity_id_str, entity_id_str[:8])
                    target_name = names.get(other_id_str, other_id_str[:8])

                    if not reverse_types:
                        # No reverse relationship at all
                        issues.append(
                            RelationshipAsymmetry(
                                source_id=entity_id_str,
                                source_name=source_name,
                                target_id=other_id_str,
                                target_name=target_name,
                                forward_rel_type=fwd_type,
                                reverse_rel_type=None,
                                expected_inverse=expected_inverse,
                                severity=WorldbuildingSeverity.INFO,
                            )
                        )
                    elif not reverse_matches:
                        # Reverse exists but with wrong type
                        actual_reverse = ", ".join(reverse_types)
                        issues.append(
                            RelationshipAsymmetry(
                                source_id=entity_id_str,
                                source_name=source_name,
                                target_id=other_id_str,
                                target_name=target_name,
                                forward_rel_type=fwd_type,
                                reverse_rel_type=actual_reverse,
                                expected_inverse=expected_inverse,
                                severity=WorldbuildingSeverity.MINOR,
                            )
                        )

        # Sort by severity (critical first)
        issues.sort(
            key=lambda a: _SEVERITY_ORDER.get(a.severity.value, 4),
        )

        logger.info(
            "asymmetry_check_complete",
            novel_id=str(novel_id),
            pairs_checked=len(seen_pairs),
            issues_found=len(issues),
        )

        return issues
