"""Unit tests for KBImproveAnalyzer — cache and analysis orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic_ai.models import Model

from narrare.kb.improve_contracts import KBImproveAnalysisResponse
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.kb.improve_cache import KBImproveCache
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

# ---------------------------------------------------------------------------
# Fake classes
# ---------------------------------------------------------------------------


class _FakeKBEntry:
    def __init__(self, **kwargs: object) -> None:
        self.id = kwargs.get("id", uuid4())
        self.name = kwargs.get("name", "Test Entity")
        self.entity_type = kwargs.get("entity_type", "character")
        self.metadata_ = kwargs.get("metadata_", {})
        self.body = kwargs.get("body", "Some body text")
        self.tags = kwargs.get("tags", [])
        self.novel_id = kwargs.get("novel_id", uuid4())


class _FakeKBRepo:
    def __init__(self, entry: _FakeKBEntry | None = None) -> None:
        self._entry = entry

    async def get_by_id(self, entry_id: object) -> _FakeKBEntry | None:
        return self._entry


class _FakeRelRepo:
    async def list_for_entry(self, entry_id: object) -> list[object]:
        return []

    async def get_adjacency_map(
        self, novel_id: object, entity_ids: set[object] | None = None
    ) -> dict[str, set[str]] | None:
        return {}


class _FakeKBContextProvider:
    """Fake KBContextProviderProtocol for KBImproveAnalyzer construction.

    Mirrors the real provider's RULE-11 contract: ``fetch_world_context``
    returns a configurable string (empty by default) and never raises.
    """

    def __init__(self, world_context: str = "") -> None:
        from narrare.kb.context_contracts import KBContextBundle

        self.fetch_world_context = AsyncMock(return_value=world_context)
        self.fetch_context = AsyncMock(return_value=KBContextBundle.empty())
        self.fetch_entities = AsyncMock(return_value=[])


class _FakeComposer:
    async def build(self, intent: object, ctx: object) -> ComposedPrompt:
        return ComposedPrompt(system="improve system prompt", user="user prompt")


class _FakeImproveCache:
    def __init__(self, data: str | None = None) -> None:
        self._data = data
        self.deleted_keys: list[str] = []

    async def get(self, key: str) -> str | None:
        return self._data

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._data = value

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)


class _FakeRegistry:
    def __init__(self) -> None:
        self.get_model = AsyncMock(return_value=MagicMock(spec=Model))


def _make_analyzer(
    *,
    cache_data: str | None = None,
    entry: _FakeKBEntry | None = None,
    kb_agent: object | None = None,
    world_context: str = "",
) -> tuple[Any, dict[str, Any]]:
    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare_core.llm import ResolvedModelConfig

    cache = _FakeImproveCache(data=cache_data)
    provider = _FakeKBContextProvider(world_context=world_context)
    config = ResolvedModelConfig(provider_name="test", model_id="test-model")
    analyzer = KBImproveAnalyzer(
        registry=cast("ModelRegistry", _FakeRegistry()),
        config=config,
        kb_context_provider=cast("KBContextProviderProtocol", provider),
        prompt_composer=cast("PromptComposer", _FakeComposer()),
        kb_repo=cast("KBRepository", _FakeKBRepo(entry=entry)),
        rel_repo=cast("RelationshipRepository", _FakeRelRepo()),
        improve_cache=cast("KBImproveCache", cache),
        kb_agent=kb_agent,
    )
    return analyzer, {"cache": cache, "provider": provider}


def _make_cached_response(entry_id: object | None = None) -> str:
    resp = KBImproveAnalysisResponse(
        suggestions=[],
        overall_assessment="Good",
        completeness_score=0.9,
    )
    return resp.model_dump_json()


# ---------------------------------------------------------------------------
# Tests: cache methods
# ---------------------------------------------------------------------------


class TestHasCachedAnalysis:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_cache(self) -> None:
        from narrare.kb.improve_analyzer import KBImproveAnalyzer
        from narrare_core.llm import ResolvedModelConfig

        config = ResolvedModelConfig(provider_name="test", model_id="test")
        analyzer = KBImproveAnalyzer(
            registry=cast("ModelRegistry", _FakeRegistry()),
            config=config,
            kb_context_provider=cast("KBContextProviderProtocol", _FakeKBContextProvider()),
            prompt_composer=cast("PromptComposer", _FakeComposer()),
            kb_repo=cast("KBRepository", _FakeKBRepo()),
            rel_repo=cast("RelationshipRepository", _FakeRelRepo()),
            improve_cache=None,
        )
        assert await analyzer.has_cached_analysis(uuid4()) is False

    @pytest.mark.asyncio
    async def test_returns_true_when_cache_has_data(self) -> None:
        entry = _FakeKBEntry()
        analyzer, _ = _make_analyzer(cache_data=_make_cached_response(), entry=entry)
        assert await analyzer.has_cached_analysis(entry.id) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_cache_missing(self) -> None:
        analyzer, _ = _make_analyzer(cache_data=None)
        assert await analyzer.has_cached_analysis(uuid4()) is False


class TestGetCachedAnalysis:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_cache(self) -> None:
        from narrare.kb.improve_analyzer import KBImproveAnalyzer
        from narrare_core.llm import ResolvedModelConfig

        config = ResolvedModelConfig(provider_name="test", model_id="test")
        analyzer = KBImproveAnalyzer(
            registry=cast("ModelRegistry", _FakeRegistry()),
            config=config,
            kb_context_provider=cast("KBContextProviderProtocol", _FakeKBContextProvider()),
            prompt_composer=cast("PromptComposer", _FakeComposer()),
            kb_repo=cast("KBRepository", _FakeKBRepo()),
            rel_repo=cast("RelationshipRepository", _FakeRelRepo()),
            improve_cache=None,
        )
        assert await analyzer.get_cached_analysis(uuid4()) is None

    @pytest.mark.asyncio
    async def test_returns_parsed_response_when_cached(self) -> None:
        entry = _FakeKBEntry()
        analyzer, _ = _make_analyzer(cache_data=_make_cached_response(), entry=entry)
        result = await analyzer.get_cached_analysis(entry.id)
        assert result is not None
        assert result.completeness_score == 0.9


class TestInvalidateCache:
    @pytest.mark.asyncio
    async def test_noop_when_no_cache(self) -> None:
        from narrare.kb.improve_analyzer import KBImproveAnalyzer
        from narrare_core.llm import ResolvedModelConfig

        config = ResolvedModelConfig(provider_name="test", model_id="test")
        analyzer = KBImproveAnalyzer(
            registry=cast("ModelRegistry", _FakeRegistry()),
            config=config,
            kb_context_provider=cast("KBContextProviderProtocol", _FakeKBContextProvider()),
            prompt_composer=cast("PromptComposer", _FakeComposer()),
            kb_repo=cast("KBRepository", _FakeKBRepo()),
            rel_repo=cast("RelationshipRepository", _FakeRelRepo()),
            improve_cache=None,
        )
        await analyzer.invalidate_cache(uuid4())  # should not raise

    @pytest.mark.asyncio
    async def test_calls_delete_when_cache_exists(self) -> None:
        entry_id = uuid4()
        analyzer, deps = _make_analyzer(cache_data="data")
        await analyzer.invalidate_cache(entry_id)
        cache = deps["cache"]
        assert str(entry_id) in cache.deleted_keys


# ---------------------------------------------------------------------------
# Tests: analyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_returns_cached_result_on_cache_hit(self) -> None:
        entry = _FakeKBEntry()
        cached = _make_cached_response()
        analyzer, _ = _make_analyzer(cache_data=cached, entry=entry)
        result = await analyzer.analyze(novel_id=uuid4(), entry_id=entry.id)
        assert result.completeness_score == 0.9

    @pytest.mark.asyncio
    async def test_raises_not_found_when_entry_missing(self) -> None:
        analyzer, _ = _make_analyzer(entry=None)
        with pytest.raises(Exception, match="KBEntry"):
            await analyzer.analyze(novel_id=uuid4(), entry_id=uuid4())

    @pytest.mark.asyncio
    async def test_runs_agent_and_caches_on_miss(self) -> None:
        entry = _FakeKBEntry(name="Alice", entity_type="character")
        analyzer, deps = _make_analyzer(cache_data=None, entry=entry)

        from narrare_core.agents.kb_improve_types import (
            ImprovementSuggestion,
            KBImproveOutput,
            SuggestionType,
        )

        output = KBImproveOutput(
            suggestions=[
                ImprovementSuggestion(
                    type=SuggestionType.ADD_FIELD,
                    target="role",
                    description="Add role field",
                    proposed_content="Warrior",
                    confidence=0.8,
                    reasoning="Missing important field",
                )
            ],
            overall_assessment="Good start",
            completeness_score=0.7,
        )

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            MockAgent.return_value.run = AsyncMock(return_value=output)
            result = await analyzer.analyze(novel_id=uuid4(), entry_id=entry.id)

        assert result.completeness_score == 0.7
        assert len(result.suggestions) == 1
        assert result.suggestions[0].type == "add_field"
        cache = deps["cache"]
        assert cache._data is not None


# ---------------------------------------------------------------------------
# Tests: world context sourced from KBContextProvider (ADR-067)
# ---------------------------------------------------------------------------


class TestWorldContextViaProvider:
    """``_build_deps`` obtains world context from the KBContextProvider.

    Consolidates the former inline ``proactive_context.suggest`` + relevance
    formatting: improve now routes through the canonical KBContextProvider so
    kb assist/improve share one world-context source (ADR-067).
    """

    @pytest.mark.asyncio
    async def test_build_deps_sources_world_context_via_provider(self) -> None:
        """_build_deps calls provider.fetch_world_context and flows it into deps.

        Verifies the provider is called with the novel id and the entry's
        entity type, and that the rendered ``- name (type): brief`` aggregate
        flows straight into ``deps.world_context`` (single source).
        """
        canonical_context = "- Alice (character): A brave hero"
        entry = _FakeKBEntry(name="Bob", entity_type="character")
        novel_id = uuid4()
        analyzer, deps = _make_analyzer(entry=entry, world_context=canonical_context)
        provider = deps["provider"]

        built = await analyzer._build_deps(novel_id=novel_id, entry_id=entry.id)

        provider.fetch_world_context.assert_awaited_once()
        call_kwargs = provider.fetch_world_context.call_args
        assert call_kwargs.args[0] == novel_id
        assert call_kwargs.kwargs["entity_type"] == "character"
        # The canonical aggregate flows straight into deps (single source).
        assert built.world_context == canonical_context

    @pytest.mark.asyncio
    async def test_build_deps_degrades_to_empty_world_context(self) -> None:
        """Empty KB yields empty world_context (RULE-11), deps still build."""
        entry = _FakeKBEntry(name="Bob", entity_type="character")
        analyzer, _ = _make_analyzer(entry=entry, world_context="")

        built = await analyzer._build_deps(novel_id=uuid4(), entry_id=entry.id)

        # Empty world_context becomes None on the deps (no enrichment).
        assert built.world_context is None
