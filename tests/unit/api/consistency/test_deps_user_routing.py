"""User-routing migration tests for the consistency dependency factory (Task 3).

Lazy-wiring proof (ADR-086 L13, S4b-dual) that
``consistency/deps.get_consistency_service`` wires BOTH staged-pipeline
cascades as ``LazyModelResolution``s via the per-user
``ModelRoutingResolver`` cascade — with NO resolution at construction —
and that first use resolves both intents with the correct args in the
eager factory's verbatim order, threading the resolved configs +
credentials into the orchestrator/service that own the actual
``ModelRegistry.prepare`` resolution calls (Task-6b: resolution flows
prepare → get_model):

- FactExtractor model — ``LLMIntent.FACT_EXTRACT`` (ADR-044 stage 1,
  feature ``consistency_fact_extraction``)
- ConsistencyAgent model — ``LLMIntent.CONSISTENCY`` (staged stage 2,
  feature ``consistency_staged_check``, and the legacy single-pass
  fallback, feature ``consistency_check``)

The legacy temperature overrides (0.2 extractor / 0.3 checker) are
applied at first use via ``dataclasses.replace`` on the RESOLVED
cascade configs. Credential flow into the three real resolution points
is proven in ``TestCredentialsReachResolutionPoint`` (setup-bug shape).
Sibling of ``tests/unit/api/kb/test_deps_user_routing_1b.py`` (Task 1b,
TWO-config shape) — same conventions: fake resolver, cast-pattern
registry fakes.
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

if TYPE_CHECKING:
    from narrare_core.agents.consistency_types import ConsistencyDeps
    from narrare_core.agents.fact_extractor_types import FactExtractorOutput
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts import PromptComposer

# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_deps_user_routing_1b.py, Task 1b conventions)
# ---------------------------------------------------------------------------

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


def _resolved() -> ResolvedModel:
    """A ResolvedModel as the wired-up user's cascade would return."""
    return ResolvedModel(
        config=_user_config(),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )


def _fake_two_resolved_resolver() -> tuple[MagicMock, ResolvedModel, ResolvedModel]:
    """A spec'd fake resolver returning TWO models (extractor + checker)."""
    fact_resolved = _resolved()
    consistency_resolved = _resolved()
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(side_effect=[fact_resolved, consistency_resolved])
    return resolver, fact_resolved, consistency_resolved


class _StopResolution(Exception):
    """Sentinel raised after get_model recorded its call (short-circuits)."""


