"""Integration tests for EvidenceRepositoryImpl.get_adaptive_snapshots (ADR-070)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest_asyncio

from narrare.evidence.models import InvocationEvidenceModel
from narrare.evidence.repository import EvidenceRepositoryImpl

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


def _row(
    *,
    novel_id: UUID | None,
    adaptive: dict[str, str] | None,
    created_at: datetime,
    invocation_id: UUID | None = None,
) -> InvocationEvidenceModel:
    return InvocationEvidenceModel(
        id=uuid.uuid4(),
        feature_id="dialogue_coach",
        intent="dialogue_coach",
        mode="dialogue_coach",
        prompt_route="ai_assist/dialogue_coach",
        preference_status="provided",
        kb_suggested_status="not_applicable",
        audit_state="adopted",
        final_prompt_validated=True,
        novel_id=novel_id,
        invocation_id=invocation_id or uuid.uuid4(),
        adaptive_source_summary=adaptive,
        adaptive_weights={"preference": 0.7} if adaptive else None,
        created_at=created_at,
    )


@pytest_asyncio.fixture(loop_scope="session")
async def evidence_repo(db_session: AsyncSession) -> EvidenceRepositoryImpl:
    return EvidenceRepositoryImpl(session=db_session)


class TestGetAdaptiveSnapshots:
    async def test_returns_only_rows_for_novel_with_adaptive(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        db_session: AsyncSession,
    ) -> None:
        novel = uuid.uuid4()
        other = uuid.uuid4()
        db_session.add_all(
            [
                _row(
                    novel_id=novel,
                    adaptive={"summary": "preferences"},
                    created_at=datetime(2026, 7, 1, tzinfo=UTC),
                ),
                _row(
                    novel_id=novel, adaptive=None, created_at=datetime(2026, 7, 2, tzinfo=UTC)
                ),  # no adaptive → excluded
                _row(
                    novel_id=other,
                    adaptive={"summary": "voices"},
                    created_at=datetime(2026, 7, 3, tzinfo=UTC),
                ),  # other novel → excluded
                _row(
                    novel_id=None,
                    adaptive={"summary": "legacy"},
                    created_at=datetime(2026, 7, 4, tzinfo=UTC),
                ),  # unattributable → excluded
            ]
        )
        await db_session.flush()

        results = await evidence_repo.get_adaptive_snapshots(novel_id=novel)
        assert len(results) == 1
        assert results[0].novel_id == novel
        assert results[0].adaptive_source_summary == {"summary": "preferences"}

    async def test_orders_newest_first_and_carries_created_at(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        db_session: AsyncSession,
    ) -> None:
        novel = uuid.uuid4()
        db_session.add_all(
            [
                _row(
                    novel_id=novel,
                    adaptive={"summary": "old"},
                    created_at=datetime(2026, 7, 1, tzinfo=UTC),
                ),
                _row(
                    novel_id=novel,
                    adaptive={"summary": "new"},
                    created_at=datetime(2026, 7, 23, tzinfo=UTC),
                ),
            ]
        )
        await db_session.flush()

        results = await evidence_repo.get_adaptive_snapshots(novel_id=novel)
        assert all(r.adaptive_source_summary is not None for r in results)
        assert [cast("dict[str, str]", r.adaptive_source_summary)["summary"] for r in results] == [
            "new",
            "old",
        ]
        assert all(r.created_at is not None for r in results)

    async def test_limit_is_respected(
        self,
        evidence_repo: EvidenceRepositoryImpl,
        db_session: AsyncSession,
    ) -> None:
        novel = uuid.uuid4()
        db_session.add_all(
            [
                _row(
                    novel_id=novel,
                    adaptive={"summary": str(i)},
                    created_at=datetime(2026, 7, i, tzinfo=UTC),
                )
                for i in range(1, 6)
            ]
        )
        await db_session.flush()

        results = await evidence_repo.get_adaptive_snapshots(novel_id=novel, limit=2)
        assert len(results) == 2
        assert all(r.adaptive_source_summary is not None for r in results)
        assert [cast("dict[str, str]", r.adaptive_source_summary)["summary"] for r in results] == [
            "5",
            "4",
        ]

    async def test_no_matching_rows_returns_empty(
        self,
        evidence_repo: EvidenceRepositoryImpl,
    ) -> None:
        results = await evidence_repo.get_adaptive_snapshots(novel_id=uuid.uuid4())
        assert results == []
