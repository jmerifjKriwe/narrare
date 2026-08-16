"""C5 / ADR-082 wiring tests — resolved budgets reach the runtime consumers.

Enforcement evidence for RULE-18b: create_pipeline is the ONLY
WritingContextAssembler construction point, and fetch_series_history is
the ONLY series-history assembly call site — pinning both proves the
resolved cascade values reach the runtime consumers.

Factory-level wiring (deps_* resolving against the model window) lives
in the classes below.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.writing._helpers import fetch_series_history
from narrare_core.context.contracts import ContextBudgetResolver, EffectiveContextBudgets
from narrare_core.llm import ResolvedModelConfig
from narrare_core.writing.draft_processor import DraftProcessor


def _fake_resolved_config() -> ResolvedModelConfig:
    """A valid ResolvedModelConfig for ``dataclasses.replace`` in factories."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=4096,
    )


def _fake_session() -> MagicMock:
    """A spec'd AsyncSession mock for factory repository construction."""
    return MagicMock(spec=AsyncSession, name="session")


class TestCreatePipelineForwardsTotalBudget:
    def test_forwards_total_budget_to_assembler(self) -> None:
        from narrare.writing.deps_pipeline import create_pipeline

        pipeline = create_pipeline(DraftProcessor(), total_budget=24_000)

        assert pipeline._context_assembler.total_budget == 24_000

    def test_without_total_budget_keeps_core_default(self) -> None:
        from narrare.writing.deps_pipeline import create_pipeline
        from narrare_core.context.budget import DEFAULT_TOTAL_BUDGET

        pipeline = create_pipeline(DraftProcessor())

        assert pipeline._context_assembler.total_budget == DEFAULT_TOTAL_BUDGET


class TestFetchSeriesHistoryBudget:
    async def test_passes_token_budget_through_to_provider(self) -> None:
        provider = AsyncMock()
        provider.assemble_series_history.return_value = "block"
        novel_id = uuid.uuid4()

        result = await fetch_series_history(provider, novel_id, token_budget=12_000)

        assert result == "block"
        provider.assemble_series_history.assert_awaited_once_with(novel_id, token_budget=12_000)

    async def test_none_budget_calls_provider_without_token_budget(self) -> None:
        """Backward-compatible default: no budget → provider default (16,000)."""
        provider = AsyncMock()
        provider.assemble_series_history.return_value = "block"
        novel_id = uuid.uuid4()

        await fetch_series_history(provider, novel_id)

        provider.assemble_series_history.assert_awaited_once_with(novel_id)

    async def test_none_provider_returns_empty(self) -> None:
        assert await fetch_series_history(None, uuid.uuid4(), token_budget=12_000) == ""


class TestResolveContextBudgetsAdapter:
    """The API-side adapter delegates to the injected resolver with the
    cascade's configured values and the routed model identity."""

    def test_delegates_with_cascade_values(self) -> None:
        from unittest.mock import MagicMock

        from narrare.settings.token_limits.context_budgets import resolve_context_budgets
        from narrare.settings.token_limits.contracts import TokenLimitOverrides
        from narrare_core.llm import ResolvedModelConfig

        canned = EffectiveContextBudgets(
            context_total=24_000,
            series_history=12_000,
            writing_tier_base=12_000,
            reserve_tokens=8_096,
            context_window=128_000,
            source="cascade:uncapped",
        )
        # spec= the Core Protocol the adapter delegates to (RULE-TEST-01):
        # keeps spy semantics while pinning the resolve() signature.
        spy = MagicMock(spec=ContextBudgetResolver, name="resolver")
        spy.resolve.return_value = canned
        limits = TokenLimitOverrides(context_total_budget=24_000, series_history_budget=12_000)
        config = ResolvedModelConfig(provider_name="ollama", model_id="llama3")

        result = resolve_context_budgets(
            limits=limits, config=config, series_in_scope=True, resolver=spy
        )

        assert result is canned
        spy.resolve.assert_called_once_with(
            configured_total=24_000,
            configured_series_history=12_000,
            # TokenLimitOverrides default profile (balanced) resolves 2,000.
            effective_output_limit=limits.effective_output_limit,
            series_in_scope=True,
            provider_name="ollama",
            model_id="llama3",
        )


def _canned_budgets(tier_base: int, series_history: int) -> EffectiveContextBudgets:
    return EffectiveContextBudgets(
        context_total=tier_base + series_history,
        series_history=series_history,
        writing_tier_base=tier_base,
        reserve_tokens=4_096,
        context_window=128_000,
        source="cascade:uncapped",
    )


