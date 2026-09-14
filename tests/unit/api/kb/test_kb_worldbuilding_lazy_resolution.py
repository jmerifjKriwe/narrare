"""Lazy model-resolution semantics for WorldbuildingAnalyzer (ADR-086 L19).

The factory (``kb/dependencies_worldbuilding.py::
get_worldbuilding_service``) wires a ``LazyModelResolution``; this file
pins the ANALYZER-side lazy contract (the analyzer is the config
consumer — the service only orchestrates and gates):

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards,
- ``ConfigurationError`` propagates un-swallowed from the entry points
  (RULE-11 — AI-mandatory endpoints), and resolution PRECEDES the
  analysis cache lookup, so an unconfigured provider stays a loud 400
  even with a warm cache (eager-world status semantics preserved),
- the resolved triple reaches ``ModelRegistry.prepare`` unchanged — the
  eager factory applied no sampling overrides, so none appear (WHAT
  unchanged, only WHEN).

Mirrors ``tests/unit/api/kb/test_kb_improve_lazy_resolution.py``
(ADR-086 L17 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare._app.dependencies_services import ModelResolution
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches.

    Exposes the analyzer-level lazy seam (ADR-086): the analyzer must
    call ``resolve()`` exactly once (first use), never at construction.
    """

    def __init__(self, model: ResolvedModel) -> None:
        self._model = model
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        return self._model


class _RaisingResolution:
    """Fake ModelResolution — the cascade finds no configured provider."""

    async def resolve(self) -> ResolvedModel:
        raise ConfigurationError(
            "No AI provider configured.",
            code="NO_AI_PROVIDER",
        )


def _resolved_model(
    config: ResolvedModelConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=config or ResolvedModelConfig(provider_name="test", model_id="test-model"),
        api_key=api_key,
        base_url=base_url,
        source="unit-test",
    )


# ---------------------------------------------------------------------------
# Minimal domain fakes (self-contained; the analyzer is the unit under test)
# ---------------------------------------------------------------------------


class _FakeKBEntry:
    def __init__(self) -> None:
        self.id = uuid4()
        self.name = "Alice"
        self.entity_type = "character"
        self.metadata_ = {}
        self.body = "Some body text"
        self.tags = []
        self.usage_count = 0


class _FakeKBRepo:
    def __init__(self, entries: list[_FakeKBEntry] | None = None) -> None:
        self._entries = entries or []

    async def list_entries(
        self,
        novel_id: object,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[_FakeKBEntry], int]:
        start = (page - 1) * page_size
        return self._entries[start : start + page_size], len(self._entries)

    async def get_by_id(self, entry_id: object) -> _FakeKBEntry | None:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None


class _FakeRelRepo:
    async def get_adjacency_map(
        self, novel_id: object, entity_ids: set[object] | None = None
    ) -> dict[str, set[str]] | None:
        return {}

    async def list_for_entry(self, entry_id: object) -> list[object]:
        return []


class _FakeComposer:
    async def build(self, intent: object, ctx: object) -> ComposedPrompt:
        return ComposedPrompt(system="worldbuilding system prompt", user="user prompt")


class _FakeCache:
    def __init__(self, data: str | None = None) -> None:
        self._data = data

    async def get(self, novel_id: str, types_hash: str = "") -> str | None:
        return self._data

    async def set(self, novel_id: str, value: str, types_hash: str = "") -> None:
        self._data = value


class _RecordingRegistry:
    """Fake ModelRegistry — records the single prepare() assembly point."""

    def __init__(self) -> None:
        self.get_model = AsyncMock(return_value=MagicMock(spec=["sentinel"], sentinel=True))
        self.prepares: list[dict[str, object]] = []

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        self.prepares.append(
            {"config": config, "intent": intent, "api_key": api_key, "base_url": base_url}
        )
        model = await self.get_model(config, api_key=api_key, base_url=base_url)
        return PreparedModelCall(
            model=cast("Any", model), model_settings=None, usage_limits=usage_limits
        )


def _phase1_output() -> Any:
    """A canned WorldbuildingPhase1Output for the patched agent."""
    from narrare_core.agents.worldbuilding_types import WorldbuildingPhase1Output

    return WorldbuildingPhase1Output(
        gaps=[],
        connection_suggestions=[],
        assessment="OK",
        worldbuilding_score=0.5,
        candidate_pairs_for_consistency=[],
    )


