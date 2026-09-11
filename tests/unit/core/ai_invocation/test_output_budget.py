"""Tests for OutputBudget and OutputBudgetDecision value objects.

Covers:
1. OutputBudget — positive tokens only, zero/negative invalid.
2. OutputBudget — profile handling (None, named, empty invalid).
3. OutputBudgetDecision — construction, source/reason required.
4. Stable serialization roundtrip.
5. Known profile values are valid.
"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from pydantic import ValidationError

from narrare_core.ai_invocation.models import (
    OutputBudget,
    OutputBudgetDecision,
)

# ---------------------------------------------------------------------------
# OutputBudget
# ---------------------------------------------------------------------------


class TestOutputBudget:
    """OutputBudget validated value object."""

    def test_positive_tokens(self) -> None:
        """Positive token count is valid."""
        budget = OutputBudget(max_tokens=4096)
        assert budget.max_tokens == 4096
        assert budget.profile is None

    def test_small_positive_tokens(self) -> None:
        """Token count of 1 is valid (minimum positive)."""
        budget = OutputBudget(max_tokens=1)
        assert budget.max_tokens == 1

    def test_zero_tokens_invalid(self) -> None:
        """Zero tokens is invalid."""
        with pytest.raises(ValidationError, match="max_tokens"):
            OutputBudget(max_tokens=0)

    def test_negative_tokens_invalid(self) -> None:
        """Negative tokens is invalid."""
        with pytest.raises(ValidationError, match="max_tokens"):
            OutputBudget(max_tokens=-100)

    def test_with_named_profile(self) -> None:
        """Named profile is stored."""
        budget = OutputBudget(max_tokens=500, profile="quick")
        assert budget.profile == "quick"
        assert budget.max_tokens == 500

    def test_without_profile(self) -> None:
        """Profile defaults to None."""
        budget = OutputBudget(max_tokens=2000)
        assert budget.profile is None

    def test_empty_profile_invalid(self) -> None:
        """Empty string profile is invalid."""
        with pytest.raises(ValidationError, match="profile"):
            OutputBudget(max_tokens=2000, profile="")

    def test_frozen(self) -> None:
        """OutputBudget is immutable."""
        budget = OutputBudget(max_tokens=100)
        with pytest.raises(ValidationError, match="frozen"):
            cast("Any", budget).max_tokens = 200

    def test_known_profiles(self) -> None:
        """Known profiles from PROFILE_OUTPUT_LIMITS are valid values."""
        for profile_name, tokens in [("quick", 500), ("balanced", 2000), ("long_texts", 64000)]:
            budget = OutputBudget(max_tokens=tokens, profile=profile_name)
            assert budget.profile == profile_name
            assert budget.max_tokens == tokens


class TestOutputBudgetSerialization:
    """Stable serialization for OutputBudget and OutputBudgetDecision."""

    def test_budget_json_roundtrip(self) -> None:
        """OutputBudget survives JSON roundtrip."""
        budget = OutputBudget(max_tokens=2000, profile="balanced")
        data = budget.model_dump()
        json_str = json.dumps(data)
        restored = OutputBudget.model_validate(json.loads(json_str))
        assert restored == budget

    def test_budget_model_dump(self) -> None:
        """model_dump produces expected structure."""
        budget = OutputBudget(max_tokens=500, profile="quick")
        data = budget.model_dump()
        assert data == {"max_tokens": 500, "profile": "quick"}

    def test_budget_none_profile_serialized(self) -> None:
        """None profile is included in dump."""
        budget = OutputBudget(max_tokens=100)
        data = budget.model_dump()
        assert data["profile"] is None


# ---------------------------------------------------------------------------
# OutputBudgetDecision
# ---------------------------------------------------------------------------


class TestOutputBudgetDecision:
    """OutputBudgetDecision provenance metadata."""

    def test_basic_construction(self) -> None:
        """Decision wraps budget with source and reason."""
        budget = OutputBudget(max_tokens=2000, profile="balanced")
        decision = OutputBudgetDecision(
            budget=budget,
            source="profile",
            reason="User selected balanced profile",
        )
        assert decision.budget == budget
        assert decision.source == "profile"
        assert decision.reason == "User selected balanced profile"

    def test_source_required(self) -> None:
        """Source must be non-empty."""
        with pytest.raises(ValidationError, match="source"):
            OutputBudgetDecision(
                budget=OutputBudget(max_tokens=100),
                source="",
                reason="test",
            )

    def test_reason_required(self) -> None:
        """Reason must be non-empty."""
        with pytest.raises(ValidationError, match="reason"):
            OutputBudgetDecision(
                budget=OutputBudget(max_tokens=100),
                source="config",
                reason="",
            )

    def test_frozen(self) -> None:
        """OutputBudgetDecision is immutable."""
        decision = OutputBudgetDecision(
            budget=OutputBudget(max_tokens=100),
            source="default",
            reason="default budget",
        )
        with pytest.raises(ValidationError, match="frozen"):
            cast("Any", decision).source = "changed"

    def test_decision_json_roundtrip(self) -> None:
        """Full decision survives JSON roundtrip."""
        decision = OutputBudgetDecision(
            budget=OutputBudget(max_tokens=8000, profile="long_texts"),
            source="intent_default",
            reason="Long-form writing mode requires large output budget",
        )
        data = decision.model_dump()
        json_str = json.dumps(data)
        restored = OutputBudgetDecision.model_validate(json.loads(json_str))
        assert restored == decision
        assert restored.budget.max_tokens == 8000

    def test_decision_serialization_stable(self) -> None:
        """Serialization is deterministic across calls."""
        decision = OutputBudgetDecision(
            budget=OutputBudget(max_tokens=2000),
            source="config",
            reason="from settings",
        )
        first = decision.model_dump_json()
        second = decision.model_dump_json()
        assert first == second
