"""Tests for the generic ContextAssembler base class (ADR-025 Decision 3).

Validates the abstract base class, its contract, and the integration
with WritingContextAssembler as the first concrete implementation.
"""

from __future__ import annotations

from typing import Any

import pytest

from narrare_core.context.assembler import ContextAssembler
from narrare_core.context.budget import TokenBudgetManager
from narrare_core.context.contracts import ContextAssemblerProtocol
from narrare_core.context.types import TierBudget
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.models import WritingContext

# ---------------------------------------------------------------------------
# Minimal concrete subclass for base-class tests
# ---------------------------------------------------------------------------


class _StubAssembler(ContextAssembler[dict[str, str]]):
    """Minimal concrete assembler for testing the ABC contract."""

    async def assemble(self, **kwargs: Any) -> dict[str, str]:
        return {"context": "stub-value"}

    def get_tier_allocation(self, **kwargs: Any) -> dict[str, TierBudget]:
        manager = TokenBudgetManager(self.total_budget)
        return manager.allocate()


# ---------------------------------------------------------------------------
# Tests: ContextAssembler ABC
# ---------------------------------------------------------------------------


class TestContextAssemblerABC:
    """Tests for the abstract ContextAssembler base class."""

    def test_cannot_instantiate_abc_directly(self) -> None:
        """ABC cannot be instantiated — subclass must implement abstracts."""
        with pytest.raises(TypeError, match="abstract method"):
            ContextAssembler(total_budget=6000)  # type: ignore[abstract]

    def test_stub_subclass_instantiates(self) -> None:
        """Concrete subclass can be instantiated."""
        asm = _StubAssembler(total_budget=8000)
        assert asm.total_budget == 8000

    async def test_stub_assemble_returns_dict(self) -> None:
        """Concrete assemble() returns the declared type."""
        asm = _StubAssembler(total_budget=6000)
        result = await asm.assemble()
        assert isinstance(result, dict)
        assert result == {"context": "stub-value"}

    def test_stub_get_tier_allocation(self) -> None:
        """Concrete get_tier_allocation() returns tier budgets."""
        asm = _StubAssembler(total_budget=6000)
        tiers = asm.get_tier_allocation()
        assert isinstance(tiers, dict)
        assert all(isinstance(t, TierBudget) for t in tiers.values())
        assert "immediate" in tiers

    def test_total_budget_property(self) -> None:
        """total_budget property returns constructor value."""
        asm = _StubAssembler(total_budget=10000)
        assert asm.total_budget == 10000


# ---------------------------------------------------------------------------
# Tests: WritingContextAssembler inherits ContextAssembler
# ---------------------------------------------------------------------------


class TestWritingContextAssemblerInheritance:
    """Verify WritingContextAssembler is a proper ContextAssembler subclass."""

    def test_is_subclass_of_context_assembler(self) -> None:
        """WritingContextAssembler inherits from ContextAssembler."""
        assert issubclass(WritingContextAssembler, ContextAssembler)

    def test_default_total_budget(self) -> None:
        """Default budget matches TokenBudgetManager.DEFAULT_TOTAL_BUDGET."""
        asm = WritingContextAssembler()
        assert asm.total_budget == TokenBudgetManager.DEFAULT_TOTAL_BUDGET

    def test_custom_total_budget(self) -> None:
        """Custom budget is stored and accessible."""
        asm = WritingContextAssembler(total_budget=10000)
        assert asm.total_budget == 10000

    async def test_assemble_returns_writing_context(self) -> None:
        """assemble() returns WritingContext (the generic T parameter)."""
        asm = WritingContextAssembler()
        result = await asm.assemble()
        assert isinstance(result, WritingContext)

    def test_get_tier_allocation_delegates_to_budget_manager(self) -> None:
        """get_tier_allocation() uses TokenBudgetManager internally."""
        asm = WritingContextAssembler(total_budget=8000)
        tiers = asm.get_tier_allocation()
        assert isinstance(tiers, dict)
        assert "immediate" in tiers
        assert "recent" in tiers
        assert "kb_referenced" in tiers
        assert "kb_suggested" in tiers
        assert "pinned" in tiers

    def test_get_tier_allocation_with_mode(self) -> None:
        """get_tier_allocation() passes kwargs to TokenBudgetManager."""
        asm = WritingContextAssembler(total_budget=8000)
        tiers = asm.get_tier_allocation(mode="extend")
        assert tiers["immediate"].percentage > tiers["recent"].percentage

    def test_get_tier_allocation_first_chapter(self) -> None:
        """get_tier_allocation() respects first_chapter flag."""
        asm = WritingContextAssembler(total_budget=8000)
        tiers = asm.get_tier_allocation(first_chapter=True)
        assert tiers["recent"].percentage == 0.0

    def test_total_budget_in_assembled_context(self) -> None:
        """Assembled WritingContext reflects the configured budget."""
        asm = WritingContextAssembler(total_budget=10000)
        import asyncio

        ctx = asyncio.get_event_loop().run_until_complete(asm.assemble())
        assert ctx.total_budget_tokens == 10000