def _make_analyzer(
    model_resolution: ModelResolution,
    *,
    cache: _FakeCache | None = None,
    registry: _RecordingRegistry | None = None,
) -> WorldbuildingAnalyzer:
    """Build a WorldbuildingAnalyzer with the lazy seam injected."""
    return WorldbuildingAnalyzer(
        kb_repo=cast("Any", _FakeKBRepo(entries=[_FakeKBEntry()])),
        rel_repo=cast("Any", _FakeRelRepo()),
        cache=cast("Any", cache or _FakeCache()),
        registry=cast("ModelRegistry", registry or _RecordingRegistry()),
        model_resolution=model_resolution,
        composer=cast("PromptComposer", _FakeComposer()),
    )


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the WorldbuildingAnalyzer boundary."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch the routing cascade."""
        counting = _CountingResolution(_resolved_model())

        _make_analyzer(counting)

        assert counting.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First use resolves exactly once; repeat calls hit the cache."""
        counting = _CountingResolution(_resolved_model())
        analyzer = _make_analyzer(counting)

        first = await analyzer.ensure_resolved()
        second = await analyzer.ensure_resolved()

        assert counting.calls == 1
        assert first is second

    async def test_analyze_resolves_exactly_once(self) -> None:
        """The entry point is the first-use seam — one resolve per analyze."""
        counting = _CountingResolution(_resolved_model())
        analyzer = _make_analyzer(counting)

        # No invocation-pipeline patch needed: pipeline=None degrades to the
        # composer fallback inside _run_phase1 (precedent: prepare-wiring tests).
        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as mock_agent_cls:
            mock_agent_cls.return_value.run_phase1 = AsyncMock(return_value=_phase1_output())
            await analyzer.analyze(
                novel_id=uuid4(),
                request=_analysis_request(),
            )

        assert counting.calls == 1

    async def test_resolver_configuration_error_propagates_un_swallowed(self) -> None:
        """RULE-11 / ADR-086: the cascade's ``ConfigurationError``
        (unconfigured provider) propagates from the entry point — the
        analyzer never swallows it (AI-mandatory endpoint)."""
        analyzer = _make_analyzer(_RaisingResolution())

        with pytest.raises(ConfigurationError):
            await analyzer.analyze(novel_id=uuid4(), request=_analysis_request())

    async def test_resolution_precedes_cache_lookup(self) -> None:
        """An unconfigured provider stays a loud 400 even with a warm
        cache — resolution timing moved, eager-world status semantics
        did not (the eager factory resolved before any cache lookup)."""
        warm_cache = _FakeCache(data=_cached_response_json())
        analyzer = _make_analyzer(_RaisingResolution(), cache=warm_cache)

        with pytest.raises(ConfigurationError):
            await analyzer.analyze(novel_id=uuid4(), request=_analysis_request())

    async def test_resolved_triple_flows_into_prepare_unchanged(self) -> None:
        """Timing-only invariant: the eager factory passed
        ``resolved.config`` + credentials into ``ModelRegistry.prepare``
        verbatim — the lazy analyzer passes the SAME values (no sampling
        overrides exist for ``KB_WORLDBUILD``)."""
        resolved_config = ResolvedModelConfig(
            provider_name="zai",
            model_id="glm-4.7",
            temperature=0.7,
            max_tokens=4096,
        )
        registry = _RecordingRegistry()
        counting = _CountingResolution(
            _resolved_model(
                resolved_config, api_key="sk-user-key", base_url="https://user.example/v1"
            )
        )
        analyzer = _make_analyzer(counting, registry=registry)

        # No invocation-pipeline patch needed: pipeline=None degrades to the
        # composer fallback inside _run_phase1 (precedent: prepare-wiring tests).
        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as mock_agent_cls:
            mock_agent_cls.return_value.run_phase1 = AsyncMock(return_value=_phase1_output())
            await analyzer.analyze(
                novel_id=uuid4(),
                request=_analysis_request(include_consistency=False),
            )

        assert len(registry.prepares) == 1
        prepared = registry.prepares[0]
        assert prepared["config"] is resolved_config
        assert prepared["intent"] is LLMIntent.KB_WORLDBUILD
        assert prepared["api_key"] == "sk-user-key"
        assert prepared["base_url"] == "https://user.example/v1"


def _analysis_request(**overrides: Any) -> Any:
    """A minimal analyze request (consistency off keeps phases single)."""
    from narrare.kb.worldbuilding_contracts import WorldbuildingAnalysisRequest

    defaults: dict[str, Any] = {"refresh": True, "include_consistency": False}
    defaults.update(overrides)
    return WorldbuildingAnalysisRequest(**defaults)


def _cached_response_json() -> str:
    """A valid cached WorldbuildingAnalysisResponse payload (warm cache)."""
    from narrare.kb.worldbuilding_contracts import WorldbuildingAnalysisResponse

    return WorldbuildingAnalysisResponse(
        novel_id=str(uuid4()),
        entity_count=0,
        gap_findings=[],
        connection_suggestions=[],
        consistency_issues=[],
        worldbuilding_score=0.5,
        overall_assessment="Cached",
        summary={
            "total_entities": 0,
            "gaps_found": 0,
            "connections_suggested": 0,
            "consistency_issues": 0,
            "entities_in_analysis": 0,
        },
        analyzed_at="2025-01-01T00:00:00Z",
    ).model_dump_json()
