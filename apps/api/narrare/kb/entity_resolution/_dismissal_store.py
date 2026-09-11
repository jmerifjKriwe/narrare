"""Dismissal ledger adapter for rejected resolution suggestions (spec §7).

Persists rejections in the EXISTING ``dismissed_findings`` fingerprint
table — the consistency-dismissal pattern (novel-scoped fingerprint
string + idempotent upsert) — under a reserved ``resolution:``
namespace. No migration, and the namespaces stay disjoint: consistency
suppression compares its own ``description::entities`` fingerprints and
can never collide with ``resolution:<hex16>``, while the resolution read
path (analysis service + endorse re-validation) only ever sees
prefix-stripped resolution ids.

Implements
:class:`~narrare.kb.entity_resolution.contracts.DismissedSuggestionStoreProtocol`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.dismissed_repository import DismissedFindingRepository

_FINGERPRINT_PREFIX: Final[str] = "resolution:"
"""Reserved namespace inside ``dismissed_findings.fingerprint``."""


class ResolutionDismissalStore:
    """Rejection ledger for resolution suggestions over the existing table.

    Args:
        repo: The dismissed-finding repository (DB queries only).
    """

    def __init__(self, repo: DismissedFindingRepository) -> None:
        self._repo = repo

    async def dismiss(self, novel_id: UUID, suggestion_id: str) -> None:
        """Persist a rejection (idempotent upsert, existing pattern)."""
        await self._repo.dismiss(novel_id, f"{_FINGERPRINT_PREFIX}{suggestion_id}")

    async def rejected_ids(self, novel_id: UUID) -> frozenset[str]:
        """Return the novel's rejected suggestion ids (namespace-stripped)."""
        fingerprints = await self._repo.list_dismissed(novel_id)
        return frozenset(
            fp[len(_FINGERPRINT_PREFIX) :]
            for fp in fingerprints
            if fp.startswith(_FINGERPRINT_PREFIX)
        )
