"""Lazy model-resolution semantics for SeriesConsistencyService (ADR-086 L26).

The factory (``series/dependencies_consistency.py::
get_series_consistency_service``) wires a ``LazyModelResolution``; this file
pins the SERVICE-side lazy contract:

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards,
- ``ConfigurationError`` propagates un-swallowed from the entry point
  (RULE-11 — AI-mandatory endpoint), with the ownership gates running
  FIRST (gates stay ahead of resolution),
- the resolved triple reaches ``ModelRegistry.prepare`` unchanged — the
  eager factory applied no sampling overrides, so none appear (WHAT
  unchanged, only WHEN),
- the graceful no-canon/no-prose early exit is DOWNSTREAM of resolution:
  an unconfigured provider stays a loud 400-equivalent even when the
  check would degrade to an empty result (the eager factory resolved
  before the early exit too — timing-only migration).

Mirrors ``tests/unit/api/kb/test_extraction_service_lazy_resolution.py``
(ADR-086 L16 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

from narrare.series.series_consistency_service import SeriesConsistencyService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError, ForbiddenError
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_kb_scope_repo import FakeScopeKBRepo
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

from ._series_consistency_test_helpers import (
    FakeSeriesConsistencyAgent,
    FakeSeriesConsistencyComposer,
    make_config,
    seed_owned_series_with_canon,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare._app.dependencies_services import ModelResolution
    from narrare_core.llm.gateway import ModelRegistry


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches.

    Exposes the service-level lazy seam (ADR-086): the service must call
    ``resolve()`` exactly once (first use), never at construction.
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


class _RecordingRegistry:
    """Minimal ModelRegistry fake — records the prepare() call verbatim."""

    def __init__(self) -> None:
        self.prepare_kwargs: dict[str, Any] | None = None
        self.prepare_config: Any = None

    async def prepare(self, config: Any, **kwargs: Any) -> Any:
        from types import SimpleNamespace

        self.prepare_config = config
        self.prepare_kwargs = kwargs
        return SimpleNamespace(model=object(), model_settings=None, usage_limits=None)


def _resolved_model(
    config: ResolvedModelConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=config or make_config(),
        api_key=api_key,
        base_url=base_url,
        source="unit-test",
    )


def _make_service(
    model_resolution: ModelResolution,
    registry: _RecordingRegistry | None = None,
    *,
    seed: bool = True,
) -> tuple[SeriesConsistencyService, FakeSeriesConsistencyAgent, Any, Any, Any]:
    """Build a SeriesConsistencyService with the lazy seam injected.

    When ``seed`` is True, an owned series + member novel + Canon entries
    + prose chapters are seeded so ``check_novel`` flows past the gates
    into the invocation assembly. Returns
    ``(service, agent, series_id, novel_id, user_id)``.
    """
    series_repo = FakeSeriesRepository()
    novel_repo = FakeNovelRepository()
    chapter_repo = FakeChapterRepository()
    kb_repo = FakeScopeKBRepo()
    agent = FakeSeriesConsistencyAgent()

    user_id = uuid4()
    if seed:
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )
    else:
        series_id, novel_id = uuid4(), uuid4()

    def _agent_factory(model: Any, system_prompt: Any = None) -> FakeSeriesConsistencyAgent:
        del system_prompt
        agent.last_model = model
        return agent

    service = SeriesConsistencyService(
        series_repo=cast("Any", series_repo),
        novel_repo=cast("Any", novel_repo),
        chapter_repo=cast("Any", chapter_repo),
        kb_repo=cast("Any", kb_repo),
        registry=cast("ModelRegistry", registry or _RecordingRegistry()),
        model_resolution=model_resolution,
        composer=cast("Any", FakeSeriesConsistencyComposer()),
        agent_factory=cast("Callable[..., Any]", _agent_factory),
    )
    return service, agent, series_id, novel_id, user_id


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the SeriesConsistencyService boundary."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch the routing cascade."""
        counting = _CountingResolution(_resolved_model())

        _make_service(counting)

        assert counting.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First use resolves exactly once; repeat calls hit the cache."""
        counting = _CountingResolution(_resolved_model())
        service = _make_service(counting)[0]

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert counting.calls == 1
        assert first is second

    async def test_check_novel_resolves_exactly_once(self) -> None:
        """The entry point is the first-use seam — one resolve per check."""
        counting = _CountingResolution(_resolved_model())
        service, _agent, series_id, novel_id, user_id = _make_service(counting)

        await service.check_novel(series_id, novel_id, user_id)

        assert counting.calls == 1

    async def test_resolver_configuration_error_propagates_un_swallowed(self) -> None:
        """RULE-11 / ADR-086: the cascade's ``ConfigurationError``
        (unconfigured provider) propagates from the entry point — the
        service never swallows it (AI-mandatory endpoint). The ownership
        gates run FIRST and pass (seeded repos), so the error comes from
        resolution, proving gates stay ahead of resolution."""
        service, _agent, series_id, novel_id, user_id = _make_service(
            _RaisingResolution(), registry=_RecordingRegistry()
        )

        with pytest.raises(ConfigurationError):
            await service.check_novel(series_id, novel_id, user_id)

    async def test_ownership_gates_stay_ahead_of_resolution(self) -> None:
        """A non-owned series is rejected with ``ForbiddenError`` and the
        routing cascade is NEVER invoked — the gates precede resolution
        (eager-world precedence preserved; MUST-NOT-change list)."""
        counting = _CountingResolution(_resolved_model())
        service, _agent, _series_id, novel_id, _user_id = _make_service(
            counting, registry=_RecordingRegistry()
        )

        with pytest.raises(ForbiddenError):
            await service.check_novel(uuid4(), novel_id, uuid4())

        assert counting.calls == 0

    async def test_unconfigured_provider_stays_loud_on_graceful_degradation_path(
        self,
    ) -> None:
        """The no-canon early exit is DOWNSTREAM of resolution: with an
        unconfigured provider the entry point raises ``ConfigurationError``
        instead of returning the empty degradation result — the eager
        factory also failed before the early exit could run (timing-only
        invariant: WHAT is unchanged, only WHEN)."""
        service, _agent, series_id, novel_id, user_id = _make_service(
            _RaisingResolution(), registry=_RecordingRegistry()
        )
        # Wipe the Canon entries → the graceful empty-result path would
        # trigger IF resolution were deferred past it.
        kb_repo = cast("FakeScopeKBRepo", service._kb_repo)
        kb_repo._entries.clear()

        with pytest.raises(ConfigurationError):
            await service.check_novel(series_id, novel_id, user_id)

    async def test_resolved_triple_flows_into_prepare_unchanged(self) -> None:
        """Timing-only invariant: the eager factory passed
        ``resolved.config`` + credentials into the invocation assembly
        verbatim — the lazy service passes the SAME values (no sampling
        overrides exist for series consistency's ANALYSE resolve)."""
        resolved_config = ResolvedModelConfig(
            provider_name="zai",
            model_id="glm-4.7",
            temperature=0.7,
            max_tokens=4096,
        )
        registry = _RecordingRegistry()
        counting = _CountingResolution(_resolved_model(resolved_config, api_key="sk-user-key"))
        service, agent, series_id, novel_id, user_id = _make_service(counting, registry=registry)

        await service.check_novel(series_id, novel_id, user_id)

        assert agent.run_count == 1
        assert registry.prepare_config is resolved_config
        assert registry.prepare_kwargs is not None
        assert registry.prepare_kwargs["api_key"] == "sk-user-key"
        assert registry.prepare_kwargs["intent"].name == "ANALYSE"
