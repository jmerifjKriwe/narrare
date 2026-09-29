"""Lazy first-use resolve of ConsistencyCheckerService + orchestrator
(ADR-086 L13, S4b-dual shape).

Service-level half of the L13 lazy contract:

- ``get_consistency_service`` wires TWO ``LazyModelResolution``s
  (FACT_EXTRACT + CONSISTENCY) and performs NO routing work at
  construction — the eager factory resolved both cascades at wiring
  time, preempting legitimate 422s (ADR-086 defect class).
- First use resolves BOTH cascades exactly once, in the eager
  factory's verbatim order (extractor first, checker second), applies
  the legacy temperature overrides (0.2 / 0.3) to the RESOLVED configs,
  and is idempotent on repeat (``LazyModelResolution`` caching).
- Resolution runs AFTER the uid-scoped novel ownership gate
  (``collect_check_context`` → ``novel_repo.get_by_id(novel_id,
  user_id)``) — gate-before-resolution ordering (L15 convention).
- ``ConfigurationError`` (no AI provider configured) propagates loudly
  from the entry point — un-swallowed (RULE-11; consistency endpoints
  are AI-mandatory — this is NOT the planning graceful set).
- Legacy-only wiring (no orchestrator) resolves ONLY the CONSISTENCY
  cascade — the fact cascade is staged-pipeline-only.

The factory-level construction-neutrality pin lives in
``TestFactoryConstructionNeutrality``. Credential threading into the
real ``ModelRegistry.prepare`` resolution points stays pinned in
``test_deps_user_routing.py`` / ``test_consistency_prepare_wiring.py``.

See:
    ADR-086 — lazy model resolution (L13; S4b-dual)
    docs/superpowers/plans/2026-09-12-adr086-ledger-migration.md §3 #13
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, Protocol, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.agents.fact_extractor_types import FactExtractorOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos

if TYPE_CHECKING:
    from uuid import UUID

    from narrare._app.dependencies_services import ModelResolution
    from narrare.consistency.checker_service import ConsistencyCheckerService
    from narrare.consistency.consistency_orchestrator import ConsistencyOrchestrator
    from narrare.consistency.schemas import ConsistencyRequest
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts import PromptComposer

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _cascade_config() -> ResolvedModelConfig:
    """The config a wired-up user's cascade would return."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


def _resolved() -> ResolvedModel:
    """A fixed cascade result, as the routing resolver would return it."""
    return ResolvedModel(
        config=_cascade_config(),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
        source="unit-test",
    )


class _CountingResolution:
    """Fake ``ModelResolution`` — counts ``resolve()`` calls."""

    def __init__(self, result: ResolvedModel | None = None, error: Exception | None = None):
        self._result = result if result is not None else _resolved()
        self._error = error
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._result


class _TracedResolution(_CountingResolution):
    """Counting resolution that appends to a shared ordering trace."""

    def __init__(self, trace: list[str]) -> None:
        super().__init__()
        self._trace = trace

    async def resolve(self) -> ResolvedModel:
        self._trace.append("resolve")
        return await super().resolve()


class _GateOrderingNovelRepo(FakeNovelRepository):
    """Fake novel repo recording the ownership-gate call into a shared trace."""

    def __init__(self, trace: list[str]) -> None:
        super().__init__()
        self._trace = trace

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object:
        self._trace.append("gate")
        return await super().get_by_id(novel_id, user_id)


class _RegistryProto(Protocol):
    """Minimal registry protocol for spec'd mocks (RULE-TEST-01)."""

    async def prepare(self, config: object, **kw: object) -> object: ...


def _async_registry() -> MagicMock:
    """Registry stub with an async ``prepare`` (single assembly point)."""
    registry = MagicMock(spec=_RegistryProto)
    registry.prepare = AsyncMock(
        return_value=SimpleNamespace(model=object(), model_settings=None, usage_limits=None)
    )
    return registry


def _async_composer() -> AsyncMock:
    """Composer stub with an async ``build`` returning a composed prompt."""
    from narrare_core.prompts.composer import ComposedPrompt

    composer = AsyncMock()
    composer.build = AsyncMock(
        return_value=ComposedPrompt(system="System prompt.", user="User prompt.")
    )
    return composer


