"""Tests for IntentOutputBudgetResolverImpl.

Covers all mandatory test cases from P0.3b spec:
1. Happy path — intent with known profile (BETA_READ → long_texts → 16000).
2. Happy path — intent with known profile (NAME_GENERATE → quick → 500).
3. Fallback — intent without profile mapping (EMBED) → default_max_tokens.
4. Custom default_max_tokens in constructor.
5. Provenance — source="intent_profile" when profile found.
6. Reason strings are non-empty and descriptive.
7. OutputBudget returned has correct max_tokens > 0.
8. Protocol conformance — satisfies IntentOutputBudgetResolver Protocol.
9. All existing LLMIntent values produce a valid result (parametrized).
10. Mode is included in reasoning context when provided (informational only).

See: ADR-038, INFRA-013.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from narrare_core.ai_invocation.budgets import (
    IntentOutputBudgetResolverImpl,
    OutputBudget,
    OutputBudgetDecision,
)
from narrare_core.ai_invocation.models import PromptInvocationContext
from narrare_core.llm.intents import LLMIntent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides: object) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext for tests."""
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
    }
    defaults.update(overrides)
    return cast("Any", PromptInvocationContext)(**defaults)


# ---------------------------------------------------------------------------
# All LLMIntent values (excluding EMBED which is not routeable)
# ---------------------------------------------------------------------------

#: All routeable LLMIntent values — those present in INTENT_CATEGORY_MAP.
ROUTEABLE_INTENTS: list[LLMIntent] = [member for member in LLMIntent if member != LLMIntent.EMBED]


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestIntentOutputBudgetResolverHappyPath:
    """Happy-path resolution with known profile mappings."""

    @pytest.mark.asyncio
    async def test_beta_read_maps_to_long_texts(self) -> None:
        """BETA_READ → profile 'long_texts' → 16000 tokens (raised from 8000)."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.BETA_READ)
        decision = await resolver.resolve(ctx)

        assert decision.budget.max_tokens == 16000
        assert decision.budget.profile == "long_texts"

    @pytest.mark.asyncio
    async def test_name_generate_maps_to_quick(self) -> None:
        """NAME_GENERATE → profile 'quick' → 500 tokens."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.NAME_GENERATE)
        decision = await resolver.resolve(ctx)

        assert decision.budget.max_tokens == 500
        assert decision.budget.profile == "quick"


class TestIntentOutputBudgetResolverFallback:
    """Fallback when no profile mapping exists."""

    @pytest.mark.asyncio
    async def test_embed_intent_uses_default(self) -> None:
        """EMBED has no profile mapping → default_max_tokens (4096)."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.EMBED)
        decision = await resolver.resolve(ctx)

        assert decision.budget.max_tokens == 4096
        assert decision.budget.profile is None

    @pytest.mark.asyncio
    async def test_custom_default_max_tokens(self) -> None:
        """Constructor-configured default is used when no profile exists."""
        resolver = IntentOutputBudgetResolverImpl(default_max_tokens=2048)
        ctx = _make_context(intent=LLMIntent.EMBED)
        decision = await resolver.resolve(ctx)

        assert decision.budget.max_tokens == 2048

    def test_constructor_rejects_non_positive_default(self) -> None:
        """Constructor raises ValueError for non-positive default_max_tokens."""
        with pytest.raises(ValueError, match="positive"):
            IntentOutputBudgetResolverImpl(default_max_tokens=0)

    def test_constructor_rejects_negative_default(self) -> None:
        """Constructor raises ValueError for negative default_max_tokens."""
        with pytest.raises(ValueError, match="positive"):
            IntentOutputBudgetResolverImpl(default_max_tokens=-100)


class TestIntentOutputBudgetResolverProvenance:
    """Provenance metadata (source and reason) tests."""

    @pytest.mark.asyncio
    async def test_source_intent_profile_when_mapped(self) -> None:
        """source='intent_profile' when intent has a profile mapping."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.BETA_READ)
        decision = await resolver.resolve(ctx)

        assert decision.source == "intent_profile"

    @pytest.mark.asyncio
    async def test_source_default_config_when_unmapped(self) -> None:
        """source='default_config' when intent has no profile mapping (EMBED)."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.EMBED)
        decision = await resolver.resolve(ctx)

        assert decision.source == "default_config"

    @pytest.mark.asyncio
    async def test_reason_non_empty_when_mapped(self) -> None:
        """Reason is non-empty and descriptive when profile is found."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.BETA_READ)
        decision = await resolver.resolve(ctx)

        assert len(decision.reason) > 0
        assert "beta_read" in decision.reason
        assert "long_texts" in decision.reason

    @pytest.mark.asyncio
    async def test_reason_non_empty_when_unmapped(self) -> None:
        """Reason is non-empty and descriptive when using default (EMBED)."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.EMBED)
        decision = await resolver.resolve(ctx)

        assert len(decision.reason) > 0
        assert "embed" in decision.reason
        assert "default" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_reason_includes_mode_when_provided(self) -> None:
        """Mode is included in reason string when provided."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.WRITE, mode="new_chapter")
        decision = await resolver.resolve(ctx)

        assert "mode=" in decision.reason
        assert "new_chapter" in decision.reason

    @pytest.mark.asyncio
    async def test_reason_includes_mode_with_profile(self) -> None:
        """Mode is included in reason even when profile is found."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.BETA_READ, mode="detailed")
        decision = await resolver.resolve(ctx)

        assert "mode=" in decision.reason
        assert "detailed" in decision.reason
        assert decision.budget.profile == "long_texts"

    @pytest.mark.asyncio
    async def test_reason_omits_mode_when_none(self) -> None:
        """Mode is not mentioned in reason when it is None."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.CHAT)
        decision = await resolver.resolve(ctx)

        assert "mode=" not in decision.reason


