"""Service-side dual lazy-resolution pins for KBConsistencyService (ADR-086 L15).

The factory wires TWO ``LazyModelResolution``s — the DUAL resolve:
``LLMIntent.KB_CONSISTENCY`` for the entry-internal analyzer and
``LLMIntent.KB_WORLDBUILD`` for the reused cross-entity worldbuilding
analyzer. This file pins the SERVICE-side contract of the stack:

- no resolution at construction of the assembled service,
- check() resolves BOTH cascades exactly once — even for asymmetry-only
  checks (the eager factory resolved unconditionally; WHAT unchanged,
  only WHEN), idempotent across repeat calls,
- resolution runs after the novel ownership gate and BEFORE the cache
  probe, so an unconfigured provider stays a loud 400 even with a warm
  cache (eager-factory semantics preserved; L19 precedent),
- the dual intents land on the correct consumers: the worldbuild triple
  on ``service._worldbuilding_analyzer.ensure_resolved()`` (is-identity
  pin), the consistency triple on ``service._analyzer.ensure_resolved()``,
- ``ConfigurationError`` propagates un-swallowed (RULE-11).

Analyzer-side pins: ``test_kb_consistency_analyzer_lazy_resolution.py``.
Factory-level wiring pins: ``test_deps_user_routing_1b.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from narrare._app.dependencies_services import LazyModelResolution
from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
from narrare.kb.consistency_contracts import ConsistencyCheckRequest, ConsistencyCheckResponse
from narrare.kb.consistency_service import KBConsistencyService
from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError, NotFoundError

from ._test_fakes import FakeNovelRepo

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol


# ---------------------------------------------------------------------------
# Fakes (plumbing only — the resolve seam is the unit under test)
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


def _resolved_model(model_id: str, api_key: str) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=ResolvedModelConfig(provider_name="test", model_id=model_id),
        api_key=api_key,
        base_url=None,
        source="unit-test",
    )


class _IntentDispatchingResolver:
    """Fake ModelRoutingResolverImpl — counting async resolve per intent."""

    def __init__(self, triples: dict[LLMIntent, ResolvedModel]) -> None:
        self._triples = triples
        self.resolve = AsyncMock(side_effect=lambda intent, *_a: self._triples[intent])


class _FakeAsymmetryChecker:
    async def check(self, novel_id: object) -> list[object]:
        return []


class _FakeConsistencyCache:
    def __init__(self, data: str | None = None) -> None:
        self._data = data

    def hash_entity_types(self, entity_types: list[str] | None) -> str:
        return ",".join(entity_types) if entity_types else ""

    async def get(self, novel_id: str, types_hash: str = "") -> str | None:
        return self._data

    async def set(self, novel_id: str, value: str, types_hash: str = "") -> None:
        self._data = value


def _cached_response_json(novel_id: UUID) -> str:
    """A cached ConsistencyCheckResponse payload (warm-cache probe)."""
    return ConsistencyCheckResponse(
        novel_id=str(novel_id),
        entity_count=7,
        issues=[],
        summary={"entry_internal": 0, "asymmetry": 0, "cross_entity": 0},
        suppressed_count=0,
        checked_at="2026-01-01T00:00:00+00:00",
    ).model_dump_json()


def _make_stack(
    consistency_resolution: object,
    worldbuild_resolution: object,
    *,
    cache_data: str | None = None,
    novel_repo: FakeNovelRepo | None = None,
) -> KBConsistencyService:
    """Assemble the real consistency service over fake edges.

    The analyzers' non-resolve plumbing is inert MagicMock plumbing
    (routing-test convention): service-level checks here never reach a
    phase that touches registry/composer/repos.
    """
    analyzer = KBConsistencyAnalyzer(
        kb_repo=cast("KBRepositoryProtocol", MagicMock(spec=True, name="KBRepository")),
        registry=cast("Any", MagicMock(spec=True, name="ModelRegistry")),
        model_resolution=cast("Any", consistency_resolution),
        composer=cast("Any", MagicMock(spec=True, name="PromptComposer")),
    )
    worldbuilding_analyzer = WorldbuildingAnalyzer(
        kb_repo=cast("KBRepositoryProtocol", MagicMock(spec=True, name="KBRepository")),
        rel_repo=cast("Any", MagicMock(spec=True, name="RelationshipRepository")),
        cache=cast("Any", MagicMock(spec=True, name="WorldbuildingCache")),
        registry=cast("Any", MagicMock(spec=True, name="ModelRegistry")),
        model_resolution=cast("Any", worldbuild_resolution),
        composer=cast("Any", MagicMock(spec=True, name="PromptComposer")),
    )
    return KBConsistencyService(
        analyzer=analyzer,
        asymmetry_checker=cast("Any", _FakeAsymmetryChecker()),
        worldbuilding_analyzer=worldbuilding_analyzer,
        kb_repo=cast("KBRepositoryProtocol", MagicMock(spec=True, name="KBRepository")),
        rel_repo=cast("Any", MagicMock(spec=True, name="RelationshipRepository")),
        cache=cast("Any", _FakeConsistencyCache(cache_data)),
        novel_repo=cast("Any", novel_repo or FakeNovelRepo()),
    )


# ===========================================================================
# Service-side dual lazy contract
# ===========================================================================


class TestServiceDualLazyResolution:
    """check() resolves BOTH cascades at first use — dual resolve, L15."""

    _ASYMMETRY_ONLY = ConsistencyCheckRequest(
        include_asymmetry=True,
        include_entry_internal=False,
        include_cross_entity=False,
    )

    def _wired_stack(
        self,
        *,
        cache_data: str | None = None,
        novel_repo: FakeNovelRepo | None = None,
    ) -> tuple[KBConsistencyService, _IntentDispatchingResolver, ResolvedModel, ResolvedModel]:
        """Real factory wiring shape: one LazyModelResolution per intent."""
        resolved_consistency = _resolved_model("consistency-model", "sk-consistency")
        resolved_worldbuild = _resolved_model("worldbuild-model", "sk-worldbuild")
        resolver = _IntentDispatchingResolver(
            {
                LLMIntent.KB_CONSISTENCY: resolved_consistency,
                LLMIntent.KB_WORLDBUILD: resolved_worldbuild,
            }
        )
        user_id = uuid4()
        novel_id = uuid4()
        service = _make_stack(
            LazyModelResolution(
                lambda: resolver.resolve(LLMIntent.KB_CONSISTENCY, user_id, novel_id)
            ),
            LazyModelResolution(
                lambda: resolver.resolve(LLMIntent.KB_WORLDBUILD, user_id, novel_id)
            ),
            cache_data=cache_data,
            novel_repo=novel_repo,
        )
        return service, resolver, resolved_consistency, resolved_worldbuild

    async def test_service_construction_resolves_nothing(self) -> None:
        _service, resolver, _consistency, _worldbuild = self._wired_stack()

        assert resolver.resolve.await_args_list == []

    async def test_check_resolves_both_cascades_exactly_once(self) -> None:
        """Even an asymmetry-only check resolves BOTH cascades — once each.

        The eager factory resolved unconditionally at construction, so
        the lazy first use must not become phase-conditional (WHAT
        unchanged, only WHEN).
        """
        service, resolver, _consistency, _worldbuild = self._wired_stack()

        await service.check(novel_id=uuid4(), request=self._ASYMMETRY_ONLY, user_id=str(uuid4()))

        assert resolver.resolve.await_count == 2

    async def test_check_repeat_calls_are_idempotent_no_reresolve(self) -> None:
        service, resolver, _consistency, _worldbuild = self._wired_stack()

        await service.check(novel_id=uuid4(), request=self._ASYMMETRY_ONLY, user_id=str(uuid4()))
        await service.check(novel_id=uuid4(), request=self._ASYMMETRY_ONLY, user_id=str(uuid4()))

        assert resolver.resolve.await_count == 2  # cached per cascade

    async def test_dual_intents_land_on_correct_consumers(self) -> None:
        """Identity pin: worldbuild triple on the worldbuilding analyzer.

        The consistency stack reuses WorldbuildingAnalyzer for Phase 3 —
        the dual wiring must keep the KB_WORLDBUILD cascade on THAT
        analyzer and the KB_CONSISTENCY cascade on the entry-internal
        analyzer (a crossed wire would silently swap intents).
        """
        service, _resolver, resolved_consistency, resolved_worldbuild = self._wired_stack()

        consistency_triple = await service._analyzer.ensure_resolved()
        worldbuild_triple = await service._worldbuilding_analyzer.ensure_resolved()

        assert consistency_triple is resolved_consistency
        assert worldbuild_triple is resolved_worldbuild
        assert worldbuild_triple.api_key == "sk-worldbuild"

    async def test_check_resolution_precedes_cache_lookup(self) -> None:
        """Warm cache still resolves — unconfigured provider stays loud 400.

        Eager-factory semantics preserved (L19 precedent): resolution
        runs BEFORE the cache probe, so a cached report never masks an
        unconfigured provider.
        """
        novel_id = uuid4()
        service, resolver, _consistency, _worldbuild = self._wired_stack(
            cache_data=_cached_response_json(novel_id)
        )

        result = await service.check(
            novel_id=novel_id, request=self._ASYMMETRY_ONLY, user_id=str(uuid4())
        )

        assert resolver.resolve.await_count == 2
        assert result.entity_count == 7  # the cached report came back

    async def test_ownership_gate_precedes_resolution(self) -> None:
        """Foreign novel → 404 class at the gate; the cascade never runs.

        Gates stay ahead of resolution (plan constraint 5): the
        resolver's DB reads must not happen for a caller who does not
        own the novel.
        """
        service, resolver, _consistency, _worldbuild = self._wired_stack(
            novel_repo=FakeNovelRepo(ownership={})  # nobody owns anything
        )

        with pytest.raises(NotFoundError):
            await service.check(
                novel_id=uuid4(), request=self._ASYMMETRY_ONLY, user_id=str(uuid4())
            )

        assert resolver.resolve.await_args_list == []

    async def test_check_configuration_error_propagates_un_swallowed(self) -> None:
        service = _make_stack(
            _RaisingResolution(),
            _CountingResolution(_resolved_model("worldbuild-model", "sk-worldbuild")),
        )

        with pytest.raises(ConfigurationError):
            await service.check(
                novel_id=uuid4(), request=self._ASYMMETRY_ONLY, user_id=str(uuid4())
            )