def _wired(
    fact: ModelResolution | None = None,
    consistency: ModelResolution | None = None,
) -> tuple[ConsistencyOrchestrator, ConsistencyCheckerService]:
    """Orchestrator + service sharing counting resolutions."""
    from narrare.consistency.checker_service import ConsistencyCheckerService
    from narrare.consistency.consistency_orchestrator import ConsistencyOrchestrator

    orchestrator = ConsistencyOrchestrator(
        registry=cast("ModelRegistry", _async_registry()),
        fact_extractor_resolution=fact if fact is not None else _CountingResolution(),
        consistency_resolution=consistency if consistency is not None else _CountingResolution(),
        composer=cast("PromptComposer", _async_composer()),
    )
    service = ConsistencyCheckerService(
        chapter_repo=FakeChapterRepository(),
        novel_repo=FakeNovelRepository(),
        kb_repo=AsyncMock(list_entries=AsyncMock(return_value=([], 0))),
        timeline_repo=AsyncMock(),
        registry=cast("ModelRegistry", MagicMock(spec=_RegistryProto)),
        consistency_resolution=(consistency if consistency is not None else _CountingResolution()),
        composer=cast("PromptComposer", AsyncMock()),
        orchestrator=orchestrator,
    )
    return orchestrator, service


def _seeded(
    fact: ModelResolution | None = None,
    consistency: ModelResolution | None = None,
    *,
    trace: list[str] | None = None,
):
    """Service over seeded fake repos (novel + one chapter, same owner)."""
    from narrare.consistency.checker_service import ConsistencyCheckerService

    novel = make_novel()
    chapter = make_chapter(novel_id=novel.id)
    novel_repo = _GateOrderingNovelRepo(trace) if trace is not None else FakeNovelRepository()
    chapter_repo = FakeChapterRepository()
    seed_repos(novel, chapter, novel_repo=novel_repo, chapter_repo=chapter_repo)
    timeline_repo = AsyncMock()
    timeline_repo.list_by_novel = AsyncMock(return_value=[])
    composed = MagicMock(spec=["system", "user"])
    composed.system = "Test prompt"
    composed.user = ""
    composer = AsyncMock()
    composer.build = AsyncMock(return_value=composed)

    if consistency is None:
        consistency = _CountingResolution()
    if fact is None:
        fact = _CountingResolution()

    orchestrator = _wired(fact, consistency)[0]
    service = ConsistencyCheckerService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        kb_repo=AsyncMock(list_entries=AsyncMock(return_value=([], 0))),
        timeline_repo=timeline_repo,
        registry=cast("ModelRegistry", MagicMock(spec=_RegistryProto)),
        consistency_resolution=consistency,
        composer=cast("PromptComposer", composer),
        orchestrator=orchestrator,
    )
    return service, novel, chapter


def _consistency_agent() -> AsyncMock:
    """Canned staged stage-2 agent returning a ConsistencyOutput."""
    from narrare_core.agents.consistency_types import (
        ConsistencyCheckType,
        ConsistencyOutput,
    )

    return AsyncMock(
        run=AsyncMock(
            return_value=ConsistencyOutput(
                issues=[],
                overall_assessment="No issues.",
                checked_types=[ConsistencyCheckType.CHARACTER],
            )
        )
    )


def _request() -> ConsistencyRequest:
    from narrare.consistency.schemas import ConsistencyRequest

    return ConsistencyRequest()


# ===========================================================================
# Service-level — first-use resolve, idempotency, overrides, ordering
# ===========================================================================


