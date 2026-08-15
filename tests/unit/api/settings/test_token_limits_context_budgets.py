"""Contract + write-boundary tests for the ADR-082 context budget keys.

Covers: defaults single-sourced from Core constants (DEFAULT_TOKEN_PROFILE
precedent — backend and Core cannot drift), write-boundary bounds
(ge=1_024, ADR-082 Decision 1), and unknown-key rejection unchanged.
"""

from __future__ import annotations

import pytest

from narrare.settings.token_limits._validators import (
    VALID_OVERRIDE_FIELDS,
    validate_token_overrides,
)
from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)
from narrare_core.shared.errors import ValidationError


class TestContractDefaults:
    def test_context_total_budget_defaults_to_core_constant(self) -> None:
        assert TokenLimitOverrides().context_total_budget == DEFAULT_TOTAL_BUDGET

    def test_series_history_budget_defaults_to_core_constant(self) -> None:
        assert TokenLimitOverrides().series_history_budget == DEFAULT_SERIES_HISTORY_BUDGET

    def test_defaults_are_32k_and_16k(self) -> None:
        """ADR-082 Decisions 1/2 — literal pin (catches accidental constant
        re-defaults without a plan)."""
        assert TokenLimitOverrides().context_total_budget == 32_000
        assert TokenLimitOverrides().series_history_budget == 16_000

    def test_explicit_values_preserved(self) -> None:
        overrides = TokenLimitOverrides(context_total_budget=65_536, series_history_budget=8_192)
        assert overrides.context_total_budget == 65_536
        assert overrides.series_history_budget == 8_192


class TestWriteBoundary:
    def test_both_keys_are_valid_override_fields(self) -> None:
        assert "context_total_budget" in VALID_OVERRIDE_FIELDS
        assert "series_history_budget" in VALID_OVERRIDE_FIELDS

    @pytest.mark.parametrize(
        "overrides",
        [
            {"context_total_budget": 65_536},
            {"series_history_budget": 8_192},
            {"context_total_budget": 1_024, "series_history_budget": 1_024},
            # Sibling keys still validate (unchanged behavior).
            {"context_total_budget": 65_536, "ws_timeout": 3_600},
        ],
    )
    def test_accepts_valid_values(self, overrides: dict[str, object]) -> None:
        validate_token_overrides(overrides)  # must not raise

    @pytest.mark.parametrize(
        "overrides",
        [
            {"context_total_budget": 1_023},  # below ge=1_024
            {"series_history_budget": 0},
            {"context_total_budget": 2_048, "series_history_budget": 512},
        ],
    )
    def test_rejects_below_bound(self, overrides: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="must be >=") as excinfo:
            validate_token_overrides(overrides)
        assert excinfo.value.code == "INVALID_BUDGET_BOUNDS"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"context_total_budget": "32000"},  # str, not int
            {"series_history_budget": 16_000.5},  # float
            {"context_total_budget": True},  # bool is not an int budget
        ],
    )
    def test_rejects_non_int_values(self, overrides: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_token_overrides(overrides)

    def test_unknown_field_still_rejected(self) -> None:
        # Deliberately typo'd key — unknown-field rejection is unchanged.
        with pytest.raises(ValidationError, match="Unknown token limit override field"):
            validate_token_overrides({"context_total_budgt": 32_000})
