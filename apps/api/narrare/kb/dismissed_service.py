"""Dismissed finding service — thin delegation to DismissedFindingRepository.

Persists user-dismissed consistency findings per novel so that re-running
a consistency check no longer resurfaces findings the user has reviewed
and consciously accepted (CR-AUFG-07-26).

After the per-novel DB dismiss succeeds, the service optionally forwards
the dismissal to a mem0-backed learning layer (CR-AUFG-03-10) so that
findings whose fingerprint shifted across runs (LLM rephrased the
description) are still recognised as already-dismissed. The mem0 write is
best-effort (RULE-11): a failure is a logged warning, never an error —
the DB dismiss is the source of truth and has already succeeded.

This is a separate service from :class:`narrare.kb.consistency_service.
KBConsistencyService` (which runs analysis) — dismiss-persistence is an
orthogonal concern (SRP / RULE-06).

See:
    :class:`narrare.kb.consistency_contracts.DismissedFindingProtocol`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb.consistency_contracts import (
    DismissedFindingRepositoryProtocol,
    DismissedFindingsResponse,
    DismissFindingRequest,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.memory.consistency_models import ConsistencyDismissalRecord
    from narrare_core.memory.protocols import ConsistencyFeedbackCollector

logger = structlog.get_logger(__name__)

# Sentinel for the category/severity fields when the dismiss request did not
# carry them. The frontend dismisses by fingerprint only, so these structural
# attributes are genuinely unknown at dismiss time. They are metadata-only —
# mem0's semantic match rides on ``finding_description``, not these tags.
_UNKNOWN_CATEGORY = "unknown"
_UNKNOWN_SEVERITY = "unknown"


def _parse_fingerprint(fingerprint: str) -> tuple[str, list[str]]:
    """Split ``{description}::{entity_names}`` into its parts.

    The fingerprint format mirrors the frontend ``consistencyFingerprint()``
    helper: ``description::sorted_entity_names.join(",")``. Splitting on the
    first ``::`` keeps descriptions that legitimately contain ``::`` intact.

    Args:
        fingerprint: The stable finding identifier.

    Returns:
        Tuple of ``(description, entity_names)``. When the separator is
        absent the whole string is the description and ``entity_names`` is
        empty — the record is still useful for semantic matching.
    """
    if "::" not in fingerprint:
        return fingerprint, []
    description, _, entities_part = fingerprint.partition("::")
    entity_names = [e for e in entities_part.split(",") if e]
    return description, entity_names


def _build_dismissal_record(
    *,
    user_id: str,
    project_id: UUID,
    request: DismissFindingRequest,
) -> ConsistencyDismissalRecord:
    """Build a mem0 dismissal record from the dismiss request.

    The request only carries the stable ``fingerprint`` and optional
    ``reason`` — the description and entity names are recovered by parsing
    the fingerprint, and category/severity are unknown at dismiss time
    (frontend dismisses by fingerprint only).

    Args:
        user_id: Authenticated user identifier (mem0 ``user_id`` scope).
        project_id: The novel (mem0 ``agent_id`` scope).
        request: The dismiss request carrying fingerprint + reason.

    Returns:
        A :class:`ConsistencyDismissalRecord` ready to forward to mem0.
    """
    from uuid import UUID

    from narrare_core.memory.consistency_models import ConsistencyDismissalRecord

    description, entity_names = _parse_fingerprint(request.fingerprint)
    return ConsistencyDismissalRecord(
        user_id=UUID(user_id),
        project_id=project_id,
        fingerprint=request.fingerprint,
        finding_description=description,
        entity_names=entity_names,
        category=_UNKNOWN_CATEGORY,
        severity=_UNKNOWN_SEVERITY,
        reason=request.reason,
    )


class DismissedFindingService:
    """Thin service layer over :class:`DismissedFindingRepository`.

    Args:
        repo: The dismissed-finding repository (DB queries).
        feedback_memory: Optional mem0-backed dismissal collector. When
            present, dismissals are forwarded to mem0 after the DB persist
            so future consistency checks can suppress semantically-equivalent
            findings (CR-AUFG-03-10). ``None`` (default) disables the
            learning layer — graceful degradation (RULE-11).
    """

    def __init__(
        self,
        repo: DismissedFindingRepositoryProtocol,
        feedback_memory: ConsistencyFeedbackCollector | None = None,
    ) -> None:
        self._repo = repo
        self._feedback_memory = feedback_memory

    async def dismiss_finding(
        self,
        *,
        novel_id: UUID,
        request: DismissFindingRequest,
        user_id: str | None = None,
    ) -> DismissedFindingsResponse:
        """Dismiss a finding and return the updated dismissed list.

        Persists the dismiss to the DB (source of truth), then — when a
        feedback memory and authenticated user are available — forwards the
        dismissal to mem0 for cross-run semantic learning (CR-AUFG-03-10).
        The mem0 write never breaks the DB dismiss (RULE-11): failures are
        logged warnings.

        Args:
            novel_id: The project the finding belongs to.
            request: The finding fingerprint and optional reason.
            user_id: Authenticated user identifier, required to scope the
                mem0 write. ``None`` skips the mem0 forward (DB dismiss
                still succeeds).

        Returns:
            Updated list of all dismissed fingerprints for the novel.
        """
        await self._repo.dismiss(novel_id, request.fingerprint, request.reason)
        await self._forward_to_feedback_memory(user_id, novel_id, request)
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

    # ------------------------------------------------------------------
    # mem0 learning-layer forward (best-effort, RULE-11)
    # ------------------------------------------------------------------

    async def _forward_to_feedback_memory(
        self,
        user_id: str | None,
        novel_id: UUID,
        request: DismissFindingRequest,
    ) -> None:
        """Forward the dismiss to mem0 for cross-run learning (best-effort).

        No-op when ``feedback_memory`` or ``user_id`` is ``None`` (graceful
        degradation). Never raises: a mem0 write failure is a logged warning
        so the DB dismiss — the source of truth — stays intact.
        """
        if self._feedback_memory is None or user_id is None:
            return
        try:
            record = _build_dismissal_record(
                user_id=user_id,
                project_id=novel_id,
                request=request,
            )
            await self._feedback_memory.record_dismissal(user_id, novel_id, record)
        except Exception:
            logger.warning(
                "consistency_dismissal_forward_failed",
                fingerprint=request.fingerprint,
                project_id=str(novel_id),
            )
