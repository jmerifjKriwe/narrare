"""W2 gap closure — DB-level integration test for worldbuilding apply.

Commit 391ce76d added the entries∈novel validation to
``WorldbuildingService.apply_connections`` (batch probe via
``KBRepository.filter_ids_in_novel`` before any write). The unit suites
cover it over recording fakes, and ``test_worldbuilding.py`` covers the
HTTP surface with the service MOCKED — no test exercised the real SQL
path. This file closes that gap: the REAL service over the REAL
``KBRepository`` / ``RelationshipRepository`` / ``NovelRepository``
against real PostgreSQL, via the transaction-wrapped ``db_session``
(rolled back per test).

Only the analyzer (LLM boundary — never invoked by apply) is a raising
stub, which doubles as an assertion that the apply path never reaches
the LLM. Everything else is production wiring (in-memory cache backend,
same as ``dependencies_worldbuilding.get_worldbuilding_service``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, cast
from uuid import UUID, uuid4

import pytest

from narrare.auth.models import User
from narrare.kb.models import KBEntry
from narrare.kb.relationship_repository import RelationshipRepository
from narrare.kb.repository import KBRepository
from narrare.kb.worldbuilding_cache import WorldbuildingCache
from narrare.kb.worldbuilding_contracts import (
    ConnectionSuggestion,
    WorldbuildingAnalysisRequest,
    WorldbuildingAnalysisResponse,
    WorldbuildingApplyRequest,
)
from narrare.kb.worldbuilding_service import WorldbuildingService
from narrare.novels.models import Novel
from narrare.novels.repository import NovelRepository
from narrare_core.cache import InMemorySessionCache
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer


# ---------------------------------------------------------------------------
# LLM boundary stub
# ---------------------------------------------------------------------------


class _NoLLMAnalyzer:
    """Stub for the analyzer — the apply path must never call it.

    ``apply_connections`` is pure validation + SQL; reaching the analyzer
    here would mean an accidental LLM invocation in an integration suite
    that promises a mocked LLM. Raises instead of recording so such a
    regression fails loudly.
    """

    async def analyze(
        self,
        novel_id: UUID,
        request: WorldbuildingAnalysisRequest,
    ) -> WorldbuildingAnalysisResponse:
        raise AssertionError(f"apply path must not invoke the analyzer (LLM boundary): {novel_id}")


# ---------------------------------------------------------------------------
# Seed + payload builders
# ---------------------------------------------------------------------------


class _W2Seed(NamedTuple):
    """The W2 matrix fixture: two owners, two novels, entries in each."""

    user_a: UUID  # owner of novel_a (the caller / victim)
    user_b: UUID  # owner of novel_b (foreign novel)
    novel_a: UUID
    novel_b: UUID
    alice: UUID  # entry in novel_a
    bob: UUID  # entry in novel_a
    carol: UUID  # entry in novel_b (foreign, but a REAL row)


async def _seed_w2_graph(session: AsyncSession) -> _W2Seed:
    """Seed users A/B, novels A/B, and entries in each (W2 matrix)."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    user_a = User(
        id=uuid4(),
        email=f"w2-a-{uuid4().hex[:12]}@example.com",
        hashed_password="not-a-real-hash",
        created_at=now,
        updated_at=now,
    )
    user_b = User(
        id=uuid4(),
        email=f"w2-b-{uuid4().hex[:12]}@example.com",
        hashed_password="not-a-real-hash",
        created_at=now,
        updated_at=now,
    )
    session.add_all([user_a, user_b])
    await session.flush()

    novel_a = Novel(id=uuid4(), user_id=user_a.id, title="Novel A (caller's)")
    novel_b = Novel(id=uuid4(), user_id=user_b.id, title="Novel B (foreign)")
    session.add_all([novel_a, novel_b])
    await session.flush()

    def _entry(novel_id: UUID, name: str) -> KBEntry:
        return KBEntry(
            id=uuid4(),
            novel_id=novel_id,
            entity_type="character",
            name=name,
            slug=f"{name.lower()}-{uuid4().hex[:8]}",
        )

    alice = _entry(novel_a.id, "Alice")
    bob = _entry(novel_a.id, "Bob")
    carol = _entry(novel_b.id, "Carol")
    session.add_all([alice, bob, carol])
    await session.flush()

    return _W2Seed(
        user_a=user_a.id,
        user_b=user_b.id,
        novel_a=novel_a.id,
        novel_b=novel_b.id,
        alice=alice.id,
        bob=bob.id,
        carol=carol.id,
    )


