"""Regression tests for FIND-012 / CR-AUFG-08-02 (backend wiring).

The backend writing DI factories resolve ``tier_percentages`` from the
``TokenLimitsService`` but previously never forwarded them to the
``WritingContextAssembler``: ``create_pipeline`` constructed the assembler
with no ``tier_overrides``, so user-configured tier percentages had zero
effect on the emitted tier budgets (FIND-012).

These tests pin the contract that the resolved tier percentages reach the
assembler via the shared ``create_pipeline`` factory and that *every*
pipeline-based writing factory wires them through.

Key behavioural guarantees:

1. ``create_pipeline`` forwards ``tier_overrides`` to the assembler.
2. ``create_pipeline`` defaults to ``None`` so mode-specific allocations
   (extend 50/15/20/10/5, rewrite, first-chapter) are preserved when no
   override is configured — passing the always-present default dict would
   otherwise clobber those mode bases.
3. Each writing factory passes ``limits.tier_percentages`` to
   ``create_pipeline``.
4. Changing the resolved ``tier_percentages`` changes the override the
   assembler receives.
5. ``TokenLimitOverrides.tier_percentages`` is ``None`` by default (the
   "not configured" sentinel that maps to core's ``tier_overrides=None``).
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare_core.llm import ResolvedModelConfig
from narrare_core.writing.draft_processor import DraftProcessor

# A custom, valid 5-tier distribution (sums to 1.0) that is clearly
# distinct from the code default (30/20/25/15/10).
CUSTOM_TIERS: dict[str, float] = {
    "immediate": 0.50,
    "recent": 0.15,
    "kb_referenced": 0.20,
    "kb_suggested": 0.10,
    "pinned": 0.05,
}

# A second, different distribution used to prove the override is dynamic
# (not a cached/hardcoded constant).
ALT_TIERS: dict[str, float] = {
    "immediate": 0.35,
    "recent": 0.25,
    "kb_referenced": 0.20,
    "kb_suggested": 0.10,
    "pinned": 0.10,
}


def _fake_resolved_config() -> ResolvedModelConfig:
    """A valid ResolvedModelConfig for ``dataclasses.replace`` in factories."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=4096,
    )


def _fake_session() -> MagicMock:
    """A spec'd AsyncSession mock for factory repository construction.

    Repository constructors only store the session, so a spec'd mock is
    sufficient and satisfies RULE-TEST-01 (no bare ``MagicMock()``).
    """
    return MagicMock(spec=AsyncSession, name="session")


# ---------------------------------------------------------------------------
# create_pipeline — the single WritingContextAssembler construction point
# ---------------------------------------------------------------------------


class TestCreatePipelineForwardsTierOverrides:
    """FIND-012: ``create_pipeline`` must forward tier_overrides to the assembler.

    ``create_pipeline`` is the ONLY production site that constructs a
    ``WritingContextAssembler``; all four pipeline-based writing factories
    route through it.  If it forwards the overrides, every factory inherits
    the fix.
    """

    def test_create_pipeline_forwards_tier_overrides_to_assembler(self) -> None:
        """REGRESSION (FIND-012): overrides reach the assembler's budget manager.

        Before the fix ``create_pipeline`` did not accept ``tier_overrides``
        (TypeError) and the assembler was built with code defaults only.
        """
        from narrare.writing.deps_pipeline import create_pipeline

        pipeline = create_pipeline(
            DraftProcessor(),
            tier_overrides={"immediate": 0.50},
        )

        budgets = pipeline._context_assembler.get_tier_allocation()
        assert budgets["immediate"].percentage == pytest.approx(0.50)
        assert budgets["immediate"].token_limit == pytest.approx(
            pipeline._context_assembler._total_budget * 0.50
        )

    def test_create_pipeline_default_none_preserves_extend_mode(self) -> None:
        """No overrides (default) preserves the extend mode allocation.

        Passing the always-present default dict instead of ``None`` would
        clobber mode-specific bases; ``None`` keeps the extend (50/15/20/10/5)
        allocation intact.
        """
        from narrare.writing.deps_pipeline import create_pipeline

        pipeline = create_pipeline(DraftProcessor())
        budgets = pipeline._context_assembler.get_tier_allocation(mode="extend")

        assert budgets["immediate"].percentage == pytest.approx(0.50)
        assert budgets["kb_suggested"].percentage == pytest.approx(0.10)

    def test_create_pipeline_default_none_preserves_first_chapter_mode(self) -> None:
        """No overrides preserves the first-chapter allocation (recent → 0)."""
        from narrare.writing.deps_pipeline import create_pipeline

        pipeline = create_pipeline(DraftProcessor())
        budgets = pipeline._context_assembler.get_tier_allocation(first_chapter=True)

        assert budgets["recent"].percentage == pytest.approx(0.0)
        assert budgets["kb_referenced"].percentage == pytest.approx(0.35)


# ---------------------------------------------------------------------------
# Factory wiring — each writing factory passes limits.tier_percentages
# ---------------------------------------------------------------------------

# Each entry maps a pipeline-based factory to the module that owns the
# ``get_model_routing_resolver`` import the factory uses.  ``deps_suggest``
# is intentionally excluded: it does not build a WritingPipeline and has no
# WritingContextAssembler.
PIPELINE_FACTORIES = [
    ("narrare.writing.deps_writing", "get_writing_service"),
    ("narrare.writing.deps_extend", "get_extend_service"),
    ("narrare.writing.deps_coauthor", "get_coauthor_service"),
    ("narrare.writing.deps_rewrite", "get_rewrite_service"),
]


