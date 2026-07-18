"""Unit tests for KBConsistencyService — orchestrates all consistency analysis sources.

Tests the service layer with mocked dependencies (analyzer, asymmetry checker,
worldbuilding analyzer, cache). No LLM calls, no database.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from narrare.kb.consistency_contracts import (
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
    RelationshipAsymmetry,
)
from narrare.kb.consistency_service import KBConsistencyService
from narrare.kb.worldbuilding_contracts import (
    ConsistencyCategory,
    ConsistencyIssue,
    WorldbuildingSeverity,
)


def _make_asymmetry(
    *,
    source_name: str = "Alice",
    target_name: str = "Bob",
    forward_rel_type: str = "ally",
    reverse_rel_type: str | None = None,
    expected_inverse: str | None = "ally",
    severity: WorldbuildingSeverity = WorldbuildingSeverity.MINOR,
) -> RelationshipAsymmetry:
    """Create a test RelationshipAsymmetry with defaults."""
    return RelationshipAsymmetry(
        source_id=str(uuid4()),
        source_name=source_name,
        target_id=str(uuid4()),
        target_name=target_name,
        forward_rel_type=forward_rel_type,
        reverse_rel_type=reverse_rel_type,
        expected_inverse=expected_inverse,
        severity=severity,
    )


def _make_issue(
    *,
    finding_index: int = 0,
    category: ConsistencyCategory = ConsistencyCategory.ENTRY_INTERNAL,
    description: str = "Test inconsistency",
    contradiction: str = "Field A contradicts Field B",
) -> ConsistencyIssue:
    """Create a test ConsistencyIssue with defaults."""
    return ConsistencyIssue(
        finding_index=finding_index,
        category=category,
        entity_ids=[str(uuid4())],
        entity_names=["Entity"],
        description=description,
        contradiction=contradiction,
        confidence=0.9,
    )


def _make_service() -> tuple[KBConsistencyService, dict[str, AsyncMock | Mock]]:
    """Create a KBConsistencyService with all dependencies mocked."""
    analyzer = AsyncMock()
    asymmetry_checker = AsyncMock()
    worldbuilding_analyzer = AsyncMock()
    cache = AsyncMock()
    cache.hash_entity_types = Mock(return_value="")
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    service = KBConsistencyService(
        analyzer=analyzer,
        asymmetry_checker=asymmetry_checker,
        worldbuilding_analyzer=worldbuilding_analyzer,
        kb_repo=AsyncMock(),
        rel_repo=AsyncMock(),
        cache=cache,
    )
    # Mock private helper to avoid full worldbuilding-entity-assembly pipeline.
    mock_run_cross = AsyncMock(return_value=[])
    service._run_cross_entity = mock_run_cross  # type: ignore[assignment]

    return service, {
        "analyzer": analyzer,
        "asymmetry_checker": asymmetry_checker,
        "cache": cache,
        "_run_cross_entity": mock_run_cross,
    }


class TestKBConsistencyService:
    """Unit tests for KBConsistencyService.check() and helpers."""

    async def test_check_returns_issues_from_all_sources(self) -> None:
        """check() merges issues from asymmetry, entry-internal, and cross-entity."""
        service, mocks = _make_service()
        novel_id = uuid4()

        asym = _make_asymmetry(forward_rel_type="ally", expected_inverse="ally")
        mocks["asymmetry_checker"].check = AsyncMock(return_value=[asym])

        entry_issue = _make_issue(
            category=ConsistencyCategory.ENTRY_INTERNAL,
            description="Entry contradicts itself",
        )
        mocks["analyzer"].analyze_entries = AsyncMock(return_value=([entry_issue], 5))

        cross_issue = _make_issue(
            category=ConsistencyCategory.GEOGRAPHY,
            description="Geographic contradiction",
        )
        mocks["_run_cross_entity"].return_value = [cross_issue]

        result = await service.check(novel_id=novel_id, request=ConsistencyCheckRequest())

        assert len(result.issues) == 3
        categories = {issue.category for issue in result.issues}
        assert ConsistencyCategory.RELATIONSHIP_ASYMMETRY in categories
        assert ConsistencyCategory.ENTRY_INTERNAL in categories
        assert ConsistencyCategory.GEOGRAPHY in categories
        assert result.summary["asymmetry"] == 1
        assert result.summary["entry_internal"] == 1
        assert result.summary["cross_entity"] == 1

    async def test_check_caches_results(self) -> None:
        """check() calls cache.set() with novel_id, JSON body, and types_hash."""
        service, mocks = _make_service()
        novel_id = uuid4()

        mocks["asymmetry_checker"].check = AsyncMock(return_value=[])
        mocks["analyzer"].analyze_entries = AsyncMock(return_value=([], 3))

        request = ConsistencyCheckRequest()
        types_hash = mocks["cache"].hash_entity_types(request.entity_types)

        await service.check(novel_id=novel_id, request=request)

        mocks["cache"].set.assert_awaited_once()
        call_args = mocks["cache"].set.call_args[0]
        assert call_args[0] == str(novel_id)
        assert call_args[2] == types_hash
        parsed = ConsistencyCheckResponse.model_validate_json(call_args[1])
        assert parsed.novel_id == str(novel_id)

    async def test_check_uses_cache_on_second_call(self) -> None:
        """Second call with a cache hit returns cached result without re-analysis."""
        service, mocks = _make_service()
        novel_id = uuid4()

        cached = ConsistencyCheckResponse(
            novel_id=str(novel_id),
            entity_count=10,
            issues=[],
            summary={"entry_internal": 0, "asymmetry": 0, "cross_entity": 0},
            checked_at="2025-01-01T00:00:00+00:00",
        )
        mocks["cache"].get = AsyncMock(
            side_effect=[None, cached.model_dump_json()],
        )
        mocks["asymmetry_checker"].check = AsyncMock(return_value=[])
        mocks["analyzer"].analyze_entries = AsyncMock(return_value=([], 10))

        request = ConsistencyCheckRequest()

        result1 = await service.check(novel_id=novel_id, request=request)
        assert result1.novel_id == str(novel_id)
        mocks["asymmetry_checker"].check.assert_awaited()

        # Reset trackers before second call.
        mocks["asymmetry_checker"].check.reset_mock()
        mocks["analyzer"].analyze_entries.reset_mock()
        mocks["_run_cross_entity"].reset_mock()

        result2 = await service.check(novel_id=novel_id, request=request)
        assert result2.entity_count == 10
        assert result2.checked_at == "2025-01-01T00:00:00+00:00"
        mocks["asymmetry_checker"].check.assert_not_awaited()
        mocks["analyzer"].analyze_entries.assert_not_awaited()
        mocks["_run_cross_entity"].assert_not_awaited()

    async def test_check_refresh_bypasses_cache(self) -> None:
        """refresh=True skips cache.get() but still caches the new result."""
        service, mocks = _make_service()
        novel_id = uuid4()

        mocks["asymmetry_checker"].check = AsyncMock(return_value=[])
        mocks["analyzer"].analyze_entries = AsyncMock(return_value=([], 2))

        await service.check(novel_id=novel_id, request=ConsistencyCheckRequest(refresh=True))

        mocks["cache"].get.assert_not_awaited()
        mocks["cache"].set.assert_awaited_once()

    async def test_check_asymmetry_only(self) -> None:
        """Only asymmetry_checker runs when other sources are disabled."""
        service, mocks = _make_service()
        novel_id = uuid4()

        asym = _make_asymmetry(source_name="A", target_name="B")
        mocks["asymmetry_checker"].check = AsyncMock(return_value=[asym])

        request = ConsistencyCheckRequest(
            include_asymmetry=True,
            include_entry_internal=False,
            include_cross_entity=False,
        )

        result = await service.check(novel_id=novel_id, request=request)

        mocks["asymmetry_checker"].check.assert_awaited_once()
        mocks["analyzer"].analyze_entries.assert_not_awaited()
        mocks["_run_cross_entity"].assert_not_awaited()
        assert len(result.issues) == 1
        assert result.issues[0].category == ConsistencyCategory.RELATIONSHIP_ASYMMETRY

    async def test_asymmetry_converted_to_consistency_issue(self) -> None:
        """RelationshipAsymmetry is converted to ConsistencyIssue with correct fields."""
        service, mocks = _make_service()
        novel_id = uuid4()

        source_id = str(uuid4())
        target_id = str(uuid4())
        asym = _make_asymmetry(
            source_name="Rome",
            target_name="Juliet",
            forward_rel_type="rival",
            expected_inverse="rival",
            severity=WorldbuildingSeverity.MAJOR,
        )
        asym.source_id = source_id
        asym.target_id = target_id
        mocks["asymmetry_checker"].check = AsyncMock(return_value=[asym])

        request = ConsistencyCheckRequest(
            include_asymmetry=True,
            include_entry_internal=False,
            include_cross_entity=False,
        )

        result = await service.check(novel_id=novel_id, request=request)

        issue = result.issues[0]
        assert issue.category == ConsistencyCategory.RELATIONSHIP_ASYMMETRY
        assert source_id in issue.entity_ids
        assert target_id in issue.entity_ids
        assert "Rome" in issue.entity_names
        assert "rival" in issue.description
        assert issue.severity == WorldbuildingSeverity.MAJOR
        assert issue.confidence == 1.0
        assert issue.suggested_resolution is not None
        assert "rival" in issue.suggested_resolution


# CR-AUFG-03-10 semantic-suppression integration tests (mem0 hook inside
# check()) live in test_consistency_service_suppress.py — split out to keep
# this file under the RULE-04 300-line limit.