class TestIntentOutputBudgetResolverOutputBudget:
    """OutputBudget value correctness."""

    @pytest.mark.asyncio
    async def test_budget_max_tokens_positive(self) -> None:
        """Resolved budget always has max_tokens > 0."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.CHAT)
        decision = await resolver.resolve(ctx)

        assert decision.budget.max_tokens > 0

    @pytest.mark.asyncio
    async def test_budget_is_output_budget_instance(self) -> None:
        """Returned budget is an OutputBudget instance."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.WRITE)
        decision = await resolver.resolve(ctx)

        assert isinstance(decision.budget, OutputBudget)

    @pytest.mark.asyncio
    async def test_decision_is_output_budget_decision_instance(self) -> None:
        """Returned decision is an OutputBudgetDecision instance."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=LLMIntent.WRITE)
        decision = await resolver.resolve(ctx)

        assert isinstance(decision, OutputBudgetDecision)


class TestIntentOutputBudgetResolverProtocolConformance:
    """Protocol conformance — IntentOutputBudgetResolver."""

    def test_has_resolve_method(self) -> None:
        """IntentOutputBudgetResolverImpl has the required resolve method."""
        resolver = IntentOutputBudgetResolverImpl()
        assert hasattr(resolver, "resolve")
        assert callable(resolver.resolve)

    def test_satisfies_protocol_structurally(self) -> None:
        """IntentOutputBudgetResolverImpl satisfies IntentOutputBudgetResolver."""
        resolver = IntentOutputBudgetResolverImpl()
        # Structural subtyping check: the resolver has the resolve method
        # with the correct signature. This is verified by the Protocol
        # system at runtime via hasattr + callable checks.
        assert hasattr(resolver, "resolve")

    @pytest.mark.asyncio
    async def test_resolve_returns_output_budget_decision(self) -> None:
        """resolve() returns an OutputBudgetDecision (Protocol contract)."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context()
        decision = await resolver.resolve(ctx)
        assert isinstance(decision, OutputBudgetDecision)


class TestIntentOutputBudgetResolverAllIntents:
    """All routeable LLMIntent values produce valid results."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("intent", ROUTEABLE_INTENTS)
    async def test_every_intent_returns_valid_decision(self, intent: LLMIntent) -> None:
        """Every routeable intent produces a valid OutputBudgetDecision."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=intent)
        decision = await resolver.resolve(ctx)

        assert isinstance(decision, OutputBudgetDecision)
        assert decision.budget.max_tokens > 0
        assert len(decision.source) > 0
        assert len(decision.reason) > 0
        assert decision.source in ("intent_profile", "default_config")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("intent", ROUTEABLE_INTENTS)
    async def test_every_intent_decision_is_frozen(self, intent: LLMIntent) -> None:
        """Every decision is immutable (frozen Pydantic model)."""
        resolver = IntentOutputBudgetResolverImpl()
        ctx = _make_context(intent=intent)
        decision = await resolver.resolve(ctx)

        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="frozen"):
            cast("Any", decision).source = "changed"


class TestIntentOutputBudgetResolverConcurrency:
    """Stateless resolver is safe for concurrent use."""

    @pytest.mark.asyncio
    async def test_concurrent_resolves_are_independent(self) -> None:
        """Multiple concurrent resolve calls produce correct, independent results."""
        import asyncio

        resolver = IntentOutputBudgetResolverImpl()

        contexts = [
            _make_context(intent=LLMIntent.BETA_READ),
            _make_context(intent=LLMIntent.NAME_GENERATE),
            _make_context(intent=LLMIntent.CHAT),
            _make_context(intent=LLMIntent.WRITE),
        ]

        decisions = await asyncio.gather(*(resolver.resolve(ctx) for ctx in contexts))

        assert decisions[0].budget.max_tokens == 16000  # BETA_READ → long_texts
        assert decisions[1].budget.max_tokens == 500  # NAME_GENERATE → quick
        assert decisions[2].budget.max_tokens == 2000  # CHAT → balanced
        assert decisions[3].budget.max_tokens == 16000  # WRITE → long_texts


class TestIntentOutputBudgetResolverNeverRaises:
    """Resolver NEVER raises — always returns a valid decision."""

    @pytest.mark.asyncio
    async def test_no_exception_for_any_routeable_intent(self) -> None:
        """All routeable intents resolve without raising."""
        resolver = IntentOutputBudgetResolverImpl()
        for intent in ROUTEABLE_INTENTS:
            ctx = _make_context(intent=intent)
            decision = await resolver.resolve(ctx)
            assert isinstance(decision, OutputBudgetDecision)
