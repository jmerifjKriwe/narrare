"""KB Consistency Check service contract — Protocol definitions.

Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

from .worldbuilding_contracts import ConsistencyIssue, WorldbuildingSeverity

if TYPE_CHECKING:
    from uuid import UUID


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------


class ConsistencyCheckRequest(BaseModel):
    """Request to run a consistency check.

    Attributes:
        entity_types: Optional filter — check only specific entity types.
            When None, checks all types present in the project.
        include_entry_internal: Whether to check entry-internal consistency (LLM).
        include_asymmetry: Whether to check relationship asymmetry (algorithmic).
        include_cross_entity: Whether to check cross-entity consistency (LLM via KB-006b).
        refresh: If True, bypass cache and force fresh analysis.
    """

    entity_types: list[str] | None = None
    include_entry_internal: bool = True
    include_asymmetry: bool = True
    include_cross_entity: bool = True
    refresh: bool = False


class ConsistencyCheckResponse(BaseModel):
    """Response from a consistency check.

    Attributes:
        novel_id: The project that was checked.
        entity_count: How many entities were analyzed.
        issues: All consistency issues found, sorted by severity (critical first).
        summary: Breakdown counts by category.
        checked_at: When the check was performed.
    """

    novel_id: str
    entity_count: int
    issues: list[ConsistencyIssue]
    summary: dict[str, int]  # {"entry_internal": 3, "asymmetry": 2, "cross_entity": 1}
    checked_at: str  # ISO datetime string


# ---------------------------------------------------------------------------
# Asymmetry Result Type
# ---------------------------------------------------------------------------


class RelationshipAsymmetry(BaseModel):
    """A single detected relationship asymmetry.

    Attributes:
        source_id: Entity ID of the source in the original relationship.
        source_name: Name of the source entity.
        target_id: Entity ID of the target in the original relationship.
        target_name: Name of the target entity.
        forward_rel_type: The relationship type from source → target.
        reverse_rel_type: The relationship type from target → source (if any).
        expected_inverse: What the inverse should be based on INVERSE_SUGGESTIONS.
        severity: How concerning this asymmetry is.
    """

    source_id: str
    source_name: str
    target_id: str
    target_name: str
    forward_rel_type: str
    reverse_rel_type: str | None
    expected_inverse: str | None
    severity: WorldbuildingSeverity = WorldbuildingSeverity.MINOR


# ---------------------------------------------------------------------------
# Consistency Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class KBConsistencyProtocol(Protocol):
    """Protocol for KB consistency checking.

    Combines three analysis sources into a single consistency report:
    - Entry-internal: LLM-based per-entry field contradiction detection
    - Relationship asymmetry: algorithmic reciprocal relationship validation
    - Cross-entity: LLM-based entity-pair contradiction detection (reuses KB-006b)
    """

    async def check(
        self,
        *,
        novel_id: UUID,
        request: ConsistencyCheckRequest,
    ) -> ConsistencyCheckResponse:
        """Run a consistency check on the project's KB.

        Args:
            novel_id: The project to check.
            request: Check options and filters.

        Returns:
            Complete consistency report with all requested issue types.
        """
        ...


# ---------------------------------------------------------------------------
# Dismissed Findings (CR-AUFG-07-26)
# ---------------------------------------------------------------------------


class DismissFindingRequest(BaseModel):
    """Request to dismiss (ignore) a consistency finding.

    The fingerprint is a stable key that survives re-runs — it matches the
    frontend ``issueKey()`` function: ``description::entity_names.join(",")``.
    Using ``finding_index`` would be unstable because indices shift between
    runs when findings are added or removed.

    Attributes:
        fingerprint: Stable finding identifier (description::entities).
        reason: Optional user-provided reason for dismissing the finding.
    """

    fingerprint: str
    reason: str | None = None


class DismissedFindingsResponse(BaseModel):
    """Response listing dismissed consistency finding fingerprints.

    Attributes:
        fingerprints: Stable fingerprints of all dismissed findings for a novel.
    """

    fingerprints: list[str]


@runtime_checkable
class DismissedFindingRepositoryProtocol(Protocol):
    """Protocol for dismissed-finding persistence operations.

    Defined as a Protocol (not the concrete class) so the service can be
    unit-tested with an in-memory fake without ``cast``.
    """

    async def dismiss(
        self,
        novel_id: UUID,
        fingerprint: str,
        reason: str | None = None,
    ) -> None: ...

    async def list_dismissed(self, novel_id: UUID) -> list[str]: ...

    async def undismiss(self, novel_id: UUID, fingerprint: str) -> bool: ...


@runtime_checkable
class DismissedFindingProtocol(Protocol):
    """Protocol for dismissing consistency findings.

    Persisted per-novel so that findings a user has consciously reviewed and
    accepted can be hidden from future consistency checks.  The frontend
    fetches the dismissed fingerprint list and filters issues client-side.
    """

    async def dismiss_finding(
        self,
        *,
        novel_id: UUID,
        request: DismissFindingRequest,
    ) -> DismissedFindingsResponse:
        """Dismiss a finding by its stable fingerprint (idempotent upsert).

        Args:
            novel_id: The project the finding belongs to.
            request: The finding fingerprint and optional reason.

        Returns:
            Updated list of all dismissed fingerprints for the novel.
        """
        ...

    async def list_dismissed(
        self,
        *,
        novel_id: UUID,
    ) -> DismissedFindingsResponse:
        """List all dismissed finding fingerprints for a novel.

        Args:
            novel_id: The project to list dismissed findings for.

        Returns:
            All currently-dismissed fingerprints for the novel.
        """
        ...

    async def undismiss_finding(
        self,
        *,
        novel_id: UUID,
        fingerprint: str,
    ) -> DismissedFindingsResponse:
        """Re-enable a previously dismissed finding.

        Args:
            novel_id: The project the finding belongs to.
            fingerprint: The stable fingerprint to un-dismiss.

        Returns:
            Updated list of all dismissed fingerprints for the novel.
        """
        ...
