"""Unit tests for the ADR-082 context budget resolver.

Covers the ADR Implementation Notes test list: default no-cap (128k window),
8k-window capping (total 6,000 / series-history 3,000 continuity property),
unknown-window passthrough + source tag, reserve boundary
min(fixed + output, window // 4), and the containment invariant
(series_history + writing_tier_base == context_total).

The window provider is always injected — these tests never touch the
models.dev cache or the network (RULE-07 pure Core).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
    RESERVE_FIXED,
    SERIES_HISTORY_MAX_SHARE,
)
from narrare_core.context.budget_resolver import DefaultContextBudgetResolver
from narrare_core.context.contracts import (
    ContextBudgetResolver,
    EffectiveContextBudgets,
)
from narrare_core.llm import ModelLimits


def _window_provider(window: int | None):
    """Build a ModelLimits provider returning a fixed context window."""

    def _provider(_provider_name: str, _model_id: str) -> ModelLimits | None:
        if window is None:
            return None
        return ModelLimits(context=window, output=4096)

    return _provider


def _resolver(window: int | None) -> DefaultContextBudgetResolver:
    return DefaultContextBudgetResolver(model_limits_provider=_window_provider(window))


def _resolve(
    resolver: DefaultContextBudgetResolver, **overrides: object
) -> EffectiveContextBudgets:
    kwargs: dict[str, object] = {
        "configured_total": 32_000,
        "configured_series_history": 16_000,
        "effective_output_limit": 4_096,
        "series_in_scope": True,
        "provider_name": "anthropic",
        "model_id": "claude-sonnet-4-5-20251020",
    }
    kwargs.update(overrides)
    return resolver.resolve(**kwargs)  # type: ignore[arg-type]


class TestContract:
    def test_default_resolver_satisfies_protocol(self) -> None:
        assert isinstance(DefaultContextBudgetResolver(), ContextBudgetResolver)

    def test_result_model_is_frozen(self) -> None:
        budgets = _resolve(_resolver(128_000))
        with pytest.raises(PydanticValidationError):
            budgets.context_total = 1  # type: ignore[misc]


class TestDefaultNoCap:
    def test_128k_window_applies_full_configured_budget(self) -> None:
        """128k window: reserve 8,096 → cap 119,904 → full 32,000 applies."""
        budgets = _resolve(_resolver(128_000))

        assert budgets.context_total == 32_000
        assert budgets.series_history == 16_000  # 16k = exactly 50% of 32k
        assert budgets.writing_tier_base == 16_000
        assert budgets.reserve_tokens == 8_096  # min(4_000 + 4_096, 128_000 // 4)
        assert budgets.context_window == 128_000
        assert budgets.source == "cascade:uncapped"


class TestSmallWindowCapping:
    def test_8k_window_caps_total_to_6000_and_series_to_3000(self) -> None:
        """PO-approved continuity property: 8k model → reserve 2,000 →
        effective total 6,000 (today's working set, now window-valid),
        series-history ≤ 3,000."""
        budgets = _resolve(_resolver(8_000))

        assert budgets.reserve_tokens == 2_000  # min(8_096, 8_000 // 4)
        assert budgets.context_total == 6_000  # min(32_000, 8_000 - 2_000)
        assert budgets.series_history == 3_000  # min(16_000, floor(0.5 * 6_000))
        assert budgets.writing_tier_base == 3_000
        assert budgets.source == "cascade:capped_to_window"


class TestUnknownWindow:
    def test_unknown_window_passes_configured_through_with_source_tag(self) -> None:
        """RULE-11: no capping on unknown window; proceed + tag provenance."""
        budgets = _resolve(_resolver(None))

        assert budgets.context_total == 32_000
        assert budgets.series_history == 16_000
        assert budgets.writing_tier_base == 16_000
        assert budgets.reserve_tokens is None
        assert budgets.context_window is None
        assert budgets.source == "cascade:window_unknown"


class TestReserveBoundary:
    def test_reserve_uses_fixed_plus_output_on_large_windows(self) -> None:
        budgets = _resolve(_resolver(128_000), effective_output_limit=2_000)

        assert budgets.reserve_tokens == RESERVE_FIXED + 2_000  # 6_000 < 32_000

    def test_reserve_uses_window_quarter_on_small_windows(self) -> None:
        budgets = _resolve(_resolver(8_000), effective_output_limit=4_096)

        assert budgets.reserve_tokens == 8_000 // 4  # 2_000 < 8_096

    def test_reserve_at_equality_boundary(self) -> None:
        """fixed + output == window // 4 → both branches agree on 8,000."""
        budgets = _resolve(_resolver(32_000), effective_output_limit=4_000)

        assert budgets.reserve_tokens == 8_000


class TestMinPrinciple:
    def test_never_scales_up(self) -> None:
        """Configured total below the cap stays as-is (D5 min() only)."""
        budgets = _resolve(
            _resolver(128_000),
            configured_total=4_096,
            configured_series_history=2_048,
        )

        assert budgets.context_total == 4_096
        assert budgets.series_history == 2_048
        assert budgets.source == "cascade:uncapped"


class TestStandaloneAsymmetry:
    def test_standalone_allocates_full_total_to_tiers(self) -> None:
        """series_in_scope=False → no carve-out; tier base = full total."""
        budgets = _resolve(_resolver(128_000), series_in_scope=False)

        assert budgets.series_history == 0
        assert budgets.writing_tier_base == 32_000


class TestContainmentInvariant:
    @pytest.mark.parametrize(
        ("window", "series_in_scope"),
        [
            (128_000, True),
            (128_000, False),
            (8_000, True),
            (8_000, False),
            (None, True),
            (None, False),
        ],
    )
    def test_series_history_plus_tier_base_equals_total(
        self, window: int | None, series_in_scope: bool
    ) -> None:
        budgets = _resolve(
            _resolver(window),
            series_in_scope=series_in_scope,
            configured_series_history=DEFAULT_SERIES_HISTORY_BUDGET,
            configured_total=DEFAULT_TOTAL_BUDGET,
        )

        assert budgets.series_history + budgets.writing_tier_base == budgets.context_total
        assert SERIES_HISTORY_MAX_SHARE == 0.5  # guard pin (ADR-082 Axis 3 Option C)