class _RecordingRegistry:
    """Fake ModelRegistry — records ``get_model`` calls for asserts."""

    def __init__(self, stop_after_record: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._stop = stop_after_record

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        self.calls.append({"config": config, "api_key": api_key, "base_url": base_url})
        if self._stop is not None:
            raise self._stop
        return object()

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        """Task-6b bridge: resolution flows through prepare → get_model.

        Delegates to the SAME recording ``get_model`` call so the
        credential assertions (``registry.calls`` shape) hold for both
        the migrated (prepare) and not-yet-migrated (direct get_model)
        paths under test.
        """
        return SimpleNamespace(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


# ===========================================================================
# Structural — factory is async, user-scoped, legacy-pattern-free
# ===========================================================================

_FACTORY = ("narrare.consistency.deps", "get_consistency_service")


class TestFactoryStructure:
    """Structural regressions: signature gains user routing, legacy is gone."""

    def test_factory_is_async_with_user_routing_params(self) -> None:
        import importlib

        factory = getattr(importlib.import_module(_FACTORY[0]), _FACTORY[1])

        assert inspect.iscoroutinefunction(factory)
        params = list(inspect.signature(factory).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    def test_factory_does_not_use_system_default_config(self) -> None:
        import importlib

        source = inspect.getsource(importlib.import_module(_FACTORY[0]))
        assert "build_system_default_config" not in source
        assert "SystemModelCategory" not in source


# ===========================================================================
# Factory execution — resolver resolves BOTH intents + threads results
# ===========================================================================


class TestConsistencyDepsUserRouting:
    """get_consistency_service lazily wires TWO cascades: FACT_EXTRACT + CONSISTENCY."""

    async def test_wires_lazily_and_resolves_both_intents_on_first_use(self) -> None:
        from dataclasses import replace

        from narrare._app.dependencies_services import LazyModelResolution
        from narrare.consistency.checker_service import ConsistencyCheckerService
        from narrare.consistency.consistency_orchestrator import ConsistencyOrchestrator
        from narrare.consistency.deps import get_consistency_service

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, fact_resolved, consistency_resolved = _fake_two_resolved_resolver()

        with (
            patch(
                "narrare.consistency.deps.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare._app.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare._app.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare._app.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
            patch(
                "narrare._app.config.get_settings",
                return_value=MagicMock(spec=True, name="Settings"),
            ),
            patch(
                "narrare.settings.token_limits.service.TokenLimitsService",
                return_value=MagicMock(spec=True, name="TokenLimitsService"),
            ),
        ):
            service = await get_consistency_service(
                session=session,
                user_id=user_id,
                novel_id=novel_id,
            )

        # Construction neutrality (ADR-086 L13): NO cascade runs at
        # wiring time — both intents are wired as LazyModelResolutions.
        assert resolver.resolve.await_count == 0
        assert isinstance(service, ConsistencyCheckerService)
        assert isinstance(service._consistency_resolution, LazyModelResolution)

        # First use resolves BOTH intents for THIS user + novel, in
        # stage order (extractor first, checker second).
        await service.ensure_resolved()
        assert resolver.resolve.await_args_list == [
            call(LLMIntent.FACT_EXTRACT, UUID(user_id), novel_id),
            call(LLMIntent.CONSISTENCY, UUID(user_id), novel_id),
        ]

        orchestrator = service._orchestrator
        assert isinstance(orchestrator, ConsistencyOrchestrator)

        # Legacy temperature overrides applied at first use on the
        # RESOLVED configs: 0.2 extractor / 0.3 checker; cascade
        # routing fields untouched.
        assert orchestrator._configs is not None
        assert orchestrator._configs.fact_extractor_config == replace(
            fact_resolved.config, temperature=0.2
        )
        assert orchestrator._configs.consistency_config == replace(
            consistency_resolved.config, temperature=0.3
        )
        assert service._config == replace(consistency_resolved.config, temperature=0.3)
        assert service._config is not None
        assert service._config.model_id == "glm-4.7"
        assert service._config.provider_name == "zai"

        # Resolved user credentials land on the orchestrator (both stages)
        # and on the service (legacy single-pass fallback path).
        assert orchestrator._configs.fact_extractor_api_key == _USER_KEY
        assert orchestrator._configs.fact_extractor_base_url == _USER_BASE_URL
        assert orchestrator._configs.consistency_api_key == _USER_KEY
        assert orchestrator._configs.consistency_base_url == _USER_BASE_URL
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL


# ===========================================================================
# Resolution point — credentials reach ModelRegistry.prepare → get_model
# ===========================================================================


class TestCredentialsReachResolutionPoint:
    """The resolved key must flow into the ACTUAL resolution call (setup bug)."""

    def _composer(self) -> MagicMock:
        from narrare_core.prompts.composer import ComposedPrompt

        composer = MagicMock(spec=["build"], name="PromptComposer")
        composer.build = AsyncMock(
            return_value=ComposedPrompt(system="System prompt.", user="User prompt.")
        )
        return composer

    def _deps(self) -> ConsistencyDeps:
        from narrare_core.agents.consistency_types import (
            ConsistencyCheckType,
            ConsistencyDeps,
        )

        chapter_id = str(uuid4())
        return ConsistencyDeps(
            language="en",
            novel_id=str(uuid4()),
            chapter_texts={chapter_id: "Anna walked through the forest."},
            kb_entity_summaries=[],
            timeline_events=[],
            check_types=[ConsistencyCheckType.CHARACTER],
        )

    def _fact_output(self) -> FactExtractorOutput:
        from narrare_core.agents.fact_extractor_types import FactExtractorOutput

        return FactExtractorOutput(facts=[], assessment_summary="")

    async def test_fact_extractor_stage_threads_credentials_into_get_model(self) -> None:
        from narrare._app.dependencies_services import StaticModelResolution
        from narrare.consistency.consistency_orchestrator import ConsistencyOrchestrator

        fact_resolved = _resolved()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        orchestrator = ConsistencyOrchestrator(
            registry=cast("ModelRegistry", registry),
            fact_extractor_resolution=StaticModelResolution(fact_resolved),
            consistency_resolution=StaticModelResolution(_resolved()),
            composer=cast("PromptComposer", self._composer()),
        )

        with pytest.raises(_StopResolution):
            await orchestrator.run_staged_check(
                novel_id=uuid4(),
                deps=self._deps(),
                kb_summaries=[],
                timeline_envelopes=[],
                language="en",
                max_chapter_tokens=2000,
            )

        assert registry.calls == [
            {
                "config": replace(fact_resolved.config, temperature=0.2),
                "api_key": _USER_KEY,
                "base_url": _USER_BASE_URL,
            }
        ]

    async def test_staged_consistency_stage_threads_credentials_into_get_model(self) -> None:
        from narrare.consistency.orchestrator_helpers import run_consistency_stage

        consistency_config = replace(_user_config(), temperature=0.3)
        registry = _RecordingRegistry(stop_after_record=_StopResolution())

        with pytest.raises(_StopResolution):
            await run_consistency_stage(
                registry=cast("ModelRegistry", registry),
                consistency_config=consistency_config,
                composer=cast("PromptComposer", self._composer()),
                novel_id=uuid4(),
                deps=self._deps(),
                kb_summaries=[],
                timeline_envelopes=[],
                language="en",
                max_chapter_tokens=2000,
                fact_output=self._fact_output(),
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
            )

        assert registry.calls == [
            {"config": consistency_config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def test_legacy_check_threads_credentials_into_get_model(self) -> None:
        from narrare.consistency.checker_context import CheckContext
        from narrare.consistency.legacy_check_runner import run_legacy_check

        consistency_config = replace(_user_config(), temperature=0.3)
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        context = CheckContext(
            deps=self._deps(),
            kb_summaries=[],
            timeline_envelopes=[],
            resolved_ids=[],
            language="en",
            max_chapter_tokens=2000,
            rule_issues=[],
        )

        with pytest.raises(_StopResolution):
            await run_legacy_check(
                registry=cast("ModelRegistry", registry),
                config=consistency_config,
                composer=cast("PromptComposer", self._composer()),
                novel_id=uuid4(),
                context=context,
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
            )

        assert registry.calls == [
            {"config": consistency_config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]
