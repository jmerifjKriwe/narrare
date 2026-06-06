"""KG/KB consistency types for the AI invocation adoption contract.

Shared vocabulary between KBConsistencyEnricher (runtime) and
Platform consistency checker (static CI).

See:
    ADR-040, INFRA-013 §P2, CONSTRAINTS.md RULE-03/RULE-06.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class EntityType(StrEnum):
    """KB entity types that can be checked for consistency."""

    CHARACTER = "character"
    LOCATION = "location"
    FACTION = "faction"
    ITEM = "item"
    EVENT = "event"


class ConsistencyStatus(StrEnum):
    """Status of a single consistency check."""

    PRESENT = "present"
    MISSING = "missing"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class EntityTypeCheck:
    """Result of checking whether a required entity type is present."""

    entity_type: str
    status: ConsistencyStatus
    count: int = 0
    detail: str = ""


@dataclass(frozen=True)
class KBConsistencyResult:
    """Result of a full KB consistency check.

    Produced by KBConsistencyEnricher at runtime and by the
    Platform consistency checker for static CI validation.
    """

    entity_type_checks: tuple[EntityTypeCheck, ...] = ()
    orphan_references: tuple[str, ...] = ()
    freshness_warnings: tuple[str, ...] = ()
    has_all_required_types: bool = False
    has_orphan_references: bool = False
    has_stale_profiles: bool = False

    @property
    def is_consistent(self) -> bool:
        """Whether all consistency checks pass."""
        return (
            self.has_all_required_types
            and not self.has_orphan_references
            and not self.has_stale_profiles
        )


class KBConsistencyCheck(Protocol):
    """Interface for KB consistency checking.

    Implemented by KBConsistencyEnricher (runtime) and potentially
    by the Platform checker (static).
    """

    async def check_consistency(
        self,
        project_id: object,
        *,
        required_types: frozenset[str] | None = None,
    ) -> KBConsistencyResult:
        """Check KB consistency for a project.

        Args:
            project_id: Project identifier.
            required_types: Entity types that must be present.
                None = use system defaults.

        Returns:
            KBConsistencyResult with all check outcomes.
        """
        ...
