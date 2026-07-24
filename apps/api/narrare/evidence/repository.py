"""Evidence repository — DB queries only (RULE-07: repo → DB).

Persistence layer for the ``invocation_evidence`` table. Maps between
``InvocationEvidenceModel`` (ORM) and ``FeatureInvocationEvidence`` (domain)
via the helpers in ``_mappers.py``. All SQLAlchemy queries live here —
services never write SQL directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import JSONB

from narrare._app.base_repository import BaseRepository
from narrare.evidence._mappers import domain_to_orm, orm_to_domain
from narrare.evidence.models import InvocationEvidenceModel

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare_core.ai_invocation.models import (
        AuditState,
        FeatureInvocationEvidence,
    )


class EvidenceRepositoryImpl(BaseRepository):
    """PostgreSQL-backed evidence repository.

    All evidence queries use the ``invocation_evidence`` table with
    appropriate indices for adoption scoring, quality metrics, and
    audit report use cases.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def save(self, evidence: FeatureInvocationEvidence) -> None:
        """Persist a single evidence record.

        Args:
            evidence: Privacy-safe evidence record from an AI invocation.
        """
        values = domain_to_orm(evidence)
        model = InvocationEvidenceModel(**cast("dict[str, Any]", values))
        self._session.add(model)
        await self._flush()

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
        stmt = (
            select(func.count())
            .select_from(InvocationEvidenceModel)
            .where(
                InvocationEvidenceModel.feature_id == feature_id,
            )
        )
        if since is not None:
            stmt = stmt.where(InvocationEvidenceModel.created_at >= since)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_distinct_modes(
        self,
        feature_id: str,
    ) -> list[str]:
        """Get all distinct modes recorded for a feature.

        Args:
            feature_id: Feature identifier.

        Returns:
            List of distinct mode strings (NULL omitted).
        """
        stmt = (
            select(func.distinct(InvocationEvidenceModel.mode))
            .where(InvocationEvidenceModel.feature_id == feature_id)
            .where(InvocationEvidenceModel.mode.isnot(None))
            .order_by(InvocationEvidenceModel.mode)
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

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
        stmt = (
            select(InvocationEvidenceModel)
            .where(InvocationEvidenceModel.feature_id == feature_id)
            .where(InvocationEvidenceModel.mode == mode)
            .order_by(InvocationEvidenceModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [orm_to_domain(row) for row in result.scalars()]

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
        stmt = (
            select(InvocationEvidenceModel.audit_state)
            .where(InvocationEvidenceModel.feature_id == feature_id)
            .order_by(InvocationEvidenceModel.created_at.desc())
            .limit(1)
        )
        if mode is not None:
            stmt = stmt.where(InvocationEvidenceModel.mode == mode)

        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        from narrare_core.ai_invocation.models import AuditState

        return AuditState(row)

    async def update_adaptive_snapshot(
        self,
        *,
        invocation_id: UUID,
        source_summary: dict[str, str],
        weights: dict[str, float],
    ) -> None:
        """Update the adaptive columns on an existing invocation_evidence row.

        Called by AdaptiveContextProviderImpl.record_snapshot() after an
        adaptive-consuming invocation completes (ADR-069 Decision 11).

        Args:
            invocation_id: The evidence row's invocation_id.
            source_summary: Privacy-safe summary dict.
            weights: Active weights at invocation time.

        Note:
            No-op (logged at INFO) if no evidence row matches — invocation
            evidence is best-effort and MUST NOT block the AI call.
        """
        from sqlalchemy import update

        stmt = (
            update(InvocationEvidenceModel)
            .where(InvocationEvidenceModel.invocation_id == invocation_id)
            .values(
                adaptive_source_summary=source_summary,
                adaptive_weights=weights,
            )
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[union-attr]
            import structlog

            structlog.get_logger(__name__).info(
                "adaptive_snapshot_no_evidence_row",
                invocation_id=str(invocation_id),
            )

    async def get_adaptive_snapshots(
        self,
        novel_id: UUID,
        *,
        limit: int = 20,
    ) -> list[FeatureInvocationEvidence]:
        """List per-novel adaptive snapshots, newest first (ADR-070).

        Returns only rows that actually consumed adaptive context and are
        scoped to ``novel_id``. Legacy rows with NULL ``novel_id`` are
        correctly absent — they are unattributable.

        The ``adaptive_source_summary`` filter excludes BOTH null kinds:

        * SQL ``NULL`` — pre-migration-0034 rows and any row whose
          ``novel_id`` could not be attributed.
        * JSON ``null`` — the asyncpg + SQLAlchemy JSONB codec persists a
          Python ``None`` as jsonb ``'null'`` (a valid, non-NULL JSONB
          value) rather than SQL ``NULL``. A bare ``IS NOT NULL`` would
          therefore leak non-adaptive rows, so an explicit
          ``!= JSONB.NULL`` guard is required.

        Args:
            novel_id: The novel/project UUID to scope by.
            limit: Maximum records to return (default 20).

        Returns:
            Evidence records newest-first, each carrying ``created_at``.
        """
        summary = InvocationEvidenceModel.adaptive_source_summary
        stmt = (
            select(InvocationEvidenceModel)
            .where(InvocationEvidenceModel.novel_id == novel_id)
            .where(summary.isnot(None))
            .where(summary != JSONB.NULL)
            .order_by(InvocationEvidenceModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [orm_to_domain(row) for row in result.scalars()]
