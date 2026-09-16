"""Lazy factory wiring of ``get_style_variant_service`` (ADR-086 L35, M-budget).

Factory-level half of the L35 lazy contract (the service-level half
lives in ``test_style_variant_service_lazy_resolution.py``):

- ``get_style_variant_service`` runs ZERO cascades and builds ZERO
  pipelines at construction time — FastAPI solves the factory BEFORE
  body validation, so eager resolution would preempt legitimate 422s;
- first use (``ensure_resolved``) runs the routing cascade, the
  token-limits cascade, and the pipeline composition EXACTLY ONCE,
  cached and idempotent;
- the composed runtime reproduces the eager factory's WHAT:
  ``temperature=0.7``, model-capped ``output_limit``, verbatim
  credentials, tier-wired pipeline at ``writing_tier_base`` with
  ``series_in_scope=False`` (Decision 6 standalone semantics — style
  variants never inject ``{{series_history}}``); the REWRITE intent is
  unchanged (the variant never changes providers, RULE-18).

Mirrors ``tests/unit/api/writing/test_deps_extend_lazy_wiring.py``
(ADR-086 L32 precedent).
"""

from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel

if TYPE_CHECKING:
    from narrare.writing.style_variant_service import StyleVariantService
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


def _canned_budgets(tier_base: int = 32_000) -> EffectiveContextBudgets:
    from narrare_core.context.contracts import EffectiveContextBudgets

    return EffectiveContextBudgets(
        context_total=32_000,
        series_history=0,
        writing_tier_base=tier_base,
        reserve_tokens=8_096,
        context_window=128_000,
        source="cascade:uncapped",
    )


def _factory_patch_context(
    budgets: EffectiveContextBudgets | None = None,
) -> tuple[list[Any], _CountingResolution, AsyncMock, MagicMock, MagicMock]:
    """Patch context to run the style-variant factory hermetically.

    Returns ``(patches, counting_resolution, limits_spy, budgets_stub,
    pipeline_spy)`` — counting fakes for BOTH cascades (routing +
    token limits) plus spies for the budget adapter and the pipeline
    construction, per the ADR-086 M-budget deferral contract.
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

    patches = [
        patch(
            "narrare.writing.deps_style_variants.get_model_routing_resolver",
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
        patch(
            "narrare.novels.repository.NovelRepository",
            return_value=MagicMock(spec=["get_by_id"], get_by_id=AsyncMock(return_value=object())),
        ),
    ]
    return patches, counting, limits_spy, budgets_stub, pipeline_spy


async def _run_factory() -> StyleVariantService:
    """Invoke the real ``get_style_variant_service`` under the patch context."""
    module = importlib.import_module("narrare.writing.deps_style_variants")
    service: StyleVariantService = await module.get_style_variant_service(
        session=MagicMock(spec=AsyncSession, name="session"),
        user_id=str(uuid4()),
        project_id=uuid4(),
    )
    return service


class TestLazyFactoryWiring:
    """``get_style_variant_service`` resolves NOTHING at construction (ADR-086)."""

    async def test_no_resolution_at_construction(self) -> None:
        """Factory entry runs ZERO cascades and builds ZERO pipelines.

        FastAPI solves the factory before body validation — eager
        resolution here would preempt legitimate 422s (ADR-086).
        """
        patches, counting, limits_spy, _budgets_stub, pipeline_spy = _factory_patch_context()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            await _run_factory()

        assert counting.calls == 0, "routing cascade must not run at construction"
        assert limits_spy.await_count == 0, "token-limits cascade must not run at construction"
        assert pipeline_spy.call_count == 0, "pipeline must not be built at construction"

    async def test_first_use_resolves_both_cascades_exactly_once(self) -> None:
        """First use runs routing + token-limits + composition ONCE,
        cached — repeat ``ensure_resolved`` calls are idempotent."""
        patches, counting, limits_spy, _budgets_stub, pipeline_spy = _factory_patch_context()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
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
        tier-wired pipeline at ``writing_tier_base`` (series_in_scope
        False — Decision 6 standalone semantics; REWRITE intent)."""
        patches, _counting, _limits_spy, budgets_stub, pipeline_spy = _factory_patch_context()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
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
        pipeline_kwargs = pipeline_spy.call_args.kwargs
        assert pipeline_kwargs["tier_overrides"] == CUSTOM_TIERS
        assert pipeline_kwargs["total_budget"] == _canned_budgets().writing_tier_base
