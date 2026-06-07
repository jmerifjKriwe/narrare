"""Protocol definitions for the evidence repository layer.

Defines ``EvidenceRepository`` — the contract that all evidence
repository implementations must satisfy. Written before any
implementation (RULE-03).

See ADR-042 § Contracts for design context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from narrare_core.ai_invocation.models import (
        AuditState,
        FeatureInvocationEvidence,
    )


@runtime_checkable
class EvidenceRepository(Protocol):
    """Repository for persistent evidence records.

    Encapsulates all DB access for the ``invocation_evidence`` table.
    Query methods support the adoption scorer, quality joiner, and
    audit report use cases (ADR-040, ADR-042).
    """

    async def save(self, evidence: FeatureInvocationEvidence) -> None:
        """Persist a single evidence record.

        Args:
            evidence: Privacy-safe evidence record from an AI invocation.
        """
        ...

    async def count_by_feature(
        self,
        feature_id: str,
        *,
        since: datetime | None = None,
    ) -> int:
        """Count evidence records for a feature.

        Args:
            feature_id: Feature identifier.
            since: Optional timestamp — only count records after this time.

        Returns:
            Number of matching evidence records.
        """
        ...

    async def get_distinct_modes(
        self,
        feature_id: str,
    ) -> list[str]:
        """Get all distinct modes recorded for a feature.

        Args:
            feature_id: Feature identifier.

        Returns:
            List of distinct mode strings.
        """
        ...

    async def get_by_feature_and_mode(
        self,
        feature_id: str,
        mode: str,
        *,
        limit: int = 100,
    ) -> list[FeatureInvocationEvidence]:
        """Get evidence records for a specific feature and mode.

        Args:
            feature_id: Feature identifier.
            mode: Mode name.
            limit: Maximum records to return (default 100).

        Returns:
            List of evidence records, newest first.
        """
        ...

    async def get_latest_audit_state(
        self,
        feature_id: str,
        mode: str | None = None,
    ) -> AuditState | None:
        """Get the most recent audit state for a feature (and optional mode).

        Args:
            feature_id: Feature identifier.
            mode: Optional mode filter.

        Returns:
            The latest ``AuditState`` value, or ``None`` if no records exist.
        """
        ...
