"""Unit tests for WorldbuildingAnalyzer — LLM orchestration for worldbuilding.

Tests helper functions (_safe_gap_type, _safe_severity, _safe_category)
and the analyze() method with mocked dependencies.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic_ai.models import Model

from narrare.kb.worldbuilding_analyzer import (
    WorldbuildingAnalyzer,
    _safe_category,
    _safe_gap_type,
    _safe_severity,
)
from narrare.kb.worldbuilding_contracts import (
    ConsistencyCategory,
    GapType,
    WorldbuildingAnalysisRequest,
    WorldbuildingSeverity,
)
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare_core.prompts.composer import PromptComposer

# ---------------------------------------------------------------------------
# Fake classes
# ---------------------------------------------------------------------------


class FakeKBEntry:
    def __init__(self, *, entity_type: str = "character", name: str = "Test") -> None:
        self.id = uuid4()
        self.name = name
        self.entity_type = entity_type
        self.metadata_: dict[str, object] | None = None
        self.body = "Body text"
        self.tags: list[str] | None = None
        self.usage_count = 0


class FakeKBRepo:
    def __init__(self, entries: list[FakeKBEntry] | None = None) -> None:
        self._entries = entries or []

    async def list_entries(
        self,
        novel_id: object,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[FakeKBEntry], int]:
        start = (page - 1) * page_size
        return self._entries[start : start + page_size], len(self._entries)

    async def get_by_id(self, entry_id: object) -> FakeKBEntry | None:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None


class FakeRelRepo:
    async def get_adjacency_map(
        self, novel_id: object, entity_ids: set[object] | None = None
    ) -> dict[str, set[str]]:
        return {}

    async def list_for_entry(self, entry_id: object, direction: str | None = None) -> list[object]:
        return []


class FakeCache:
    def __init__(self, data: str | None = None) -> None:
        self._data = data
        self.last_set: tuple[str, str] | None = None

    async def get(self, novel_id: str, types_hash: str = "") -> str | None:
        return self._data

    async def set(self, novel_id: str, value: str, types_hash: str = "") -> None:
        self.last_set = (novel_id, value)


class FakeComposer:
    async def build(self, intent: object, ctx: object) -> ComposedPrompt:
        return ComposedPrompt(system="fake system prompt", user="user prompt")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analyzer(
    *, cache_data: str | None = None
) -> tuple[WorldbuildingAnalyzer, dict[str, Any]]:
    kb_repo = FakeKBRepo()
    cache = FakeCache(data=cache_data)
    registry = MagicMock(spec=ModelRegistry)
    config = MagicMock(spec=ResolvedModelConfig)
    analyzer = WorldbuildingAnalyzer(
        kb_repo=cast("KBRepository", kb_repo),
        rel_repo=cast("RelationshipRepository", FakeRelRepo()),
        cache=cast("WorldbuildingCache", cache),
        registry=registry,
        config=config,
        composer=cast("PromptComposer", FakeComposer()),
    )
    return analyzer, {"kb_repo": kb_repo, "cache": cache, "registry": registry}


def _make_response_json(novel_id: str | None = None) -> str:
    from narrare.kb.worldbuilding_contracts import WorldbuildingAnalysisResponse

    return WorldbuildingAnalysisResponse(
        novel_id=novel_id or str(uuid4()),
        entity_count=5,
        gap_findings=[],
        connection_suggestions=[],
        consistency_issues=[],
        worldbuilding_score=0.8,
        overall_assessment="Good",
        summary={
            "total_entities": 5,
            "gaps_found": 0,
            "connections_suggested": 0,
            "consistency_issues": 0,
            "entities_in_analysis": 5,
        },
        analyzed_at="2025-01-01T00:00:00Z",
    ).model_dump_json()


def _make_phase1(**overrides: Any) -> object:
    from narrare_core.agents.worldbuilding_types import WorldbuildingPhase1Output

    defaults: dict[str, Any] = {
        "gaps": [],
        "connection_suggestions": [],
        "assessment": "OK",
        "worldbuilding_score": 0.5,
        "candidate_pairs_for_consistency": [],
    }
    defaults.update(overrides)
    return WorldbuildingPhase1Output(**defaults)


# ---------------------------------------------------------------------------
# Tests: safe helpers
# ---------------------------------------------------------------------------


class TestSafeGapType:
    def test_valid_returns_enum(self) -> None:
        assert _safe_gap_type("missing_entity") == GapType.MISSING_ENTITY

    def test_invalid_returns_missing_field(self) -> None:
        assert _safe_gap_type("totally_invalid") == GapType.MISSING_FIELD


class TestSafeSeverity:
    def test_valid_critical(self) -> None:
        assert _safe_severity("critical") == WorldbuildingSeverity.CRITICAL

    def test_invalid_returns_major(self) -> None:
        assert _safe_severity("bogus") == WorldbuildingSeverity.MAJOR


class TestSafeCategory:
    def test_valid_geography(self) -> None:
        assert _safe_category("geography") == ConsistencyCategory.GEOGRAPHY

    def test_invalid_returns_system_rules(self) -> None:
        assert _safe_category("nonsense") == ConsistencyCategory.SYSTEM_RULES


# ---------------------------------------------------------------------------
# Tests: analyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_returns_cached_when_available(self) -> None:
        novel_id = uuid4()
        cached_json = _make_response_json(novel_id=str(novel_id))
        analyzer, _ = _make_analyzer(cache_data=cached_json)
        request = WorldbuildingAnalysisRequest(refresh=False)
        result = await analyzer.analyze(novel_id=novel_id, request=request)
        assert result.entity_count == 5

    @pytest.mark.asyncio
    async def test_analyze_builds_deps_on_cache_miss(self) -> None:
        novel_id = uuid4()
        analyzer, deps = _make_analyzer(cache_data=None)
        deps["kb_repo"]._entries = [FakeKBEntry()]
        deps["registry"].prepare = AsyncMock(
            return_value=SimpleNamespace(
                model=MagicMock(spec=Model), model_settings=None, usage_limits=None
            )
        )

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase1 = AsyncMock(
                return_value=_make_phase1(worldbuilding_score=0.75, assessment="Looks good")
            )
            result = await analyzer.analyze(
                novel_id=novel_id,
                request=WorldbuildingAnalysisRequest(refresh=True, include_consistency=False),
            )
        assert result.worldbuilding_score == 0.75

    @pytest.mark.asyncio
    async def test_analyze_skips_phase2_when_consistency_false(self) -> None:
        novel_id = uuid4()
        analyzer, deps = _make_analyzer(cache_data=None)
        deps["kb_repo"]._entries = [FakeKBEntry()]
        deps["registry"].prepare = AsyncMock(
            return_value=SimpleNamespace(
                model=MagicMock(spec=Model), model_settings=None, usage_limits=None
            )
        )

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.run_phase1 = AsyncMock(
                return_value=_make_phase1(candidate_pairs_for_consistency=[("a", "b")])
            )
            result = await analyzer.analyze(
                novel_id=novel_id,
                request=WorldbuildingAnalysisRequest(refresh=True, include_consistency=False),
            )
        assert result.consistency_issues == []
        instance.run_phase2.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_skips_phase2_when_no_candidate_pairs(self) -> None:
        novel_id = uuid4()
        analyzer, deps = _make_analyzer(cache_data=None)
        deps["kb_repo"]._entries = [FakeKBEntry()]
        deps["registry"].prepare = AsyncMock(
            return_value=SimpleNamespace(
                model=MagicMock(spec=Model), model_settings=None, usage_limits=None
            )
        )

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase1 = AsyncMock(
                return_value=_make_phase1(candidate_pairs_for_consistency=[])
            )
            result = await analyzer.analyze(
                novel_id=novel_id,
                request=WorldbuildingAnalysisRequest(refresh=True, include_consistency=True),
            )
        assert result.consistency_issues == []

    @pytest.mark.asyncio
    async def test_analyze_stores_result_in_cache(self) -> None:
        novel_id = uuid4()
        analyzer, deps = _make_analyzer(cache_data=None)
        deps["kb_repo"]._entries = [FakeKBEntry()]
        deps["registry"].prepare = AsyncMock(
            return_value=SimpleNamespace(
                model=MagicMock(spec=Model), model_settings=None, usage_limits=None
            )
        )

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase1 = AsyncMock(return_value=_make_phase1())
            await analyzer.analyze(
                novel_id=novel_id, request=WorldbuildingAnalysisRequest(refresh=True)
            )
        cache = deps["cache"]
        assert cache.last_set is not None
        assert cache.last_set[0] == str(novel_id)
