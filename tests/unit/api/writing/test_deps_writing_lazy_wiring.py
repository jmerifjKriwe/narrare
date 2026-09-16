"""Lazy factory wiring of ``get_writing_service`` (ADR-086 L37, M-budget).

Factory-level half of the L37 lazy contract (the service-level half
lives in ``test_writing_service_lazy_resolution.py``):

- ``get_writing_service`` runs ZERO cascades and builds ZERO pipelines
  at construction time — FastAPI solves the factory BEFORE body
  validation, so eager resolution would preempt legitimate 422s;
- first use (``ensure_resolved``) runs the routing cascade, the
  token-limits cascade, and the pipeline composition EXACTLY ONCE,
  cached and idempotent;
- the composed runtime reproduces the eager factory's WHAT:
  ``temperature=0.7``, model-capped ``output_limit``, verbatim
  credentials, the ADR-082 series-scope resolution (Decision 6:
  series membership → carve-out, standalone/none → full total), and
  the tier-wired pipeline at ``writing_tier_base``; the SUGGEST intent
  keeps its fixed short-answer sampling (``temperature=0.3`` +
  ``SUGGEST_MAX_TOKENS``).

Mirrors ``tests/unit/api/writing/test_deps_style_variants_lazy_wiring.py``
(ADR-086 L35 precedent).
"""

from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.llm.run_limits import SUGGEST_MAX_TOKENS

if TYPE_CHECKING:
    from narrare.writing.service import WritingService
    from narrare_core.context.contracts import EffectiveContextBudgets

# A custom, valid 5-tier distribution (sums to 1.0) — proves the resolved
# tier percentages reach the pipeline verbatim at first use.
CUSTOM_TIERS: dict[str, float] = {
    "immediate": 0.50,
    "recent": 0.15,
    "kb_referenced": 0.20,
    "kb_suggested": 0.10,
    "pinned": 0.05,
}

_CASCADE_CONFIG = ResolvedModelConfig(
    provider_name="zai",
    model_id="glm-4.7",
    temperature=0.2,
    max_tokens=8192,
)

