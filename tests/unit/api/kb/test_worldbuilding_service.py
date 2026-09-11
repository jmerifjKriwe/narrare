"""Unit tests for WorldbuildingService — worldbuilding analysis business logic.

Tests analyze and apply_connections with mocked dependencies.
Uses AsyncMock(spec=...) patterns consistent with existing KB service tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from narrare.kb.worldbuilding_contracts import (
    ConnectionSuggestion,
    WorldbuildingAnalysisRequest,
    WorldbuildingAnalysisResponse,
    WorldbuildingApplyRequest,
)
from narrare.kb.worldbuilding_service import WorldbuildingService

from ._test_fakes import FakeNovelRepo

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_connection_suggestion(
    *,
    finding_index: int = 0,
    source_entity_id: str | None = None,
    target_entity_id: str | None = None,
    suggested_rel_type: str = "ally",
    source_entity_name: str = "Alice",
    target_entity_name: str = "Bob",
) -> ConnectionSuggestion:
    """Create a test ConnectionSuggestion with defaults."""
    return ConnectionSuggestion(
        finding_index=finding_index,
        source_entity_id=source_entity_id or str(uuid4()),
        source_entity_name=source_entity_name,
        source_entity_type="character",
        target_entity_id=target_entity_id or str(uuid4()),
        target_entity_name=target_entity_name,
        target_entity_type="character",
        suggested_rel_type=suggested_rel_type,
        reasoning="Characters interact frequently",
        confidence=0.85,
        story_relevance=0.7,
    )


def _make_analysis_response(
    *,
    suggestions: list[ConnectionSuggestion] | None = None,
    novel_id: str | None = None,
) -> WorldbuildingAnalysisResponse:
    """Create a test WorldbuildingAnalysisResponse with defaults."""
    return WorldbuildingAnalysisResponse(
        novel_id=novel_id or str(uuid4()),
        entity_count=10,
        gap_findings=[],
        connection_suggestions=suggestions
        if suggestions is not None
        else [_make_connection_suggestion()],
        consistency_issues=[],
        worldbuilding_score=0.75,
        overall_assessment="Good worldbuilding foundation",
        summary={
            "total_entities": 10,
            "gaps_found": 0,
            "connections_suggested": 1,
            "consistency_issues": 0,
            "entities_in_analysis": 10,
        },
        analyzed_at="2025-01-01T00:00:00Z",
    )


@dataclass
class _ServiceMocks:
    """Typed handle to the mocked dependencies returned by ``_make_service``."""

    analyzer: AsyncMock
    rel_repo: AsyncMock
    entry_repo: _PermissiveEntryRepo
    cache: AsyncMock


def _make_service(
    *,
    rel_exists: bool = False,
    rel_create_fails: bool = False,
) -> tuple[WorldbuildingService, _ServiceMocks]:
    """Create a WorldbuildingService with all dependencies mocked.

    Returns (service, mocks) for assertion access. The entry repo is
    permissive for the batch entry∈novel probe (every id counts as
    in-novel) — the W2 ownership matrix lives in
    ``test_improve_worldbuilding_ownership.py``.
    """
    # --- Analyzer ---
    analyzer = AsyncMock(spec=["analyze"])

    # --- Relationship Repository ---
    rel_repo = AsyncMock(spec=["exists", "create"])
    rel_repo.exists = AsyncMock(return_value=rel_exists)
    if rel_create_fails:
        rel_repo.create = AsyncMock(side_effect=RuntimeError("DB error"))
    else:
        rel_repo.create = AsyncMock()

    # --- Entry Repository (batch entry∈novel probe, W2) ---
    entry_repo = _PermissiveEntryRepo()

    # --- Cache ---
    cache = AsyncMock(spec=["delete_all"])
    cache.delete_all = AsyncMock()

    service = WorldbuildingService(
        analyzer=analyzer,
        rel_repo=rel_repo,
        entry_repo=cast("KBRepositoryProtocol", entry_repo),
        cache=cache,
        novel_repo=cast("NovelRepositoryProtocol", FakeNovelRepo()),  # permissive: owner flow
    )

    return service, _ServiceMocks(
        analyzer=analyzer, rel_repo=rel_repo, entry_repo=entry_repo, cache=cache
    )


class _PermissiveEntryRepo:
    """Fake entry repo — every referenced id counts as in-novel (owner flow).

    Records the batch entry∈novel probe so tests can assert call shape.
    """

    def __init__(self) -> None:
        self.filter_ids_in_novel_calls: list[tuple[UUID, frozenset[UUID]]] = []

    async def filter_ids_in_novel(self, novel_id: UUID, entry_ids: set[UUID]) -> set[UUID]:
        self.filter_ids_in_novel_calls.append((novel_id, frozenset(entry_ids)))
        return set(entry_ids)


# ---------------------------------------------------------------------------
# Tests: analyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    """Test WorldbuildingService.analyze — delegates to analyzer."""

    async def test_analyze_delegates_to_analyzer(self) -> None:
        """analyze() delegates to analyzer.analyze() and returns its result."""
        service, mocks = _make_service()
        novel_id = uuid4()
        request = WorldbuildingAnalysisRequest()
        expected = _make_analysis_response()
        mocks.analyzer.analyze = AsyncMock(return_value=expected)

        result = await service.analyze(novel_id=novel_id, request=request, user_id=uuid4())

        assert result is expected
        mocks.analyzer.analyze.assert_awaited_once_with(novel_id, request)


# ---------------------------------------------------------------------------
# Tests: apply_connections
# ---------------------------------------------------------------------------


class TestApplyConnections:
    """Test WorldbuildingService.apply_connections — create relationships."""

    async def test_apply_connections_creates_relationships(self) -> None:
        """apply_connections creates KBRelationship for valid suggestions."""
        service, mocks = _make_service()
        novel_id = uuid4()
        user_id = uuid4()

        suggestion = _make_connection_suggestion(finding_index=0)
        analysis = _make_analysis_response(suggestions=[suggestion])

        request = WorldbuildingApplyRequest(finding_indices=[0])

        result = await service.apply_connections(
            novel_id=novel_id,
            user_id=user_id,
            request=request,
            analysis=analysis,
        )

        assert result.success is True
        assert result.created_count == 1
        assert result.failed_count == 0
        assert result.errors == []
        mocks.rel_repo.create.assert_awaited_once()

    async def test_apply_connections_skips_duplicates(self) -> None:
        """apply_connections skips suggestions where relationship already exists."""
        service, mocks = _make_service(rel_exists=True)
        novel_id = uuid4()
        user_id = uuid4()

        suggestion = _make_connection_suggestion(finding_index=0)
        analysis = _make_analysis_response(suggestions=[suggestion])

        request = WorldbuildingApplyRequest(finding_indices=[0])

        result = await service.apply_connections(
            novel_id=novel_id,
            user_id=user_id,
            request=request,
            analysis=analysis,
        )

        assert result.success is False
        assert result.created_count == 0
        assert result.failed_count == 1
        assert len(result.errors) == 1
        assert "already exists" in result.errors[0]
        mocks.rel_repo.create.assert_not_awaited()

    async def test_apply_connections_invalid_index(self) -> None:
        """apply_connections returns error for invalid finding_index."""
        service, mocks = _make_service()
        novel_id = uuid4()
        user_id = uuid4()

        # Only suggestion has finding_index=0, so index 99 is invalid
        suggestion = _make_connection_suggestion(finding_index=0)
        analysis = _make_analysis_response(suggestions=[suggestion])

        request = WorldbuildingApplyRequest(finding_indices=[99])

        result = await service.apply_connections(
            novel_id=novel_id,
            user_id=user_id,
            request=request,
            analysis=analysis,
        )

        assert result.success is False
        assert result.created_count == 0
        assert result.failed_count == 1
        assert len(result.errors) == 1
        assert "99" in result.errors[0]
        mocks.rel_repo.create.assert_not_awaited()

    async def test_apply_connections_invalidates_cache(self) -> None:
        """apply_connections calls cache.delete_all after successful apply."""
        service, mocks = _make_service()
        novel_id = uuid4()
        user_id = uuid4()

        suggestion = _make_connection_suggestion(finding_index=0)
        analysis = _make_analysis_response(suggestions=[suggestion])

        request = WorldbuildingApplyRequest(finding_indices=[0])

        await service.apply_connections(
            novel_id=novel_id,
            user_id=user_id,
            request=request,
            analysis=analysis,
        )

        mocks.cache.delete_all.assert_awaited_once_with(str(novel_id))

    async def test_apply_connections_no_cache_invalidation_without_creates(self) -> None:
        """apply_connections does NOT invalidate cache when nothing is created."""
        service, mocks = _make_service()
        novel_id = uuid4()
        user_id = uuid4()

        # Empty suggestions => no creates => no cache invalidation
        analysis = _make_analysis_response(suggestions=[])
        request = WorldbuildingApplyRequest(finding_indices=[0])

        await service.apply_connections(
            novel_id=novel_id,
            user_id=user_id,
            request=request,
            analysis=analysis,
        )

        mocks.cache.delete_all.assert_not_awaited()

    async def test_apply_connections_mixed_results(self) -> None:
        """apply_connections handles mix of valid and invalid indices."""
        service, _mocks = _make_service()
        novel_id = uuid4()
        user_id = uuid4()

        s0 = _make_connection_suggestion(finding_index=0)
        analysis = _make_analysis_response(suggestions=[s0])

        # Index 0 is valid, index 99 is invalid
        request = WorldbuildingApplyRequest(finding_indices=[0, 99])

        result = await service.apply_connections(
            novel_id=novel_id,
            user_id=user_id,
            request=request,
            analysis=analysis,
        )

        assert result.success is False
        assert result.created_count == 1
        assert result.failed_count == 1
        assert len(result.errors) == 1

    async def test_apply_connections_entry_ownership_single_batch_probe(self) -> None:
        """W2: all referenced entry ids are validated in ONE batch probe
        covering the whole selection — not per-suggestion lookups."""
        service, mocks = _make_service()
        novel_id = uuid4()
        user_id = uuid4()

        s0 = _make_connection_suggestion(finding_index=0)
        s1 = _make_connection_suggestion(finding_index=1)
        analysis = _make_analysis_response(suggestions=[s0, s1])

        await service.apply_connections(
            novel_id=novel_id,
            user_id=user_id,
            request=WorldbuildingApplyRequest(finding_indices=[0, 1]),
            analysis=analysis,
        )

        expected_ids = {
            UUID(s0.source_entity_id),
            UUID(s0.target_entity_id),
            UUID(s1.source_entity_id),
            UUID(s1.target_entity_id),
        }
        assert mocks.entry_repo.filter_ids_in_novel_calls == [(novel_id, expected_ids)]