# ---------------------------------------------------------------------------
# Tests: ContextAssemblerProtocol structural typing
# ---------------------------------------------------------------------------


class TestContextAssemblerProtocol:
    """Verify protocol conformance (structural subtyping)."""

    def test_stub_satisfies_protocol(self) -> None:
        """_StubAssembler satisfies ContextAssemblerProtocol structurally."""
        asm = _StubAssembler(total_budget=6000)
        assert isinstance(asm, ContextAssemblerProtocol)


# ---------------------------------------------------------------------------
# Tests: Import paths (backward compatibility)
# ---------------------------------------------------------------------------


class TestImportPaths:
    """Verify all import paths work after the move."""

    def test_new_path_context_budget(self) -> None:
        """TokenBudgetManager importable from context.budget."""
        from narrare_core.context.budget import TokenBudgetManager as TBM

        assert TBM is TokenBudgetManager

    def test_new_path_context_types(self) -> None:
        """TierBudget importable from context.types."""
        from narrare_core.context.types import TierBudget as TB

        assert TB is TierBudget

    def test_old_path_writing_budget_token_manager(self) -> None:
        """TokenBudgetManager re-exported from writing.budget."""
        from narrare_core.writing.budget import TokenBudgetManager as TBM

        assert TBM is TokenBudgetManager

    def test_old_path_writing_budget_tier_budget(self) -> None:
        """TierBudget re-exported from writing.budget."""
        from narrare_core.writing.budget import TierBudget as TB

        assert TB is TierBudget

    def test_old_path_writing_budget_cap_to_budget(self) -> None:
        """cap_to_budget still importable from writing.budget."""
        from narrare_core.writing.budget import cap_to_budget

        assert callable(cap_to_budget)

    def test_context_init_exports(self) -> None:
        """context.__init__ exports all new types."""
        import narrare_core.context as ctx

        assert hasattr(ctx, "ContextAssembler")
        assert hasattr(ctx, "ContextAssemblerProtocol")
        assert hasattr(ctx, "TokenBudgetManager")
        assert hasattr(ctx, "TierBudget")

    def test_writing_init_still_exports(self) -> None:
        """writing.__init__ still exports TokenBudgetManager + cap_to_budget."""
        import narrare_core.writing as writing

        assert hasattr(writing, "TokenBudgetManager")
        assert hasattr(writing, "WritingContextAssembler")


# ---------------------------------------------------------------------------
# Tests: TierBudget dataclass
# ---------------------------------------------------------------------------


class TestTierBudgetDataclass:
    """Verify TierBudget in its new location."""

    def test_frozen(self) -> None:
        """TierBudget is frozen (immutable)."""
        tb = TierBudget(tier_name="test", percentage=0.5, token_limit=3000)
        with pytest.raises(AttributeError):
            tb.tier_name = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        """pinned_bypass defaults to False."""
        tb = TierBudget(tier_name="test", percentage=0.5, token_limit=3000)
        assert tb.pinned_bypass is False

    def test_pinned_bypass(self) -> None:
        """pinned_bypass can be set."""
        tb = TierBudget(tier_name="pinned", percentage=0.1, token_limit=600, pinned_bypass=True)
        assert tb.pinned_bypass is True