_LIMITS = TokenLimitOverrides(output_limit=1500, tier_percentages=CUSTOM_TIERS)


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches."""

    def __init__(self, model: ResolvedModel) -> None:
        self._model = model
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        return self._model


def _resolved_model(config: ResolvedModelConfig, **kw: str | None) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=config,
        api_key=kw.get("api_key"),
        base_url=kw.get("base_url"),
        source="unit-test",
    )


def _canned_budgets(tier_base: int = 32_000, series_history: int = 0) -> EffectiveContextBudgets:
    from narrare_core.context.contracts import EffectiveContextBudgets

    return EffectiveContextBudgets(
        context_total=tier_base + series_history,
        series_history=series_history,
        writing_tier_base=tier_base,
        reserve_tokens=8_096,
        context_window=128_000,
        source="cascade:uncapped",
    )


def _factory_patch_context(
    budgets: EffectiveContextBudgets | None = None,
    *,
    series_novel: object | None = None,
) -> tuple[list[Any], _CountingResolution, AsyncMock, MagicMock, MagicMock, MagicMock]:
    """Patch context to run the writing factory hermetically.

    Returns ``(patches, counting_resolution, limits_spy, budgets_stub,
    pipeline_spy, novel_repo)`` — counting fakes for BOTH cascades
    (routing + token limits) plus spies for the budget adapter and the
    pipeline construction, and the novel-repo instance backing the N1
    ownership gate and the series-scope lookup, per the ADR-086
    M-budget deferral contract.
    """
    from narrare._app.config import Settings
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.settings.token_limits.service import TokenLimitsService

    counting = _CountingResolution(
        _resolved_model(
            _CASCADE_CONFIG,
            api_key="sk-factory-key",
            base_url="https://user.example/v1",
        )
    )

    fake_token_service = MagicMock(spec=TokenLimitsService, name="token_limits_service")
    limits_spy = AsyncMock(return_value=_LIMITS)
    fake_token_service.get_resolved_limits = limits_spy

    async def _resolve_via_counting(*args: object, **kwargs: object) -> ResolvedModel:
        return await counting.resolve()

    # spec= makes isinstance(resolver, ModelRoutingResolverImpl) True,
    # which the factory asserts after obtaining the resolver.
    fake_resolver = MagicMock(spec=ModelRoutingResolverImpl)
    fake_resolver.resolve = AsyncMock(side_effect=_resolve_via_counting)

    budgets_stub = MagicMock(
        spec=resolve_context_budgets,
        name="resolve_context_budgets_stub",
        return_value=budgets or _canned_budgets(),
    )
    pipeline_spy = MagicMock(
        spec=lambda draft_processor, *, tier_overrides=None, total_budget=None: None,
        name="create_pipeline_spy",
    )

    # The novel repo backs BOTH the N1 ownership gate (get_by_id — owned
    # novel) and the series-scope resolution (get — standalone unless a
    # series_novel is injected).
    novel_repo = MagicMock(spec=["get", "get_by_id"], name="novel_repository")
    novel_repo.get_by_id = AsyncMock(return_value=object())
    novel_repo.get = AsyncMock(return_value=series_novel)

    patches = [
        patch(
            "narrare.writing.deps_writing.get_model_routing_resolver",
            return_value=fake_resolver,
        ),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=fake_token_service,
        ),
        patch(
            "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
            budgets_stub,
        ),
        patch("narrare.writing.deps_pipeline.create_pipeline", pipeline_spy),
        patch(
            "narrare._app.config.get_settings",
            return_value=MagicMock(spec=Settings, name="settings"),
        ),
        patch("narrare.novels.repository.NovelRepository", return_value=novel_repo),
    ]
    return patches, counting, limits_spy, budgets_stub, pipeline_spy, novel_repo


async def _run_factory(
    *, project_id: Any = None, intent: LLMIntent = LLMIntent.WRITE
) -> WritingService:
    """Invoke the real ``get_writing_service`` under the patch context."""
    module = importlib.import_module("narrare.writing.deps_writing")
    service: WritingService = await module.get_writing_service(
        session=MagicMock(spec=AsyncSession, name="session"),
        user_id=str(uuid4()),
        project_id=project_id,
        intent=intent,
    )
    return service


def _enter_all(patches: list[Any]) -> contextlib.ExitStack:
    """Enter every patch context manager on one stack."""
    stack = contextlib.ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


class TestLazyFactoryWiring:
    """``get_writing_service`` resolves NOTHING at construction (ADR-086)."""

    async def test_no_resolution_at_construction(self) -> None:
        """Factory entry runs ZERO cascades and builds ZERO pipelines.

        FastAPI solves the factory before body validation — eager
        resolution here would preempt legitimate 422s (ADR-086).
        """
        patches, counting, limits_spy, _budgets_stub, pipeline_spy, _novel_repo = (
            _factory_patch_context()
        )

        with _enter_all(patches):
            await _run_factory()

        assert counting.calls == 0, "routing cascade must not run at construction"
        assert limits_spy.await_count == 0, "token-limits cascade must not run at construction"
        assert pipeline_spy.call_count == 0, "pipeline must not be built at construction"

    async def test_first_use_resolves_both_cascades_exactly_once(self) -> None:
        """First use runs routing + token-limits + composition ONCE,
        cached — repeat ``ensure_resolved`` calls are idempotent."""
        patches, counting, limits_spy, _budgets_stub, pipeline_spy, _novel_repo = (
            _factory_patch_context()
        )

        with _enter_all(patches):
            service = await _run_factory()

            first = await service.ensure_resolved()
            second = await service.ensure_resolved()

        assert counting.calls == 1
        assert limits_spy.await_count == 1
        assert pipeline_spy.call_count == 1
        assert first is second
        assert first.pipeline is pipeline_spy.return_value

    async def test_runtime_composition_pin(self) -> None:
        """The composed runtime reproduces the eager factory's WHAT:
        temperature 0.7, model-capped output limit, verbatim credentials,
        tier-wired pipeline at ``writing_tier_base``, series_in_scope
        False for a projectless factory call (Decision 6 standalone
        semantics), and the routing config passed to the budget
        adapter (the budgets resolve against the WRITING model's
        window, not the sampling-overridden config)."""
        patches, _counting, _limits_spy, budgets_stub, pipeline_spy, _novel_repo = (
            _factory_patch_context()
        )

        with _enter_all(patches):
            service = await _run_factory()
            runtime = await service.ensure_resolved()

        assert runtime.config.temperature == 0.7
        assert runtime.config.max_tokens == _LIMITS.output_limit
        assert runtime.config.provider_name == "zai"
        assert runtime.config.model_id == "glm-4.7"
        assert runtime.api_key == "sk-factory-key"
        assert runtime.base_url == "https://user.example/v1"
        budgets_kwargs = budgets_stub.call_args.kwargs
        assert budgets_kwargs["series_in_scope"] is False
        assert budgets_kwargs["limits"] is _LIMITS
        assert budgets_kwargs["config"] is _CASCADE_CONFIG
        pipeline_kwargs = pipeline_spy.call_args.kwargs
        assert pipeline_kwargs["tier_overrides"] == CUSTOM_TIERS
        assert pipeline_kwargs["total_budget"] == _canned_budgets().writing_tier_base

    async def test_series_novel_marks_series_in_scope_at_first_use(self) -> None:
        """Decision 6 on the deferred path: a novel with series
        membership resolves budgets WITH the series-history carve-out —
        the novel-scope lookup moved past validation together with the
        cascades (same I/O order: routing → limits → novel scope)."""
        from types import SimpleNamespace

        patches, _counting, _limits_spy, budgets_stub, _pipeline_spy, novel_repo = (
            _factory_patch_context(series_novel=SimpleNamespace(series_id=uuid4()))
        )

        with _enter_all(patches):
            service = await _run_factory(project_id=uuid4())
            await service.ensure_resolved()

        novel_repo.get.assert_awaited_once()
        assert budgets_stub.call_args.kwargs["series_in_scope"] is True

    async def test_suggest_intent_sampling_at_first_use(self) -> None:
        """SUGGEST intent keeps its fixed short-answer sampling — the
        eager factory's ``replace(config, temperature=0.3,
        max_tokens=SUGGEST_MAX_TOKENS)`` override, timing-only moved."""
        patches, _counting, _limits_spy, _budgets_stub, _pipeline_spy, _novel_repo = (
            _factory_patch_context()
        )

        with _enter_all(patches):
            service = await _run_factory(intent=LLMIntent.SUGGEST)
            runtime = await service.ensure_resolved()

        assert runtime.config.temperature == 0.3
        assert runtime.config.max_tokens == SUGGEST_MAX_TOKENS

    async def test_limits_kwargs_reproduce_eager_cascade_args(self) -> None:
        """The token-limits cascade is invoked with the SAME user/project
        args the eager factory used (RULE-18b: sources and args
        unchanged, only timing)."""
        patches, _counting, limits_spy, _budgets_stub, _pipeline_spy, _novel_repo = (
            _factory_patch_context()
        )
        project_id = uuid4()
        user_id = str(uuid4())

        with _enter_all(patches):
            module = importlib.import_module("narrare.writing.deps_writing")
            service: WritingService = await module.get_writing_service(
                session=MagicMock(spec=AsyncSession, name="session"),
                user_id=user_id,
                project_id=project_id,
            )
            await service.ensure_resolved()

        limits_spy.assert_awaited_once_with(user_id=user_id, project_id=str(project_id))
