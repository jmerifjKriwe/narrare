"""Evidence repository — DB queries only (RULE-07: repo → DB).

Persistence layer for the ``invocation_evidence`` table. Maps between
``InvocationEvidenceModel`` (ORM) and ``FeatureInvocationEvidence`` (domain).
All SQLAlchemy queries live here — services never write SQL directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from narrare._app.base_repository import BaseRepository
from narrare.evidence.models import InvocationEvidenceModel

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare_core.ai_invocation.models import (
        AuditState,
        FeatureInvocationEvidence,
    )


def _domain_to_orm(evidence: FeatureInvocationEvidence) -> dict[str, object]:
    """Convert a domain evidence record to ORM column values.

    Args:
        evidence: Privacy-safe evidence record from an AI invocation.

    Returns:
        Dict of ORM column names to values.
    """
    return {
        "feature_id": evidence.feature_id,
        "intent": evidence.intent,
        "mode": evidence.mode,
        "prompt_route": evidence.prompt_route,
        "preference_status": str(evidence.preference_status),
        "kb_suggested_status": str(evidence.kb_suggested_status),
        "voice_profile_status": str(evidence.voice_profile_status)
        if evidence.voice_profile_status
        else None,
        "output_budget_profile": evidence.output_budget_profile,
        "final_prompt_validated": evidence.final_prompt_validated,
        "validation_errors": list(evidence.validation_errors),
        "audit_state": str(evidence.audit_state),
    }


def _orm_to_domain(model: InvocationEvidenceModel) -> FeatureInvocationEvidence:
    """Convert an ORM model instance to a domain evidence record.

    Args:
        model: ORM model instance from the database.

    Returns:
        ``FeatureInvocationEvidence`` domain object.
    """
    from narrare_core.ai_invocation.models import (
        AuditState,
        FeatureInvocationEvidence,
        KBSuggestedStatus,
        PreferenceStatus,
        VoiceProfileStatus,
    )

    errors_raw: list[str] | list[object] = model.validation_errors or []  # type: ignore[assignment]
    return FeatureInvocationEvidence(
        feature_id=model.feature_id,
        intent=model.intent,
        mode=model.mode,
        prompt_route=model.prompt_route,
        preference_status=PreferenceStatus(model.preference_status),
        kb_suggested_status=KBSuggestedStatus(model.kb_suggested_status),
        voice_profile_status=VoiceProfileStatus(model.voice_profile_status)
        if model.voice_profile_status
        else None,
        output_budget_profile=model.output_budget_profile,
        final_prompt_validated=model.final_prompt_validated,
        validation_errors=tuple(str(e) for e in errors_raw),
        audit_state=AuditState(model.audit_state),
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
        values = _domain_to_orm(evidence)
        model = InvocationEvidenceModel(**values)  # type: ignore[arg-type]
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
        return [_orm_to_domain(row) for row in result.scalars()]

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