def _suggestion(
    idx: int,
    source: UUID,
    target: UUID,
    *,
    source_name: str = "Alice",
    target_name: str = "Bob",
) -> ConnectionSuggestion:
    """A connection suggestion with explicit (client-roundtripped) ids."""
    return ConnectionSuggestion(
        finding_index=idx,
        source_entity_id=str(source),
        source_entity_name=source_name,
        source_entity_type="character",
        target_entity_id=str(target),
        target_entity_name=target_name,
        target_entity_type="character",
        suggested_rel_type="ally",
        reasoning="Characters interact frequently",
        confidence=0.85,
        story_relevance=0.7,
    )


def _analysis(
    novel_id: UUID,
    suggestions: list[ConnectionSuggestion],
) -> WorldbuildingAnalysisResponse:
    """A minimal analysis payload carrying the given suggestions."""
    return WorldbuildingAnalysisResponse(
        novel_id=str(novel_id),
        entity_count=3,
        gap_findings=[],
        connection_suggestions=suggestions,
        consistency_issues=[],
        worldbuilding_score=0.75,
        overall_assessment="Good worldbuilding foundation",
        summary={
            "total_entities": 3,
            "gaps_found": 0,
            "connections_suggested": len(suggestions),
            "consistency_issues": 0,
            "entities_in_analysis": 3,
        },
        analyzed_at="2026-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def service(db_session: AsyncSession) -> WorldbuildingService:
    """Real WorldbuildingService over real repositories + real cache.

    Mirrors the production wiring from
    ``dependencies_worldbuilding.get_worldbuilding_service`` — only the
    analyzer is the raising LLM-boundary stub.
    """
    return WorldbuildingService(
        analyzer=cast("WorldbuildingAnalyzer", _NoLLMAnalyzer()),
        rel_repo=RelationshipRepository(db_session),
        entry_repo=KBRepository(db_session),
        cache=WorldbuildingCache(InMemorySessionCache()),
        novel_repo=NovelRepository(db_session),
    )


@pytest.fixture
async def rel_repo(db_session: AsyncSession) -> RelationshipRepository:
    """Relationship repository for direct DB-state assertions."""
    return RelationshipRepository(db_session)


# ---------------------------------------------------------------------------
# Tests: apply_connections over the real SQL path
# ---------------------------------------------------------------------------


class TestApplyConnectionsRealSql:
    """Real service → real ``filter_ids_in_novel`` SQL → real writes."""

    async def test_apply_with_foreign_entry_rejected_then_in_novel_written(
        self,
        db_session: AsyncSession,
        service: WorldbuildingService,
        rel_repo: RelationshipRepository,
    ) -> None:
        """Foreign entry → NotFoundError (404-shape) + zero rows; all-in-novel → row written.

        Phase 1: the client-roundtripped analysis references Carol, a REAL
        entry that lives in novel B. The whole batch must be rejected
        BEFORE any duplicate check or write — NotFoundError with the
        NOT_FOUND code (the shape ``main.py`` maps to HTTP 404) and zero
        relationship rows anywhere in the DB.

        Phase 2: same caller, same novel, every referenced entry in
        novel A → the relationship is actually written and visible to
        the graph/existence queries.
        """
        seed = await _seed_w2_graph(db_session)

        # -- Phase 1: foreign target (novel B entry) → rejected whole --
        foreign_analysis = _analysis(
            seed.novel_a,
            [_suggestion(0, seed.alice, seed.carol, target_name="Carol")],
        )
        with pytest.raises(NotFoundError, match="KBEntry") as exc_info:
            await service.apply_connections(
                novel_id=seed.novel_a,
                user_id=seed.user_a,
                request=WorldbuildingApplyRequest(finding_indices=[0]),
                analysis=foreign_analysis,
            )

        assert str(exc_info.value) == f"KBEntry ({seed.carol}) not found"
        assert exc_info.value.code == "NOT_FOUND"  # 404-shape at the service boundary
        # Zero relationship rows: novel A scoped, per-entry both directions.
        assert await rel_repo.list_all_for_novel(seed.novel_a) == []
        assert await rel_repo.list_for_entry(seed.alice) == []
        assert await rel_repo.list_for_entry(seed.carol) == []
        assert await rel_repo.exists(seed.alice, seed.carol, "ally") is False

        # -- Phase 2: all entries in novel A → relationship written --
        valid_analysis = _analysis(
            seed.novel_a,
            [_suggestion(0, seed.alice, seed.bob)],
        )
        result = await service.apply_connections(
            novel_id=seed.novel_a,
            user_id=seed.user_a,
            request=WorldbuildingApplyRequest(finding_indices=[0]),
            analysis=valid_analysis,
        )

        assert result.success is True
        assert result.created_count == 1
        assert result.failed_count == 0
        assert result.errors == []

        rels = await rel_repo.list_all_for_novel(seed.novel_a)
        assert len(rels) == 1
        assert rels[0].source_id == seed.alice
        assert rels[0].target_id == seed.bob
        assert rels[0].rel_type == "ally"
        assert await rel_repo.exists(seed.alice, seed.bob, "ally") is True
