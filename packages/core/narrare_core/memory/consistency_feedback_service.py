"""Consistency-feedback service — stores/retrieves dismissed findings via mem0.

Implements the :class:`ConsistencyFeedbackCollector` protocol. Stores each
dismissed consistency finding as a mem0 memory scoped to user+project, and
retrieves past dismissals by semantic similarity so the consistency-check
flow can de-prioritise/suppress findings the user has already dismissed
(CR-AUFG-03-10).

This is the *semantic* learning layer sitting ON TOP of the per-novel
exact-fingerprint DB dismiss (CR-AUFG-07-26): the DB layer suppresses exact
``description::entity_names`` matches; this layer catches findings whose
fingerprint shifted across runs (LLM rephrased the description) but whose
meaning is unchanged, via mem0's pgvector hybrid search.

Every mem0 operation is best-effort (RULE-11): failures are logged warnings
and return a safe empty/no-op result — never raised — so the dismiss and
consistency-check flows never degrade because the learning layer is down.

Storage scope (v1): user+project (within-novel), mirroring ``FeedbackCollector``
/ ``SessionMemoryCollector`` (``user_id`` → mem0 ``user_id``, ``project_id`` →
mem0 ``agent_id``). Cross-novel learning is a future retrieve-filter change
that needs no data migration (the record carries ``user_id``).

Shape mapping (record ↔ mem0 message/metadata, score normalisation, result
filtering) lives in :mod:`narrare_core.memory._consistency_helpers`; this
module owns only mem0 orchestration + graceful degradation.

See:
    :mod:`narrare_core.memory.protocols` — ``ConsistencyFeedbackCollector``
    :mod:`narrare_core.memory.feedback_service` — canonical best-effort pattern
    docs/architecture/implementation-plans/cr-06-mem0-loops.md — design note
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.memory._consistency_helpers import (
    build_dismissal_message,
    build_dismissal_metadata,
    to_dismissal_match,
)

if TYPE_CHECKING:
    # Annotation-only imports (runtime construction lives in the helpers):
    # ``from __future__ import annotations`` stringifies all annotations, so
    # these names are never evaluated at runtime.
    from narrare_core.memory.consistency_models import (
        ConsistencyDismissalRecord,
        DismissalMatch,
    )

logger = structlog.get_logger(__name__)


class ConsistencyFeedbackService:
    """mem0-backed implementation of :class:`ConsistencyFeedbackCollector`.

    Follows the established best-effort pattern (``FeedbackService`` /
    ``SessionMemoryService``): the constructor takes an injected mem0 client
    (``AsyncMemory`` or ``NullMemoryClient``); every mem0 call is wrapped so a
    failure is a logged warning, never a raised error.

    Implements:
        ConsistencyFeedbackCollector protocol.
    """

    def __init__(self, mem0_client: Any) -> None:
        """Inject the mem0 client (AsyncMemory or NullMemoryClient)."""
        self._mem0 = mem0_client

    async def record_dismissal(
        self,
        user_id: object,
        project_id: object,
        record: ConsistencyDismissalRecord,
    ) -> None:
        """Forward a dismissal to mem0 for cross-run learning (best-effort).

        The record carries the authoritative ``user_id``/``project_id`` (UUID)
        used for mem0 scoping and metadata — mirroring ``FeedbackService``,
        which scopes via the event's identity fields. The method-level
        ``user_id``/``project_id`` are accepted for protocol conformance and
        are expected to equal the record's (the API caller builds the record
        from the same ids). Never raises: mem0 write failures are warnings.
        """
        try:
            await self._mem0.add(
                messages=build_dismissal_message(record),
                user_id=str(record.user_id),
                agent_id=str(record.project_id),
                metadata=build_dismissal_metadata(record),
            )
        except Exception:
            logger.warning(
                "consistency_dismissal_record_failed",
                fingerprint=record.fingerprint,
                project_id=str(record.project_id),
            )

    async def find_similar_dismissals(
        self,
        user_id: object,
        project_id: object,
        *,
        finding_description: str,
        limit: int = 10,
        similarity_threshold: float = 0.85,
    ) -> list[DismissalMatch]:
        """Retrieve past dismissals semantically similar to a finding.

        Queries mem0 (pgvector hybrid search) scoped to user+project, then
        post-filters to ``type == consistency_dismissal`` memories whose
        ``novel_id`` metadata matches ``project_id`` (defense-in-depth on top
        of mem0's ``agent_id`` scoping). Surviving results are kept only if
        their normalised score is ``>= similarity_threshold``, best-first
        (mem0 order preserved).

        Returns ``[]`` when mem0 is unavailable or returns nothing (graceful
        degradation, RULE-11).
        """
        try:
            result = await self._mem0.search(
                query=finding_description,
                filters={
                    "user_id": str(user_id),
                    "agent_id": str(project_id),
                },
                top_k=limit,
            )
        except Exception:
            logger.warning(
                "consistency_dismissal_query_failed",
                project_id=str(project_id),
            )
            return []

        # mem0 (AsyncMemory / NullMemoryClient) always returns a dict shaped
        # ``{"results": [...]}``; trusting that contract keeps types concrete
        # (matches ``SessionMemoryService``).
        memories = result.get("results", [])
        expected_novel_id = str(project_id)
        matches: list[DismissalMatch] = []
        for memory in memories:
            match = to_dismissal_match(memory, expected_novel_id)
            if match is not None and match.similarity >= similarity_threshold:
                matches.append(match)
        return matches
