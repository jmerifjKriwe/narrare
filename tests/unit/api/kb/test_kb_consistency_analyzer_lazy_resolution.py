"""Lazy model-resolution semantics for KBConsistencyAnalyzer (ADR-086 L15).

The consistency factory wires the ``KB_CONSISTENCY`` cascade as a
``LazyModelResolution``; this file pins the ANALYZER-side lazy contract
(the analyzer is the config consumer):

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards — and the
  resolve runs at the entry-point top, BEFORE any entity listing, so it
  happens even when the entity list comes back empty (the eager factory
  resolved unconditionally; WHAT unchanged, only WHEN),
- ``ConfigurationError`` propagates un-swallowed from the entry point
  (RULE-11 — AI-mandatory endpoint),
- the resolved triple reaches ``ModelRegistry.run`` unchanged.

Service-side dual-resolve pins live in
``test_kb_consistency_lazy_resolution.py``. Mirrors
``tests/unit/api/kb/test_kb_worldbuilding_lazy_resolution.py``
(ADR-086 L19 precedent).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol


# ---------------------------------------------------------------------------
# Resolution fakes (the lazy seam under test)
# ---------------------------------------------------------------------------


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches."""

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


def _resolved_model() -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=ResolvedModelConfig(provider_name="test", model_id="test-model"),
        api_key=None,
        base_url=None,
        source="unit-test",
    )


# ---------------------------------------------------------------------------
# Minimal domain fakes (self-contained; the analyzer is the unit under test)
# ---------------------------------------------------------------------------


class _StopResolution(Exception):
    """Sentinel — stops the analyzer right after the recorded run() call."""


class _FakeKBRepo:
    """Empty KB repo — list/get are never reached past the resolve pins."""

    async def list_entries(
        self,
        novel_id: object,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[object], int]:
        return [], 0

    async def get_by_id(self, entry_id: object) -> object | None:
        return None


class _FakeComposer:
    async def build(self, intent: object, ctx: object) -> Any:
        return SimpleNamespace(system="consistency system prompt", user="user prompt")


class _RecordingRunRegistry:
    """Fake ModelRegistry — records run() calls (single assembly point)."""

    def __init__(self) -> None:
        self.run_calls: list[dict[str, object]] = []

    async def run(self, **kwargs: object) -> object:
        self.run_calls.append(kwargs)
        raise _StopResolution()


def _make_analyzer(
    resolution: object,
) -> tuple[KBConsistencyAnalyzer, _RecordingRunRegistry]:
    """Build KBConsistencyAnalyzer over fakes with the given resolution."""
    registry = _RecordingRunRegistry()
    analyzer = KBConsistencyAnalyzer(
        kb_repo=cast("KBRepositoryProtocol", _FakeKBRepo()),
        registry=cast("Any", registry),
        model_resolution=cast("Any", resolution),
        composer=cast("Any", _FakeComposer()),
    )
    return analyzer, registry


# ===========================================================================
# Analyzer-side lazy contract
# ===========================================================================


class TestAnalyzerLazyContract:
    """KBConsistencyAnalyzer resolves on first use — never at construction."""

    async def test_no_resolution_at_construction(self) -> None:
        resolution = _CountingResolution(_resolved_model())

        _make_analyzer(resolution)

        assert resolution.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        resolution = _CountingResolution(_resolved_model())
        analyzer, _registry = _make_analyzer(resolution)

        first = await analyzer.ensure_resolved()
        second = await analyzer.ensure_resolved()

        assert resolution.calls == 1
        assert second is first

    async def test_analyze_entries_resolves_exactly_once_even_with_no_entities(
        self,
    ) -> None:
        """First use resolves at the entry-point top — before list_entities.

        The eager factory resolved unconditionally; the lazy first use
        must therefore run even when the entity list comes back empty.
        """
        resolution = _CountingResolution(_resolved_model())
        analyzer, registry = _make_analyzer(resolution)

        issues, count = await analyzer.analyze_entries(uuid4(), None)

        assert issues == []
        assert count == 0
        assert resolution.calls == 1
        assert registry.run_calls == []

    async def test_analyze_entries_configuration_error_propagates_un_swallowed(
        self,
    ) -> None:
        resolution = _RaisingResolution()
        analyzer, _registry = _make_analyzer(resolution)

        with pytest.raises(ConfigurationError):
            await analyzer.analyze_entries(uuid4(), None)

    async def test_resolved_triple_flows_into_run_unchanged(self) -> None:
        """The cascade triple (config + credentials) reaches registry.run.

        The factory applied no sampling overrides, so none may appear
        (WHAT unchanged, only WHEN — L15 parity with the L19 pin).
        """
        triple = ResolvedModel(
            config=ResolvedModelConfig(provider_name="test", model_id="run-model"),
            api_key="sk-run",
            base_url="https://run.example/v1",
            source="unit-test",
        )
        analyzer, registry = _make_analyzer(_CountingResolution(triple))
        entity = SimpleNamespace(
            id=uuid4(),
            name="Entry",
            entity_type="character",
            metadata_={},
            body="Body text.",
            tags=[],
        )

        with pytest.raises(_StopResolution):
            await analyzer._analyze_entry(cast("Any", entity))

        assert len(registry.run_calls) == 1
        run_call = registry.run_calls[0]
        assert run_call["intent"] is LLMIntent.KB_CONSISTENCY
        assert run_call["config"] is triple.config
        assert run_call["api_key"] == "sk-run"
        assert run_call["base_url"] == "https://run.example/v1"

    async def test_run_credentials_resolution_is_not_cached_on_error(self) -> None:
        """A failed resolve is never cached — the next use retries (RULE-11).

        Mirrors the LazyModelResolution error contract at the analyzer
        seam: ``ConfigurationError`` propagates and leaves ``_resolved``
        unset, so a later configured attempt resolves fresh.
        """
        attempts: list[ResolvedModel] = []

        class _FlakyResolution:
            def __init__(self) -> None:
                self.calls = 0

            async def resolve(self) -> ResolvedModel:
                self.calls += 1
                if self.calls == 1:
                    raise ConfigurationError(
                        "No AI provider configured.",
                        code="NO_AI_PROVIDER",
                    )
                triple = _resolved_model()
                attempts.append(triple)
                return triple

        resolution = _FlakyResolution()
        analyzer, _registry = _make_analyzer(resolution)

        with pytest.raises(ConfigurationError):
            await analyzer.ensure_resolved()

        triple = await analyzer.ensure_resolved()
        assert resolution.calls == 2
        assert len(attempts) == 1
        assert triple is attempts[0]