def _factory_patch_context(module_path: str, tier_percentages: dict[str, float] | None):
    """Build the patch context required to run a writing factory without a DB.

    Patches the model-routing resolver, the token-limits service, the shared
    ``create_pipeline`` (as a spy) and ``get_settings`` so the factory can be
    exercised in isolation.  Returns the ``create_pipeline`` spy so callers
    can assert on the wiring.
    """
    from narrare._app.config import Settings
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing.deps_pipeline import create_pipeline

    fake_limits = TokenLimitOverrides(tier_percentages=tier_percentages)
    fake_token_service = MagicMock(spec=TokenLimitsService, name="token_limits_service")
    fake_token_service.get_resolved_limits = AsyncMock(return_value=fake_limits)

    fake_resolved = SimpleNamespace(
        config=_fake_resolved_config(),
        api_key=None,
        base_url=None,
    )
    # spec= makes isinstance(resolver, ModelRoutingResolverImpl) True, which
    # every factory asserts after obtaining the resolver.
    fake_resolver = MagicMock(spec=ModelRoutingResolverImpl)
    fake_resolver.resolve = AsyncMock(return_value=fake_resolved)

    # spec=create_pipeline validates the call signature while letting us
    # assert on the recorded kwargs (the wiring under test).
    pipeline_spy = MagicMock(spec=create_pipeline, name="create_pipeline_spy")

    ctx = (
        patch(f"{module_path}.get_model_routing_resolver", return_value=fake_resolver),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=fake_token_service,
        ),
        patch("narrare.writing.deps_pipeline.create_pipeline", pipeline_spy),
        patch(
            "narrare._app.config.get_settings",
            return_value=MagicMock(spec=Settings, name="settings"),
        ),
    )
    return ctx, pipeline_spy


@pytest.mark.parametrize(("module_path", "factory_name"), PIPELINE_FACTORIES)
class TestFactoriesWireTierOverrides:
    """Every pipeline-based writing factory wires resolved tier_percentages."""

    async def test_factory_passes_resolved_tier_percentages(
        self, module_path: str, factory_name: str
    ) -> None:
        """The factory forwards ``limits.tier_percentages`` to ``create_pipeline``."""
        module = importlib.import_module(module_path)
        factory = getattr(module, factory_name)

        ctx, pipeline_spy = _factory_patch_context(module_path, CUSTOM_TIERS)
        with ctx[0], ctx[1], ctx[2], ctx[3]:
            await factory(
                session=_fake_session(),
                user_id=str(uuid4()),
                project_id=uuid4(),
            )

        assert pipeline_spy.call_count == 1, "factory must build exactly one pipeline"
        assert pipeline_spy.call_args.kwargs["tier_overrides"] == CUSTOM_TIERS, (
            f"{factory_name} must pass limits.tier_percentages as tier_overrides"
        )

    async def test_factory_passes_none_when_no_override_configured(
        self, module_path: str, factory_name: str
    ) -> None:
        """When no tier_percentages are configured, ``None`` is forwarded.

        ``None`` (not the default dict) preserves mode-specific allocations;
        passing the default dict would silently clobber extend/rewrite modes.
        """
        module = importlib.import_module(module_path)
        factory = getattr(module, factory_name)

        ctx, pipeline_spy = _factory_patch_context(module_path, None)
        with ctx[0], ctx[1], ctx[2], ctx[3]:
            await factory(
                session=_fake_session(),
                user_id=str(uuid4()),
                project_id=uuid4(),
            )

        assert pipeline_spy.call_args.kwargs["tier_overrides"] is None

    async def test_factory_reflects_changed_tier_percentages(
        self, module_path: str, factory_name: str
    ) -> None:
        """Changing the resolved tier_percentages changes the forwarded override.

        Proves the wiring is dynamic (reads the resolved limits each call),
        not a cached or hardcoded constant.
        """
        module = importlib.import_module(module_path)
        factory = getattr(module, factory_name)

        ctx, pipeline_spy = _factory_patch_context(module_path, ALT_TIERS)
        with ctx[0], ctx[1], ctx[2], ctx[3]:
            await factory(
                session=_fake_session(),
                user_id=str(uuid4()),
                project_id=uuid4(),
            )

        assert pipeline_spy.call_args.kwargs["tier_overrides"] == ALT_TIERS


# ---------------------------------------------------------------------------
# Contract — TokenLimitOverrides.tier_percentages is nullable
# ---------------------------------------------------------------------------


class TestTokenLimitOverridesTierPercentagesNullable:
    """The "not configured" sentinel for tier_percentages is ``None``.

    ``None`` maps directly to core's ``WritingContextAssembler(tier_overrides=None)``
    so mode-specific allocations are preserved when the user has not
    configured tier percentages.
    """

    def test_default_tier_percentages_is_none(self) -> None:
        from narrare.settings.token_limits.contracts import TokenLimitOverrides

        assert TokenLimitOverrides().tier_percentages is None

    def test_explicit_tier_percentages_preserved(self) -> None:
        from narrare.settings.token_limits.contracts import TokenLimitOverrides

        overrides = TokenLimitOverrides(tier_percentages=CUSTOM_TIERS)
        assert overrides.tier_percentages == CUSTOM_TIERS
