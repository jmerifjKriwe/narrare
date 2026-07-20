"""Tests for AdaptiveWeights, AdaptiveContext, AdaptiveSettings dataclasses.

Covers: defaults, clamping, frozen, slots, has_any_signal.
See: ADR-069, CONSTRAINTS.md RULE-03/RULE-04.
"""

from __future__ import annotations

import dataclasses
from uuid import uuid4

import pytest

from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
    AdaptiveWeights,
)


class TestAdaptiveWeights:
    """AdaptiveWeights — frozen value object with clamping."""

    def test_default_weights_match_spec(self) -> None:
        """Spec §5.1: preference=0.7, voice_fidelity=0.9,
        style_constraints=1.0, avoidance=1.0."""
        weights = AdaptiveWeights()
        assert weights.preference == 0.7
        assert weights.voice_fidelity == 0.9
        assert weights.style_constraints == 1.0
        assert weights.avoidance == 1.0

    def test_custom_weights_preserved(self) -> None:
        weights = AdaptiveWeights(preference=0.3, voice_fidelity=0.5)
        assert weights.preference == 0.3
        assert weights.voice_fidelity == 0.5

    def test_is_frozen(self) -> None:
        """RULE-03: immutable value object."""
        weights = AdaptiveWeights()
        with pytest.raises(dataclasses.FrozenInstanceError):
            weights.preference = 0.5  # type: ignore[misc]

    def test_is_slotted(self) -> None:
        """No __dict__ — slots prevent arbitrary attribute addition."""
        weights = AdaptiveWeights()
        assert not hasattr(weights, "__dict__")

    def test_validated_clamps_below_zero(self) -> None:
        weights = AdaptiveWeights(preference=-0.5, voice_fidelity=-1.0)
        clamped = weights.validated()
        assert clamped.preference == 0.0
        assert clamped.voice_fidelity == 0.0

    def test_validated_clamps_above_one(self) -> None:
        weights = AdaptiveWeights(style_constraints=2.0, avoidance=1.5)
        clamped = weights.validated()
        assert clamped.style_constraints == 1.0
        assert clamped.avoidance == 1.0

    def test_validated_preserves_in_range(self) -> None:
        weights = AdaptiveWeights(preference=0.42, voice_fidelity=0.81)
        clamped = weights.validated()
        assert clamped.preference == 0.42
        assert clamped.voice_fidelity == 0.81

    def test_validated_returns_new_instance(self) -> None:
        """validated() does not mutate; returns a new frozen instance."""
        weights = AdaptiveWeights(preference=2.0)
        clamped = weights.validated()
        assert weights.preference == 2.0  # original unchanged
        assert clamped.preference == 1.0
        assert clamped is not weights


class TestAdaptiveContext:
    """AdaptiveContext — consolidated snapshot."""

    def test_default_text_fields_empty(self) -> None:
        ctx = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        assert ctx.preference_text == ""
        assert ctx.voice_profiles_text == ""
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
        assert ctx.source_summary == ""

    def test_default_weights_are_factory_fresh(self) -> None:
        """Each new instance gets its own AdaptiveWeights (no shared default)."""
        ctx_a = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        ctx_b = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        assert ctx_a.weights == ctx_b.weights
        assert ctx_a.weights is not ctx_b.weights

    def test_has_any_signal_false_when_all_empty(self) -> None:
        ctx = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        assert ctx.has_any_signal is False

    def test_has_any_signal_true_if_preference_text(self) -> None:
        ctx = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            preference_text="prefers dark prose",
        )
        assert ctx.has_any_signal is True

    def test_has_any_signal_true_if_voice_profiles_text(self) -> None:
        ctx = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            voice_profiles_text="**Alice**: terse",
        )
        assert ctx.has_any_signal is True

    def test_has_any_signal_true_if_style_constraints_text(self) -> None:
        ctx = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            style_constraints_text="- Short sentences",
        )
        assert ctx.has_any_signal is True

    def test_has_any_signal_true_if_avoidance_patterns_text(self) -> None:
        ctx = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            avoidance_patterns_text="- No passive voice",
        )
        assert ctx.has_any_signal is True

    def test_is_frozen(self) -> None:
        ctx = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.preference_text = "mutated"  # type: ignore[misc]

    def test_is_slotted(self) -> None:
        ctx = AdaptiveContext(user_id=uuid4(), project_id=uuid4())
        assert not hasattr(ctx, "__dict__")

    def test_does_not_carry_voice_metrics_field(self) -> None:
        """ADR-055/057 hard constraint: voice_metrics never reach
        AdaptiveContext. Only descriptive text (voice_profiles_text)
        is permitted. Asserting the field list excludes metrics."""
        field_names = {f.name for f in dataclasses.fields(AdaptiveContext)}
        assert "voice_metrics" not in field_names
        assert "metrics" not in field_names
        assert "voice_profiles_text" in field_names


class TestAdaptiveSettings:
    """AdaptiveSettings — persisted user settings."""

    def test_defaults_enabled_with_factory_weights(self) -> None:
        settings = AdaptiveSettings()
        assert settings.enabled is True
        assert isinstance(settings.weights, AdaptiveWeights)
        assert settings.weights.preference == 0.7

    def test_custom_enabled_false(self) -> None:
        settings = AdaptiveSettings(enabled=False)
        assert settings.enabled is False

    def test_custom_weights(self) -> None:
        weights = AdaptiveWeights(voice_fidelity=0.42)
        settings = AdaptiveSettings(enabled=True, weights=weights)
        assert settings.weights.voice_fidelity == 0.42

    def test_default_weights_are_factory_fresh(self) -> None:
        """Each new AdaptiveSettings gets its own AdaptiveWeights."""
        a = AdaptiveSettings()
        b = AdaptiveSettings()
        assert a.weights is not b.weights

    def test_is_frozen(self) -> None:
        settings = AdaptiveSettings()
        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.enabled = False  # type: ignore[misc]

    def test_is_slotted(self) -> None:
        settings = AdaptiveSettings()
        assert not hasattr(settings, "__dict__")

    def test_nested_weights_remain_independent(self) -> None:
        """Two AdaptiveSettings with the same values do not share weights."""
        a = AdaptiveSettings()
        b = AdaptiveSettings()
        assert a.weights == b.weights
        assert a.weights is not b.weights