def _budget_patch_context(module_path: str, budgets: EffectiveContextBudgets):
    """Run a writing factory hermetically: routing resolver, token
    limits, the context-budget adapter, and create_pipeline are patched.
    Returns (ctx-managers, create_pipeline spy, adapter spy)."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from narrare._app.config import Settings
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing.deps_pipeline import create_pipeline

    fake_limits = TokenLimitOverrides()
    fake_token_service = MagicMock(spec=TokenLimitsService, name="token_limits_service")
    fake_token_service.get_resolved_limits = AsyncMock(return_value=fake_limits)

    fake_resolved = SimpleNamespace(
        config=_fake_resolved_config(),
        api_key=None,
        base_url=None,
    )
    fake_routing = MagicMock(spec=ModelRoutingResolverImpl)
    fake_routing.resolve = AsyncMock(return_value=fake_resolved)

    # spec= the real adapter function (RULE-TEST-01) — same pattern as the
    # create_pipeline spy below; validates the factory's call signature
    # while recording kwargs for the wiring assertions.
    adapter_spy = MagicMock(
        spec=resolve_context_budgets, name="resolve_context_budgets", return_value=budgets
    )
    pipeline_spy = MagicMock(spec=create_pipeline, name="create_pipeline_spy")

    ctx = (
        patch(f"{module_path}.get_model_routing_resolver", return_value=fake_routing),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=fake_token_service,
        ),
        patch(
            "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
            adapter_spy,
        ),
        patch("narrare.writing.deps_pipeline.create_pipeline", pipeline_spy),
        patch(
            "narrare._app.config.get_settings",
            return_value=MagicMock(spec=Settings, name="settings"),
        ),
    )
    return ctx, pipeline_spy, adapter_spy


class TestDepsWritingFactoryWiring:
    async def test_passes_resolved_tier_base_and_series_budget(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=16_000, series_history=16_000)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_writing", budgets
        )
        module = importlib.import_module("narrare.writing.deps_writing")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            # project_id=None -> series_in_scope=False path (no novel lookup).
            service = await module.get_writing_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=None,
            )

        assert pipeline_spy.call_args.kwargs["total_budget"] == 16_000
        assert service._series_history_budget == 16_000
        assert adapter_spy.call_args.kwargs["series_in_scope"] is False

    async def test_series_novel_marks_series_in_scope(self) -> None:
        """A novel with series membership resolves with the carve-out."""
        import importlib
        from types import SimpleNamespace
        from unittest.mock import patch as _patch

        budgets = _canned_budgets(tier_base=16_000, series_history=16_000)
        ctx, _pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_writing", budgets
        )
        module = importlib.import_module("narrare.writing.deps_writing")

        series_novel = SimpleNamespace(series_id=uuid.uuid4())
        with (
            ctx[0],
            ctx[1],
            ctx[2],
            ctx[3],
            ctx[4],
            _patch("narrare.novels.repository.NovelRepository") as novel_repo_cls,
        ):
            novel_repo_cls.return_value.get = AsyncMock(return_value=series_novel)
            await module.get_writing_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        assert adapter_spy.call_args.kwargs["series_in_scope"] is True


class TestDepsExtendFactoryWiring:
    async def test_passes_resolved_tier_base_full_total(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=32_000, series_history=0)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_extend", budgets
        )
        module = importlib.import_module("narrare.writing.deps_extend")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            await module.get_extend_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        # Extend never injects series history -> full total as tier base.
        assert adapter_spy.call_args.kwargs["series_in_scope"] is False
        assert pipeline_spy.call_args.kwargs["total_budget"] == 32_000


class TestRemainingWritingFactoriesWiring:
    """rewrite / coauthor / style-variants resolve like extend:
    series_in_scope=False (they never inject series history)."""

    async def test_deps_rewrite_passes_resolved_tier_base(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=32_000, series_history=0)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_rewrite", budgets
        )
        module = importlib.import_module("narrare.writing.deps_rewrite")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            await module.get_rewrite_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        assert adapter_spy.call_args.kwargs["series_in_scope"] is False
        assert pipeline_spy.call_args.kwargs["total_budget"] == 32_000

    async def test_deps_coauthor_passes_resolved_tier_base(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=24_000, series_history=0)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_coauthor", budgets
        )
        module = importlib.import_module("narrare.writing.deps_coauthor")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            await module.get_coauthor_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        assert adapter_spy.call_args.kwargs["series_in_scope"] is False
        assert pipeline_spy.call_args.kwargs["total_budget"] == 24_000

    async def test_deps_style_variants_passes_resolved_tier_base(self) -> None:
        import importlib

        budgets = _canned_budgets(tier_base=28_000, series_history=0)
        ctx, pipeline_spy, adapter_spy = _budget_patch_context(
            "narrare.writing.deps_style_variants", budgets
        )
        module = importlib.import_module("narrare.writing.deps_style_variants")

        with ctx[0], ctx[1], ctx[2], ctx[3], ctx[4]:
            await module.get_style_variant_service(
                session=_fake_session(),
                user_id=str(uuid.uuid4()),
                project_id=uuid.uuid4(),
            )

        assert adapter_spy.call_args.kwargs["series_in_scope"] is False
        assert pipeline_spy.call_args.kwargs["total_budget"] == 28_000
