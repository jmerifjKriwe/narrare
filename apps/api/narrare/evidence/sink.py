"""PostgreSQL-backed evidence sink.

Implements the ``FeatureInvocationEvidenceSink`` protocol (from Core).
Writes invocation evidence to the ``invocation_evidence`` table via the
``EvidenceRepository``. Lives in Backend (``apps/api/``) — not in Core —
to keep Core DB-agnostic (RULE-07).

See ADR-042 for the hybrid evidence architecture.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.evidence.repository import EvidenceRepositoryImpl

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare_core.ai_invocation.models import FeatureInvocationEvidence


class PersistentEvidenceSink:
    """PostgreSQL-backed evidence sink for production use.

    Implements the ``FeatureInvocationEvidenceSink`` protocol.
    Each ``record()`` call acquires its own session from the factory.
    DB errors are logged but never block the invocation pipeline.

    Args:
        session_factory: Callable returning an ``AsyncSession``.
            Each ``record()`` call gets a fresh session — the sink
            never holds sessions across calls.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._logger = structlog.get_logger("narrare.invocation.evidence.persistent")

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        """Persist evidence to PostgreSQL.

        On DB error: logs a warning and returns (never blocks the pipeline).

        Args:
            evidence: Privacy-safe evidence record from an AI invocation.
        """
        try:
            async with self._session_factory() as session:
                repo = EvidenceRepositoryImpl(session=session)
                await repo.save(evidence)
                await session.commit()
        except Exception as exc:
            self._logger.warning(
                "evidence_db_write_failed",
                error=str(exc),
                feature_id=evidence.feature_id,
                intent=evidence.intent,
            )
