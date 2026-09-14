"""Lazy model-resolution semantics for KBImproveAnalyzer (ADR-086 L17).

The factory (``kb/dependencies_improve.py::get_kb_improve_service``)
wires a ``LazyModelResolution``; this file pins the ANALYZER-side lazy
contract (the analyzer is the config consumer — the service only
orchestrates and gates):

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards,
- ``ConfigurationError`` propagates un-swallowed from the entry points
  (RULE-11 — AI-mandatory endpoints), and resolution PRECEDES the
  analysis cache lookup, so an unconfigured provider stays a loud 400
  even with a warm cache (eager-world status semantics preserved),
- the resolved triple reaches ``ModelRegistry.prepare`` unchanged — the
  eager factory applied no sampling overrides, so none appear (WHAT
  unchanged, only WHEN).

Mirrors ``tests/unit/api/kb/test_extraction_service_lazy_resolution.py``
(ADR-086 L16 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.kb.improve_analyzer import KBImproveAnalyzer
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
        self.novel_id = uuid4()


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


class _FakeProvider:
    """Fake KBContextProviderProtocol — RULE-11 degradation (never raises)."""

    def __init__(self) -> None:
        self.fetch_world_context = AsyncMock(return_value="")
        self.fetch_context = AsyncMock()
        self.fetch_entities = AsyncMock(return_value=[])


class _FakeComposer:
    async def build(self, intent: object, ctx: object) -> ComposedPrompt:
        return ComposedPrompt(system="improve system prompt", user="user prompt")


class _FakeCache:
    def __init__(self, data: str | None = None) -> None:
        self._data = data

    async def get(self, key: str) -> str | None:
        return self._data

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._data = value

    async def delete(self, key: str) -> None:
        self._data = None


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


def _make_analyzer(
    model_resolution: ModelResolution,
    *,
    entry: _FakeKBEntry | None = None,
    cache: _FakeCache | None = None,
    registry: _RecordingRegistry | None = None,
) -> KBImproveAnalyzer:
    """Build a KBImproveAnalyzer with the lazy seam injected."""
    return KBImproveAnalyzer(
        registry=cast("ModelRegistry", registry or _RecordingRegistry()),
        model_resolution=model_resolution,
        kb_context_provider=cast("Any", _FakeProvider()),
        prompt_composer=cast("PromptComposer", _FakeComposer()),
        kb_repo=cast("Any", _FakeKBRepo(entry=entry)),
        rel_repo=cast("Any", _FakeRelRepo()),
        improve_cache=cast("Any", cache),
    )


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the KBImproveAnalyzer boundary."""

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
        entry = _FakeKBEntry()
        counting = _CountingResolution(_resolved_model())
        analyzer = _make_analyzer(counting, entry=entry)

        output = MagicMock(spec=["suggestions", "overall_assessment", "completeness_score"])
        output.suggestions = []
        output.overall_assessment = "Solid entry."
        output.completeness_score = 0.9

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as mock_agent_cls:
            mock_agent_cls.return_value.run = AsyncMock(return_value=output)
            await analyzer.analyze(novel_id=uuid4(), entry_id=entry.id)

        assert counting.calls == 1

    async def test_resolver_configuration_error_propagates_un_swallowed(self) -> None:
        """RULE-11 / ADR-086: the cascade's ``ConfigurationError``
        (unconfigured provider) propagates from the entry point — the
        analyzer never swallows it (AI-mandatory endpoint)."""
        analyzer = _make_analyzer(_RaisingResolution())

        with pytest.raises(ConfigurationError):
            await analyzer.analyze(novel_id=uuid4(), entry_id=uuid4())

    async def test_resolution_precedes_cache_lookup(self) -> None:
        """An unconfigured provider stays a loud 400 even with a warm
        cache — resolution timing moved, eager-world status semantics
        did not (the eager factory resolved before any cache lookup)."""
        entry = _FakeKBEntry()
        warm_cache = _FakeCache(
            data='{"suggestions": [], "overall_assessment": "x", "completeness_score": 1.0}'
        )
        analyzer = _make_analyzer(_RaisingResolution(), entry=entry, cache=warm_cache)

        with pytest.raises(ConfigurationError):
            await analyzer.analyze(novel_id=uuid4(), entry_id=entry.id)

    async def test_resolved_triple_flows_into_prepare_unchanged(self) -> None:
        """Timing-only invariant: the eager factory passed
        ``resolved.config`` + credentials into ``ModelRegistry.prepare``
        verbatim — the lazy analyzer passes the SAME values (no sampling
        overrides exist for ``KB_IMPROVE``)."""
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
        entry = _FakeKBEntry()
        analyzer = _make_analyzer(counting, entry=entry, registry=registry)

        output = MagicMock(spec=["suggestions", "overall_assessment", "completeness_score"])
        output.suggestions = []
        output.overall_assessment = "Solid entry."
        output.completeness_score = 0.9

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as mock_agent_cls:
            mock_agent_cls.return_value.run = AsyncMock(return_value=output)
            await analyzer.analyze(novel_id=entry.novel_id, entry_id=entry.id)

        assert len(registry.prepares) == 1
        prepared = registry.prepares[0]
        assert prepared["config"] is resolved_config
        assert prepared["intent"] is LLMIntent.KB_IMPROVE
        assert prepared["api_key"] == "sk-user-key"
        assert prepared["base_url"] == "https://user.example/v1"