class TestFirstUseResolution:
    """Both cascades resolve exactly once, extractor order, idempotent."""

    async def test_ensure_resolved_resolves_both_cascades_once_and_is_idempotent(self) -> None:
        fact = _CountingResolution()
        consistency = _CountingResolution()
        _, service = _wired(fact, consistency)

        await service.ensure_resolved()
        await service.ensure_resolved()

        assert fact.calls == 1
        assert consistency.calls == 1

    async def test_ensure_resolved_applies_legacy_temperature_overrides(self) -> None:
        """0.2 extractor / 0.3 checker on the RESOLVED configs — routing
        fields untouched (dataclasses.replace semantics preserved from
        the eager factory)."""
        fact = _CountingResolution()
        consistency = _CountingResolution()
        orchestrator, service = _wired(fact, consistency)

        await service.ensure_resolved()

        assert orchestrator._configs is not None
        assert orchestrator._configs.fact_extractor_config == replace(
            _cascade_config(), temperature=0.2
        )
        assert orchestrator._configs.consistency_config == replace(
            _cascade_config(), temperature=0.3
        )
        # Credentials land on the composed staged configs and on the
        # service's legacy triple (mirrored consistency stage).
        assert orchestrator._configs.fact_extractor_api_key == _USER_KEY
        assert orchestrator._configs.consistency_api_key == _USER_KEY
        assert service._config == replace(_cascade_config(), temperature=0.3)
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL

    async def test_check_resolves_exactly_once_per_cascade(self) -> None:
        """A full ``check()`` run resolves each cascade exactly once."""
        fact = _CountingResolution()
        consistency = _CountingResolution()
        service, novel, _chapter = _seeded(fact, consistency)

        fact_agent = AsyncMock(
            run=AsyncMock(return_value=FactExtractorOutput(facts=[], assessment_summary=""))
        )
        with (
            patch(
                "narrare_core.agents.fact_extractor_agent.FactExtractorAgent",
                return_value=fact_agent,
            ),
            patch(
                "narrare_core.agents.consistency_agent.ConsistencyAgent",
                return_value=_consistency_agent(),
            ),
        ):
            await service.check(novel_id=novel.id, user_id=novel.user_id, request=_request())

        assert fact.calls == 1
        assert consistency.calls == 1

    async def test_resolution_runs_after_ownership_gate(self) -> None:
        """Gate-before-resolution (L15 ordering): the uid-scoped novel
        gate inside ``collect_check_context`` runs BEFORE the routing
        cascades — never the reverse."""
        trace: list[str] = []
        fact = _CountingResolution()
        consistency = _TracedResolution(trace)
        service, novel, _chapter = _seeded(fact, consistency, trace=trace)

        fact_agent = AsyncMock(
            run=AsyncMock(return_value=FactExtractorOutput(facts=[], assessment_summary=""))
        )
        with (
            patch(
                "narrare_core.agents.fact_extractor_agent.FactExtractorAgent",
                return_value=fact_agent,
            ),
            patch(
                "narrare_core.agents.consistency_agent.ConsistencyAgent",
                return_value=_consistency_agent(),
            ),
        ):
            await service.check(novel_id=novel.id, user_id=novel.user_id, request=_request())

        assert trace == ["gate", "resolve"]


# ===========================================================================
# RULE-11 — loud propagation (consistency is NOT the graceful set)
# ===========================================================================


class TestLoudPropagation:
    """``ConfigurationError`` propagates un-swallowed from first use."""

    async def test_configuration_error_propagates_from_ensure_resolved(self) -> None:
        _orchestrator, service = _wired(
            fact=_CountingResolution(error=ConfigurationError("No AI provider configured.")),
        )

        with pytest.raises(ConfigurationError):
            await service.ensure_resolved()

    async def test_configuration_error_propagates_from_check(self) -> None:
        service, novel, _chapter = _seeded(
            fact=_CountingResolution(error=ConfigurationError("No AI provider configured.")),
        )

        with pytest.raises(ConfigurationError):
            await service.check(novel_id=novel.id, user_id=novel.user_id, request=_request())


# ===========================================================================
# Legacy-only wiring — consistency cascade only
# ===========================================================================


class TestLegacyOnlyWiring:
    """Without an orchestrator, ONLY the CONSISTENCY cascade resolves."""

    async def test_legacy_service_resolves_consistency_cascade_only(self) -> None:
        from narrare.consistency.checker_service import ConsistencyCheckerService

        fact = _CountingResolution()
        consistency = _CountingResolution()
        service = ConsistencyCheckerService(
            chapter_repo=FakeChapterRepository(),
            novel_repo=FakeNovelRepository(),
            kb_repo=AsyncMock(list_entries=AsyncMock(return_value=([], 0))),
            timeline_repo=AsyncMock(),
            registry=cast("ModelRegistry", MagicMock(spec=_RegistryProto)),
            consistency_resolution=consistency,
            composer=cast("PromptComposer", AsyncMock()),
        )
        del fact  # legacy wiring never sees the fact cascade

        await service.ensure_resolved()

        assert consistency.calls == 1
        # No orchestrator → no staged composition → no override applied
        # at service level (the override policy lives with the composed
        # orchestrator wiring; a bare legacy service passes the cascade
        # config through unchanged — pre-migration ctor semantics).
        assert service._config == _cascade_config()
