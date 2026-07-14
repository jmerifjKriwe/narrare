"""Dismissed finding service — thin delegation to DismissedFindingRepository.

Persists user-dismissed consistency findings per novel so that re-running
a consistency check no longer resurfaces findings the user has reviewed
and consciously accepted (CR-AUFG-07-26).

This is a separate service from :class:`~narrare.kb.consistency_service.
KBConsistencyService` (which runs analysis) — dismiss-persistence is an
orthogonal concern (SRP / RULE-06).

See:
    :class:`narrare.kb.consistency_contracts.DismissedFindingProtocol`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.kb.consistency_contracts import (
    DismissedFindingRepositoryProtocol,
    DismissedFindingsResponse,
    DismissFindingRequest,
)

if TYPE_CHECKING:
    from uuid import UUID


class DismissedFindingService:
    """Thin service layer over :class:`DismissedFindingRepository`.

    Args:
        repo: The dismissed-finding repository (DB queries).
    """

    def __init__(self, repo: DismissedFindingRepositoryProtocol) -> None:
        self._repo = repo

    async def dismiss_finding(
        self,
        *,
        novel_id: UUID,
        request: DismissFindingRequest,
    ) -> DismissedFindingsResponse:
        """Dismiss a finding and return the updated dismissed list.

        Args:
            novel_id: The project the finding belongs to.
            request: The finding fingerprint and optional reason.

        Returns:
            Updated list of all dismissed fingerprints for the novel.
        """
        await self._repo.dismiss(novel_id, request.fingerprint, request.reason)
        fingerprints = await self._repo.list_dismissed(novel_id)
        return DismissedFindingsResponse(fingerprints=fingerprints)

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
        fingerprints = await self._repo.list_dismissed(novel_id)
        return DismissedFindingsResponse(fingerprints=fingerprints)

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
        await self._repo.undismiss(novel_id, fingerprint)
        fingerprints = await self._repo.list_dismissed(novel_id)
        return DismissedFindingsResponse(fingerprints=fingerprints)
